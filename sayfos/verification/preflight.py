"""
Sayfos Preflight — lightweight plan-boundary verification.

This module provides the community SDK reference implementation for
checking a multi-step plan against machine-readable execution boundaries
before the plan reaches tools, APIs, cloud resources, data systems, or
embodied endpoints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sayfos.core.models import ActionDeclaration


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Verdict types ──────────────────────────────────────────────────


class PreflightVerdict(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_RESERVE = "approve_with_reserve"
    CROP = "crop"
    REJECT = "reject"
    DOWNGRADE = "downgrade"
    HUMAN_REVIEW = "human_review"


# ── Reference strategies ───────────────────────────────────────────


class PreflightStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    FULL_AGGREGATE = "full_aggregate"
    KEY_STEP = "key_step"
    RISK_WEIGHTED = "risk_weighted"


# ── Step summary ───────────────────────────────────────────────────


@dataclass(frozen=True)
class StepSummary:
    """
    Machine-readable summary of one execution step.
    """

    action_type: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    risk_level: int = 0
    irreversible: bool = False
    dependencies: tuple[int, ...] = ()
    expected_resource: dict[str, float] = field(default_factory=dict)
    consequence_level: int = 0
    parameter_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    @classmethod
    def from_action(cls, action: ActionDeclaration) -> "StepSummary":
        return cls(
            action_type=action.action_type,
            target=action.target,
            parameters=action.parameters,
            risk_level=action.risk_level,
            irreversible=action.risk_level >= 7,
            expected_resource=_deductions_from_action(action),
        )


# ── Execution plan ─────────────────────────────────────────────────


@dataclass(frozen=True)
class PreflightPlan:
    """
    Multi-step execution plan submitted for preflight.
    """

    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_now)
    owner_id: str = ""
    plan_name: str = ""
    steps: tuple[StepSummary, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        converted = tuple(
            StepSummary.from_action(step)
            if isinstance(step, ActionDeclaration)
            else step
            for step in self.steps
        )
        object.__setattr__(self, "steps", converted)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @classmethod
    def from_actions(cls, owner_id: str, plan_name: str, actions: tuple[ActionDeclaration, ...]) -> "PreflightPlan":
        return cls(
            owner_id=owner_id,
            plan_name=plan_name,
            steps=tuple(StepSummary.from_action(a) for a in actions),
        )


# ── Execution boundary ─────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutionBoundary:
    """
    Machine-readable limits for an automated executor, plan, or step.
    """

    boundary_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Budget limits
    budget: dict[str, float] = field(default_factory=dict)

    # Time-window limits
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None

    # Resource quotas
    resource_quotas: dict[str, float] = field(default_factory=dict)

    # Physical safety limits
    spatial_bounds: Optional[str] = None
    speed_limit: Optional[float] = None
    proximity_limit_cm: Optional[float] = None

    # External impact limits
    max_external_calls: int = 0
    max_data_egress_mb: float = 0.0

    # Compliance tags and approvals
    compliance_tags: tuple[str, ...] = ()
    required_approvals: tuple[str, ...] = ()

    @classmethod
    def budget_only(cls, quotas: dict[str, float]) -> "ExecutionBoundary":
        return cls(budget=dict(quotas))

    @classmethod
    def full_constraints(
        cls,
        budget: Optional[dict[str, float]] = None,
        time_window_end: Optional[datetime] = None,
        resource_quotas: Optional[dict[str, float]] = None,
        max_external_calls: int = 0,
        max_data_egress_mb: float = 0.0,
    ) -> "ExecutionBoundary":
        return cls(
            budget=budget or {},
            time_window_end=time_window_end,
            resource_quotas=resource_quotas or {},
            max_external_calls=max_external_calls,
            max_data_egress_mb=max_data_egress_mb,
        )

    @property
    def dimensions(self) -> list[str]:
        dims: list[str] = list(self.budget.keys())
        dims.extend(self.resource_quotas.keys())
        if self.max_external_calls > 0:
            dims.append("external_calls")
        if self.max_data_egress_mb > 0:
            dims.append("data_egress_mb")
        return dims

    @property
    def all_limits(self) -> dict[str, float]:
        limits: dict[str, float] = dict(self.budget)
        limits.update(self.resource_quotas)
        if self.max_external_calls > 0:
            limits["external_calls"] = float(self.max_external_calls)
        if self.max_data_egress_mb > 0:
            limits["data_egress_mb"] = float(self.max_data_egress_mb)
        return limits


# ── Preflight result ────────────────────────────────────────────────


@dataclass(frozen=True)
class PreflightResult:
    """
    Result returned by plan preflight.
    """

    plan_id: str = ""
    feasible: bool = True
    score: float = 1.0
    reason_code: str = "PLAN_FEASIBLE"

    estimated_consumption: dict[str, float] = field(default_factory=dict)
    limits_remaining_after: dict[str, float] = field(default_factory=dict)

    first_overflow_step: int = -1
    overflow_dimension: str = ""
    overflow_detail: str = ""

    step_consumptions: tuple[dict[str, float], ...] = ()
    step_scores: tuple[float, ...] = ()

    strategy: PreflightStrategy = PreflightStrategy.SEQUENTIAL
    verdict: PreflightVerdict = PreflightVerdict.APPROVE

    @property
    def budget_remaining_after(self) -> dict[str, float]:
        """Compatibility alias for budget-oriented examples."""
        return self.limits_remaining_after


# Helper functions


def _deductions_from_action(action: ActionDeclaration) -> dict[str, float]:
    d: dict[str, float] = {}
    params = action.parameters
    if action.action_type in ("payment", "transfer"):
        d["amount_cny"] = float(params.get("amount", 0))
    if action.action_type == "data_egress":
        d["data_egress_mb"] = float(params.get("size_mb", 0))
    if action.action_type == "deploy":
        d["resource_units"] = float(params.get("amount", 0))
    d["tool_calls"] = 1.0
    return d


# ── Preflight engine ────────────────────────────────────────────────


class PreflightEngine:
    """
    Lightweight reference engine for checking execution plans against boundaries.
    """

    HIGH_RISK_TYPES: frozenset[str] = frozenset({
        "payment", "transfer", "data_egress",
        "permission_change", "deploy", "delete",
    })

    def preflight(
        self,
        plan: PreflightPlan,
        boundary: ExecutionBoundary,
        strategy: PreflightStrategy = PreflightStrategy.SEQUENTIAL,
    ) -> PreflightResult:
        if strategy == PreflightStrategy.FULL_AGGREGATE:
            return self._full_aggregate(plan, boundary)
        if strategy == PreflightStrategy.KEY_STEP:
            return self._key_step(plan, boundary)
        if strategy == PreflightStrategy.RISK_WEIGHTED:
            return self._risk_weighted(plan, boundary)
        return self._sequential(plan, boundary)

    def adapt(
        self,
        plan: PreflightPlan,
        boundary: ExecutionBoundary | dict[str, float],
        strategy: PreflightStrategy = PreflightStrategy.SEQUENTIAL,
    ) -> PreflightResult:
        """Compatibility wrapper for early SDK examples."""
        if isinstance(boundary, dict):
            boundary = ExecutionBoundary.budget_only(boundary)
        return self.preflight(plan, boundary, strategy)

    # Sequential accumulation strategy

    def _sequential(
        self, plan: PreflightPlan, boundary: ExecutionBoundary,
    ) -> PreflightResult:
        limits = dict(boundary.all_limits)
        consumptions: list[dict[str, float]] = []
        scores: list[float] = []

        for i, step in enumerate(plan.steps):
            d = step.expected_resource or {}
            consumptions.append(d)

            for dim, amount in d.items():
                if dim in limits:
                    limits[dim] = limits[dim] - amount
                    if limits[dim] < 0:
                        return PreflightResult(
                            plan_id=plan.plan_id,
                            feasible=False,
                            score=max(0.0, 1.0 - (i + 1) / max(plan.step_count, 1)),
                            reason_code="PLAN_BUDGET_OVERFLOW",
                            estimated_consumption=_sum_dicts(consumptions),
                            limits_remaining_after=limits,
                            first_overflow_step=i,
                            overflow_dimension=dim,
                            overflow_detail=(
                                f"step {i} ({step.action_type}): "
                                f"{dim} exceeded by {-limits[dim]:.1f}"
                            ),
                            step_consumptions=tuple(consumptions),
                            step_scores=tuple(scores + [0.0]),
                            strategy=PreflightStrategy.SEQUENTIAL,
                            verdict=PreflightVerdict.REJECT,
                        )
            scores.append(1.0)

        all_ok = all(v >= 0 for v in limits.values())
        if not all_ok:
            return PreflightResult(
                plan_id=plan.plan_id, feasible=False, score=0.5,
                reason_code="PREFLIGHT_BOUNDARY_INSUFFICIENT",
                estimated_consumption=_sum_dicts(consumptions),
                limits_remaining_after=limits,
                step_consumptions=tuple(consumptions), step_scores=tuple(scores),
                strategy=PreflightStrategy.SEQUENTIAL,
                verdict=PreflightVerdict.REJECT,
            )

        return PreflightResult(
            plan_id=plan.plan_id, feasible=True, score=1.0,
            reason_code="PLAN_FEASIBLE",
            estimated_consumption=_sum_dicts(consumptions),
            limits_remaining_after=limits,
            step_consumptions=tuple(consumptions), step_scores=tuple(scores),
            strategy=PreflightStrategy.SEQUENTIAL,
            verdict=PreflightVerdict.APPROVE,
        )

    # Full aggregate strategy

    def _full_aggregate(
        self, plan: PreflightPlan, boundary: ExecutionBoundary,
    ) -> PreflightResult:
        limits = dict(boundary.all_limits)
        total: dict[str, float] = {}
        for step in plan.steps:
            for dim, amount in (step.expected_resource or {}).items():
                total[dim] = total.get(dim, 0.0) + amount

        for dim, amount in total.items():
            if dim in limits and amount > limits[dim]:
                remaining_after = {d: limits.get(d, 0.0) - total.get(d, 0.0) for d in set(limits) | set(total)}
                return PreflightResult(
                    plan_id=plan.plan_id, feasible=False, score=0.0,
                    reason_code="PREFLIGHT_BOUNDARY_EXCEEDED",
                    estimated_consumption=total, limits_remaining_after=remaining_after,
                    overflow_dimension=dim,
                    overflow_detail=f"total {dim}: need {amount}, have {limits[dim]}",
                    strategy=PreflightStrategy.FULL_AGGREGATE,
                    verdict=PreflightVerdict.REJECT,
                )

        remaining_after = {d: limits.get(d, 0.0) - total.get(d, 0.0) for d in set(limits) | set(total)}
        return PreflightResult(
            plan_id=plan.plan_id, feasible=True, score=1.0,
            reason_code="PLAN_FEASIBLE",
            estimated_consumption=total, limits_remaining_after=remaining_after,
            strategy=PreflightStrategy.FULL_AGGREGATE,
            verdict=PreflightVerdict.APPROVE,
        )

    # Key-step strategy

    def _key_step(
        self, plan: PreflightPlan, boundary: ExecutionBoundary,
    ) -> PreflightResult:
        limits = dict(boundary.all_limits)
        batch: dict[str, float] = {}
        key_indices: list[int] = []

        for i, step in enumerate(plan.steps):
            if step.action_type in self.HIGH_RISK_TYPES:
                key_indices.append(i)
            else:
                for dim, amount in (step.expected_resource or {}).items():
                    batch[dim] = batch.get(dim, 0.0) + amount

        for dim, amount in batch.items():
            if dim in limits:
                limits[dim] = limits[dim] - amount

        for i in key_indices:
            step = plan.steps[i]
            for dim, amount in (step.expected_resource or {}).items():
                if dim in limits:
                    limits[dim] = limits[dim] - amount
                    if limits[dim] < 0:
                        return PreflightResult(
                            plan_id=plan.plan_id, feasible=False, score=0.0,
                            reason_code="PREFLIGHT_BOUNDARY_EXCEEDED_KEY_STEP",
                            limits_remaining_after=limits,
                            first_overflow_step=i, overflow_dimension=dim,
                            overflow_detail=f"key step {i} ({step.action_type}) exceeded {dim}",
                            strategy=PreflightStrategy.KEY_STEP,
                            verdict=PreflightVerdict.REJECT,
                        )

        return PreflightResult(
            plan_id=plan.plan_id, feasible=True, score=1.0,
            reason_code="PLAN_FEASIBLE", limits_remaining_after=limits,
            strategy=PreflightStrategy.KEY_STEP,
            verdict=PreflightVerdict.APPROVE,
        )

    # Risk-weighted strategy

    def _risk_weighted(
        self, plan: PreflightPlan, boundary: ExecutionBoundary,
    ) -> PreflightResult:
        limits = dict(boundary.all_limits)
        consumptions: list[dict[str, float]] = []

        for i, step in enumerate(plan.steps):
            weight = 1.0 + step.risk_level * 0.25
            d = {dim: amount * weight for dim, amount in (step.expected_resource or {}).items()}
            consumptions.append(d)

            for dim, amount in d.items():
                if dim in limits:
                    limits[dim] = limits[dim] - amount
                    if limits[dim] < 0:
                        return PreflightResult(
                            plan_id=plan.plan_id, feasible=False, score=0.0,
                            reason_code="PREFLIGHT_BOUNDARY_EXCEEDED_RISK_WEIGHTED",
                            estimated_consumption=_sum_dicts(consumptions),
                            limits_remaining_after=limits,
                            first_overflow_step=i, overflow_dimension=dim,
                            overflow_detail=(
                                f"risk-weighted step {i} (risk={step.risk_level}, "
                                f"weight={weight:.2f}) exceeded {dim}"
                            ),
                            step_consumptions=tuple(consumptions),
                            strategy=PreflightStrategy.RISK_WEIGHTED,
                            verdict=PreflightVerdict.REJECT,
                        )

        return PreflightResult(
            plan_id=plan.plan_id, feasible=True, score=1.0,
            reason_code="PLAN_FEASIBLE",
            estimated_consumption=_sum_dicts(consumptions),
            limits_remaining_after=limits,
            step_consumptions=tuple(consumptions),
            strategy=PreflightStrategy.RISK_WEIGHTED,
            verdict=PreflightVerdict.APPROVE,
        )


def _sum_dicts(dicts: list[dict[str, float]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for d in dicts:
        for k, v in d.items():
            result[k] = result.get(k, 0.0) + v
    return result


# ── Compatibility aliases ───────────────────────────────────────────


PlanDeclaration = PreflightPlan
PlanVerdict = PreflightVerdict
