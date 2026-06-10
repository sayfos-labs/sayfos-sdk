"""
Sayfos Protocol — Abstract base classes for verification engines.

Each verifier corresponds to one patent-governed dimension:
  - Causal consistency (embodied consistency): digital vs physical/embodied evidence
  - Budget governance (budget governance): proxy-authority budget consumption
  - Source chain integrity (source-chain integrity): action provenance completeness

All verifiers return VerificationResult objects.  The pipeline
combines results into an AdjudicationToken with propagated constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sayfos.core.models import (
    ActionConstraint,
    ActionDeclaration,
    AdjudicationToken,
    Budget,
    IntentVerificationRequest,
)
from sayfos.core.enums import BudgetStatus, SourceChainBreakTag, Verdict


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class VerificationResult:
    """Output from a single verification dimension."""

    passed: bool = True
    score: float = 1.0
    reason_code: str = ""
    detail: str = ""
    constraints: tuple[ActionConstraint, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseVerifier(ABC):
    """Strategy interface for a verification dimension."""

    @abstractmethod
    def verify(
        self,
        request: IntentVerificationRequest,
    ) -> VerificationResult:
        ...


# ── embodied consistency: Causal Consistency ───────────────────────────────────────────


class CausalConsistencyVerifier(BaseVerifier):
    """
    Verify causal consistency between a digital action and physical state.

    A break (digital-active but physical-silent) produces BLACK_VERDICT
    with BLOCK constraint.  Partial evidence produces degraded score
    without block — caller decides threshold.
    """

    BLOCK_THRESHOLD: float = 0.1

    def verify(self, request: IntentVerificationRequest) -> VerificationResult:
        action = request.action

        digital_active = bool(
            action.action_type
            or action.target
            or action.parameters
        )
        physical_signals = (
            request.touch_events
            + request.key_events
            + int(request.screen_on)
            + int(bool(request.device_held))
            + int(bool(request.bio_presence))
        )

        # Score based on physical evidence density
        if not digital_active:
            score = 1.0
        elif physical_signals == 0:
            score = 0.0
        else:
            score = min(1.0, physical_signals / 10.0)

        passed = score >= self.BLOCK_THRESHOLD
        break_detected = score < 0.5
        constraints: tuple[ActionConstraint, ...] = ()

        reasons: list[str] = []
        if request.remote_control_detected:
            reasons.append("remote_control_detected")
        if not request.touch_events and not request.key_events:
            reasons.append("no_physical_interaction")
        if not request.screen_on:
            reasons.append("screen_off")
        if request.device_held is False:
            reasons.append("device_not_held")

        if not passed:
            constraints = (
                ActionConstraint(
                    action_ref=action.action_id,
                    block_execution=True,
                    downgrade_autonomy=True,
                    reason_code="CAUSAL_BREAK",
                ),
            )

        return VerificationResult(
            passed=passed,
            score=score,
            reason_code="CAUSAL_BREAK" if break_detected else "CAUSAL_OK",
            detail="|".join(reasons) if reasons else "ok",
            constraints=constraints,
            metadata={
                "digital_active": digital_active,
                "physical_signals": physical_signals,
                "touch_events": request.touch_events,
                "key_events": request.key_events,
                "screen_on": request.screen_on,
                "remote_control_detected": request.remote_control_detected,
                "break_detected": break_detected,
            },
        )


# ── budget governance: Budget Governance ────────────────────────────────────────────


class BudgetGovernanceVerifier(BaseVerifier):
    """
    Budget governance verifier:

    S1  Budget object already determined (carried in request or
        managed by external budget store).
    S2  This verifier determines budget consumption / adaptation.
    S3  Adjudication token carries the budget verdict.
    S4  ActionConstraint propagates scope limits downstream.

    The verifier is stateless; it reads the budget snapshot from the
    request and returns a verdict + constraint.  The caller (pipeline
    or budget store) is responsible for persisting the updated Budget.
    """

    def verify(self, request: IntentVerificationRequest) -> VerificationResult:
        constraints: list[ActionConstraint] = []

        # Terminal states
        if request.budget_status in (BudgetStatus.REVOKED, BudgetStatus.EXPIRED):
            return VerificationResult(
                passed=False,
                score=0.0,
                reason_code="BUDGET_TERMINATED",
                detail=f"status={request.budget_status.value}",
                constraints=(
                    ActionConstraint(
                        action_ref=request.action.action_id,
                        block_execution=True,
                        revoke_tool_tokens=True,
                        reason_code="BUDGET_TERMINATED",
                    ),
                ),
            )

        if request.budget_status == BudgetStatus.FROZEN:
            return VerificationResult(
                passed=False,
                score=0.0,
                reason_code="BUDGET_FROZEN",
                detail="budget_frozen",
                constraints=(
                    ActionConstraint(
                        action_ref=request.action.action_id,
                        block_execution=True,
                        freeze_task_chain=True,
                        reason_code="BUDGET_FROZEN",
                    ),
                ),
            )

        remaining = request.budget_remaining or {}
        if not remaining:
            return VerificationResult(passed=True, score=1.0)

        # Dimension exhaustion
        exhausted: list[str] = []
        constrained: list[str] = []
        for dim, limit in remaining.items():
            if isinstance(limit, (int, float)):
                if limit <= 0:
                    exhausted.append(dim)
                elif limit < _low_watermark(dim):
                    constrained.append(dim)

        if exhausted:
            return VerificationResult(
                passed=False,
                score=0.0,
                reason_code="BUDGET_EXHAUSTED",
                detail="|".join(exhausted),
                constraints=(
                    ActionConstraint(
                        action_ref=request.action.action_id,
                        block_execution=True,
                        reason_code="BUDGET_EXHAUSTED",
                    ),
                ),
                metadata={"exhausted_dimensions": exhausted},
            )

        if constrained:
            return VerificationResult(
                passed=True,
                score=0.5,
                reason_code="BUDGET_LOW",
                detail="|".join(constrained),
                constraints=(
                    ActionConstraint(
                        action_ref=request.action.action_id,
                        require_human_review=True,
                        reason_code="BUDGET_LOW",
                    ),
                ),
                metadata={"constrained_dimensions": constrained, "remaining": remaining},
            )

        return VerificationResult(
            passed=True,
            score=1.0,
            metadata={"remaining": remaining},
        )


def _low_watermark(dim: str) -> float:
    """Threshold below which budget is considered constrained."""
    watermarks: dict[str, float] = {
        "amount": 100.0,
        "amount_cny": 100.0,
        "tool_calls": 3,
        "task_depth": 2,
        "data_egress_mb": 10.0,
    }
    return watermarks.get(dim, 5.0)


# ── source-chain integrity: Source Chain Integrity ───────────────────────────────────────


class SourceChainVerifier(BaseVerifier):
    """
    Source-chain integrity verifier:

    S1  Source chain object generated at interception (ActionDeclaration
        carries the chain fields; ChainEntry builds the hash link).
    S2  This verifier checks chain completeness, trust, and continuity
        using both field-level rules and hash-chain verification.
    S3  Adjudication token carries chain verdict and break tags.
    S4  ActionConstraint downgrades autonomy or requires human review.

    The verifier supports two modes:
      - field-level: check if required provenance fields are present
      - hash-chain: verify cryptographic chain continuity (if a
        SourceChain object is attached to the request)
    """

    # Action types that MUST carry a complete source chain
    HIGH_RISK_TYPES: frozenset[str] = frozenset({
        "payment", "transfer", "data_egress", "permission_change",
        "deploy", "delete", "config_change", "physical_actuation",
    })

    def verify(self, request: IntentVerificationRequest) -> VerificationResult:
        action = request.action
        break_tags: list[SourceChainBreakTag] = []
        constraints: list[ActionConstraint] = []

        # ── field-level checks ──────────────────────────────────
        if not action.root_authorization_ref and not action.human_anchor_ref:
            break_tags.append(SourceChainBreakTag.MISSING_AUTHORIZATION)

        if not action.task_lineage_ref:
            break_tags.append(SourceChainBreakTag.MISSING_TASK_LINEAGE)

        if action.input_source_ref and "untrusted" in action.input_source_ref.lower():
            break_tags.append(SourceChainBreakTag.INPUT_POLLUTION)

        if (
            not action.tool_reason_ref
            and action.action_type in self.HIGH_RISK_TYPES
        ):
            break_tags.append(SourceChainBreakTag.TOOL_REASON_MISSING)

        if not action.decision_token_ref:
            break_tags.append(SourceChainBreakTag.ADJUDICATION_SOURCE_MISSING)

        # ── hash-chain continuity ───────────────────────────────
        chain_present = bool(
            request.source_chain_entries or request.previous_chain_hash
        )
        chain_hash_broken = self._check_hash_break(action, request)

        if chain_hash_broken:
            break_tags.append(SourceChainBreakTag.CHAIN_HASH_MISMATCH)

        if not chain_present and bool(action.parent_action_id):
            break_tags.append(SourceChainBreakTag.CHAIN_HASH_MISMATCH)

        # Revocation state
        if getattr(action, "revocation_active", False):
            break_tags.append(SourceChainBreakTag.REVOCATION_ACTIVE)

        # ── verdict ─────────────────────────────────────────────
        if not break_tags:
            return VerificationResult(
                passed=True,
                score=1.0,
                metadata={"source_chain_verified": True, "chain_present": chain_present},
            )

        score = max(0.0, 1.0 - len(break_tags) * 0.2)
        severe_break = any(
            tag in break_tags
            for tag in (
                SourceChainBreakTag.CHAIN_HASH_MISMATCH,
                SourceChainBreakTag.INPUT_POLLUTION,
                SourceChainBreakTag.REVOCATION_ACTIVE,
                SourceChainBreakTag.NODE_UNTRUSTED,
            )
        )
        high_risk_action = action.action_type in self.HIGH_RISK_TYPES
        passed = not severe_break and (score >= 0.5 or not high_risk_action)

        if not passed:
            constraints.append(
                ActionConstraint(
                    action_ref=action.action_id,
                    require_human_review=True,
                    downgrade_autonomy=True,
                    reason_code="SOURCE_CHAIN_INCOMPLETE",
                )
            )

        return VerificationResult(
            passed=passed,
            score=score,
            reason_code="SOURCE_CHAIN_INCOMPLETE",
            detail="|".join(t.value for t in break_tags),
            constraints=tuple(constraints),
            metadata={
                "break_tags": [t.value for t in break_tags],
                "chain_present": chain_present,
                "chain_hash_broken": chain_hash_broken,
                "high_risk_action": high_risk_action,
            },
        )

    @staticmethod
    def _check_hash_break(
        action: ActionDeclaration,
        request: IntentVerificationRequest,
    ) -> bool:
        """
        Verify that the action's content_hash incorporates the
        previous chain hash correctly.

        If the action has a previous_content_hash and the request
        carries a previous_chain_hash, they must match.
        """
        prev_declared = getattr(action, "previous_content_hash", None)
        prev_request = request.previous_chain_hash

        if prev_declared and prev_request:
            return prev_declared != prev_request
        if prev_declared and not prev_request:
            return True  # declared a link but no previous hash provided
        return False
