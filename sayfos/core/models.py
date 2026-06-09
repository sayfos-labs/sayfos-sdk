"""
Sayfos Protocol — Five standard semantic object definitions.

All five objects are frozen dataclasses. Once created they are immutable.
This guarantees that any downstream verifier, adjudicator, or auditor
operates on a snapshot that cannot be altered mid-flow — a necessary
property for source-chain integrity and audit trail trustworthiness.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sayfos.core.enums import (
    BudgetStatus,
    SourceChainBreakTag,
    Verdict,
)

_SEP = "|"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. Action Declaration ────────────────────────────────────────────


@dataclass(frozen=True)
class ActionDeclaration:
    """
    Machine-readable description of an impending high-risk action.

    Generated at the interception point (SDK, tool gateway, API gateway)
    before the action reaches the execution endpoint.
    """

    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_now)

    # Who / what is acting
    actor_id: str = ""
    actor_type: str = ""

    # What the action is
    action_type: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    # Where the action came from (source-chain fields)
    parent_action_id: Optional[str] = None
    root_authorization_ref: Optional[str] = None
    human_anchor_ref: Optional[str] = None
    task_lineage_ref: Optional[str] = None
    input_source_ref: Optional[str] = None
    tool_reason_ref: Optional[str] = None
    tool_call_ref: Optional[str] = None
    budget_state_ref: Optional[str] = None
    decision_token_ref: Optional[str] = None
    consequence_summary_ref: Optional[str] = None

    # Source-chain fields
    previous_content_hash: Optional[str] = None

    # Execution context
    context: dict[str, Any] = field(default_factory=dict)
    risk_level: int = 0

    def __hash__(self) -> int:
        return hash((
            self.action_id,
            self.timestamp,
            self.actor_id,
            self.actor_type,
            self.action_type,
            self.target,
            json.dumps(self.parameters, sort_keys=True, default=str),
            self.parent_action_id,
            self.root_authorization_ref,
            self.human_anchor_ref,
            self.task_lineage_ref,
            self.input_source_ref,
            self.tool_reason_ref,
            self.tool_call_ref,
            self.budget_state_ref,
            self.decision_token_ref,
            self.consequence_summary_ref,
            self.previous_content_hash,
            json.dumps(self.context, sort_keys=True, default=str),
            self.risk_level,
        ))

    def content_hash(self) -> str:
        """Deterministic content hash for source-chain linking."""
        payload = _SEP.join(
            str(v)
            for v in (
                self.action_type,
                self.target,
                json.dumps(self.parameters, sort_keys=True),
                self.actor_id,
                self.risk_level,
                self.previous_content_hash or "",
            )
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_chain_entry(self) -> "ChainEntry":
        """
        Convert this declaration into a ChainEntry for source-chain tracking.
        Import deferred to avoid circular dependency.
        """
        from sayfos.core.chain import ChainEntry

        return ChainEntry(
            timestamp=self.timestamp,
            action_ref=self.action_id,
            action_type=self.action_type,
            actor_id=self.actor_id,
            content_hash=self.content_hash(),
            authorization_ref=self.root_authorization_ref,
            human_anchor_ref=self.human_anchor_ref,
            task_lineage_ref=self.task_lineage_ref,
            input_source_ref=self.input_source_ref,
            tool_reason_ref=self.tool_reason_ref,
            adjudication_ref=self.decision_token_ref,
            budget_state_ref=self.budget_state_ref,
        )


# ── 2. Intent Verification Request ───────────────────────────────────


@dataclass(frozen=True)
class IntentVerificationRequest:
    """
    Carries the ActionDeclaration and all contextual evidence needed
    for human-intent verification and embodied causal-consistency checks.
    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_now)

    action: ActionDeclaration = field(default_factory=ActionDeclaration)

    # Human / embodied state snapshots
    human_present: Optional[bool] = None
    human_attentive: Optional[bool] = None
    authorization_valid: Optional[bool] = None

    # Physical interaction evidence (embodied consistency embodied verification)
    touch_events: int = 0
    key_events: int = 0
    screen_on: bool = True
    device_held: Optional[bool] = None
    device_pose_stable: Optional[bool] = None
    bio_presence: Optional[bool] = None

    # Environment
    foreground_focus: Optional[str] = None
    remote_control_detected: bool = False

    # Budget snapshot at time of request (budget governance)
    budget_remaining: Optional[dict[str, Any]] = None
    budget_status: BudgetStatus = BudgetStatus.ACTIVE

    # Source-chain snapshot (source-chain integrity)
    source_chain_entries: tuple[str, ...] = ()
    previous_chain_hash: Optional[str] = None


# ── 3. Embodied Response ─────────────────────────────────────────────


@dataclass(frozen=True)
class EmbodiedResponse:
    """
    Result of causal-consistency computation between the declared digital
    action and observed physical / embodied state (embodied consistency).

    A low causal_consistency_score or a positive break_detected indicates
    the digital action lacks corresponding physical interaction evidence —
    the core "non-embodied" attack signature.
    """

    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_now)

    causal_consistency_score: float = 1.0
    break_detected: bool = False
    break_reason: str = ""

    # Detailed evidence
    digital_active: bool = False
    physical_active: bool = False
    touch_trajectory: Optional[str] = None
    pose_state: Optional[str] = None
    device_present: Optional[bool] = None
    physical_operation_missing: bool = False

    confidence: float = 1.0


# ── 4. Adjudication Token ────────────────────────────────────────────


@dataclass(frozen=True)
class AdjudicationToken:
    """
    The binding verdict object produced by the Sayfos pipeline.

    Combines the results of intent verification, embodied response,
    budget governance, and source-chain integrity into a single,
    cryptographically hashable token that the execution endpoint
    MUST consume before allowing the action to proceed.
    """

    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=_now)
    action_ref: str = ""

    # Composite verdict
    verdict: Verdict = Verdict.ALLOW
    reason_code: str = ""
    reason_detail: str = ""

    # Multi-dimensional scores
    intent_consistency_score: float = 1.0
    embodied_consistency_score: float = 1.0
    budget_adequacy_score: float = 1.0
    source_chain_integrity_score: float = 1.0

    # Constraints to propagate
    constraints: dict[str, Any] = field(default_factory=dict)
    budget_deduction: Optional[dict[str, Any]] = None
    budget_deduction_applied: bool = False

    # Source-chain fields
    source_chain_break_tags: tuple[SourceChainBreakTag, ...] = ()
    revocation_flag: bool = False
    downgrade_flag: bool = False

    # Audit linking
    previous_token_ref: Optional[str] = None
    audit_summary_ref: Optional[str] = None

    def token_hash(self) -> str:
        payload = _SEP.join(
            str(v)
            for v in (
                self.action_ref,
                self.verdict.value,
                self.reason_code,
                self.intent_consistency_score,
                self.embodied_consistency_score,
                self.budget_adequacy_score,
                self.source_chain_integrity_score,
            )
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ── 5. Audit Summary ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AuditSummary:
    """
    Immutable, machine-verifiable audit record of a complete Sayfos
    verification cycle.

    Designed to be stored, queried, and replayed for compliance,
    post-incident forensics, and patent-evidence support.
    """

    summary_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recorded_at: datetime = field(default_factory=_now)

    action_ref: str = ""
    actor_id: str = ""

    # Snapshots
    action_snapshot: Optional[dict[str, Any]] = None
    verification_snapshot: Optional[dict[str, Any]] = None
    embodied_snapshot: Optional[dict[str, Any]] = None
    budget_snapshot: Optional[dict[str, Any]] = None
    source_chain_snapshot: Optional[dict[str, Any]] = None

    # Final output
    final_verdict: Verdict = Verdict.ALLOW
    final_reason_code: str = ""
    token_ref: Optional[str] = None

    # Source-chain audit fields
    source_chain_hash: Optional[str] = None
    source_break_tags: tuple[SourceChainBreakTag, ...] = ()
    integrity_signature: Optional[str] = None
    revocation_state: Optional[str] = None

    # Budget trajectory
    budget_before: Optional[dict[str, Any]] = None
    budget_after: Optional[dict[str, Any]] = None
    budget_delta: Optional[dict[str, Any]] = None


# ── 6. Proxy-Authority Budget ────────────────────────────────────────


@dataclass(frozen=True)
class Budget:
    """
    budget governance 代理权预算 — a machine-readable, consumable, transferable,
    revocable budget object that bounds an automated execution
    agent's authority.

    This is the S1 object in the budget governance four-step skeleton:
      Budget → consumption → adjudication → constraint.
    """

    budget_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_now)
    owner_id: str = ""

    # Dimensional quotas (immutable — consumption returns new Budget)
    quotas: dict[str, float] = field(default_factory=dict)
    # Example: {"amount_cny": 5000, "tool_calls": 50, "task_depth": 10,
    #           "data_egress_mb": 100, "autonomy_level": 3}

    # Dynamic state
    consumed: dict[str, float] = field(default_factory=dict)
    status: BudgetStatus = BudgetStatus.ACTIVE

    # Lineage
    parent_budget_ref: Optional[str] = None
    child_budget_refs: tuple[str, ...] = ()

    # Boundary
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    consequence_boundary: dict[str, Any] = field(default_factory=dict)

    # Revocation propagation
    revocation_source: Optional[str] = None
    propagation_depth: int = 0

    @property
    def remaining(self) -> dict[str, float]:
        return {
            dim: self.quotas.get(dim, 0.0) - self.consumed.get(dim, 0.0)
            for dim in self.quotas
        }

    @property
    def is_exhausted(self) -> bool:
        return any(v <= 0 for v in self.remaining.values())

    @property
    def is_expired(self) -> bool:
        if self.time_window_end and _now() > self.time_window_end:
            return True
        return False

    def consume(
        self,
        deductions: dict[str, float],
    ) -> "Budget":
        """Return a new Budget with updated consumed counters."""
        new_consumed = dict(self.consumed)
        for dim, amount in deductions.items():
            new_consumed[dim] = new_consumed.get(dim, 0.0) + amount
        new_status = self.status
        remaining = {
            dim: self.quotas.get(dim, 0.0) - new_consumed.get(dim, 0.0)
            for dim in self.quotas
        }
        if any(v <= 0 for v in remaining.values()):
            new_status = BudgetStatus.CONSTRAINED
        return Budget(
            budget_id=self.budget_id,
            created_at=self.created_at,
            owner_id=self.owner_id,
            quotas=dict(self.quotas),
            consumed=new_consumed,
            status=new_status,
            parent_budget_ref=self.parent_budget_ref,
            child_budget_refs=self.child_budget_refs,
            time_window_start=self.time_window_start,
            time_window_end=self.time_window_end,
            consequence_boundary=dict(self.consequence_boundary),
            revocation_source=self.revocation_source,
            propagation_depth=self.propagation_depth,
        )

    def freeze(self, source: str = "") -> "Budget":
        return Budget(
            **{
                **self.__dict__,
                "status": BudgetStatus.FROZEN,
                "revocation_source": source or self.revocation_source,
            }
        )

    def revoke(self, source: str = "") -> "Budget":
        return Budget(
            **{
                **self.__dict__,
                "status": BudgetStatus.REVOKED,
                "revocation_source": source or self.revocation_source,
            }
        )

    def spawn_child(
        self,
        child_id: str,
        quotas: dict[str, float],
    ) -> "Budget":
        """
        budget governance 子预算继承 — create a constrained child budget.
        The child's quotas MUST be <= parent's remaining.
        """
        for dim, limit in quotas.items():
            if limit > self.remaining.get(dim, 0.0):
                raise ValueError(
                    f"child quota {dim}={limit} exceeds parent remaining "
                    f"{self.remaining.get(dim, 0.0)}"
                )
        return Budget(
            owner_id=child_id,
            quotas=quotas,
            parent_budget_ref=self.budget_id,
            status=BudgetStatus.ACTIVE,
            time_window_start=self.time_window_start,
            time_window_end=self.time_window_end,
        )


# ── 7. Action Constraint ─────────────────────────────────────────────


@dataclass(frozen=True)
class ActionConstraint:
    """
    budget governance S4 输出 — constraints propagated to bound current and
    subsequent action scope after budget adjudication.
    """

    constraint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_ref: str = ""

    block_execution: bool = False
    require_human_review: bool = False
    max_amount: Optional[float] = None
    max_tool_calls: Optional[int] = None
    allowed_tools: tuple[str, ...] = ()
    blocked_tools: tuple[str, ...] = ()
    max_autonomy_level: str = "full"
    downgrade_autonomy: bool = False
    freeze_task_chain: bool = False
    revoke_tool_tokens: bool = False
    isolate_child_agent: bool = False
    reason_code: str = ""
