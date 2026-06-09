"""
Sayfos Protocol — Unified runtime.

SayfosRuntime combines the Sayfos pipeline, budget manager, and
source chain into a single end-to-end workflow.  This is the
primary entry-point for production use.

Usage::

    runtime = SayfosRuntime()
    runtime.create_budget(owner="agent-1", quotas={"amount_cny": 5000})

    decl = ActionDeclaration(action_type="payment", ...)
    request = IntentVerificationRequest(action=decl, ...)
    token = runtime.adjudicate(request, budget_id=budget.budget_id)

    if token.verdict != Verdict.ALLOW:
        ...
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sayfos.core.models import (
    ActionDeclaration,
    AdjudicationToken,
    AuditSummary,
    Budget,
    IntentVerificationRequest,
)
from sayfos.core.chain import ChainEntry, SourceChain
from sayfos.core.enums import Verdict
from sayfos.verification.pipeline import ConfigurablePipeline, SayfosPipeline, EngineRegistry
from sayfos.verification.preflight import (
    ExecutionBoundary,
    PreflightEngine,
    PreflightPlan,
    PreflightResult,
    PreflightStrategy,
    PreflightVerdict,
    PlanDeclaration,
    PlanVerdict,
)
from sayfos.budget import BudgetManager, BudgetStore, InMemoryBudgetStore
from sayfos.config import PipelineConfig


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SayfosRuntime:
    """
    Unified Sayfos runtime combining pipeline, budget, and chain.

    This is the recommended entry-point for SDK consumers.
    Handles budget auto-consumption, chain auto-linking,
    and audit trail recording.
    """

    def __init__(
        self,
        store: Optional[BudgetStore] = None,
        pipeline: Optional[ConfigurablePipeline] = None,
        config: Optional[PipelineConfig] = None,
        registry: Optional[EngineRegistry] = None,
    ):
        self.store = store or InMemoryBudgetStore()
        self.budgets = BudgetManager(self.store)
        self.registry = registry or EngineRegistry()
        self.config = config or PipelineConfig()
        self.pipeline = pipeline or ConfigurablePipeline(
            registry=self.registry,
            config=self.config,
        )
        self._chains: dict[str, SourceChain] = {}

    # ── Budget operations ──────────────────────────────────────

    def create_budget(
        self,
        owner_id: str,
        quotas: dict[str, float],
        parent_id: Optional[str] = None,
    ) -> Budget:
        return self.budgets.create_budget(owner_id, quotas, parent_id)

    def get_budget(self, budget_id: str) -> Optional[Budget]:
        return self.store.get(budget_id)

    def revoke_budget(
        self,
        budget_id: str,
        source: str = "",
        propagate: bool = True,
    ) -> list[Budget]:
        return self.budgets.revoke(budget_id, source, propagate)

    # ── Plan preflight ────────────────────────────────────────

    def preflight(
        self,
        plan: PreflightPlan,
        boundary: ExecutionBoundary,
        strategy: PreflightStrategy = PreflightStrategy.SEQUENTIAL,
    ) -> PreflightResult:
        """
        Run plan preflight before any step is executed.

        1. S1: 计划 + 边界约束已由调用方构建
        2. S2: 引擎执行步骤级边界预验真
        3. S3: 返回含裁决的预验真结果
        """
        engine = PreflightEngine()
        return engine.preflight(plan, boundary, strategy)

    def preflight_plan(
        self,
        plan: PreflightPlan,
        budget_id: str,
        strategy: PreflightStrategy = PreflightStrategy.SEQUENTIAL,
    ) -> PreflightResult:
        """向后兼容：从预算ID构建边界约束后执行预验真。"""
        budget = self.store.get(budget_id)
        if not budget:
            return PreflightResult(
                plan_id=plan.plan_id,
                feasible=False,
                score=0.0,
                reason_code="BUDGET_NOT_FOUND",
                verdict=PreflightVerdict.REJECT,
            )
        boundary = ExecutionBoundary.budget_only(budget.remaining)
        return self.preflight(plan, boundary, strategy)

    # ── Adjudication ───────────────────────────────────────────

    def adjudicate(
        self,
        request: IntentVerificationRequest,
        budget_id: Optional[str] = None,
        chain_id: Optional[str] = None,
    ) -> AdjudicationToken:
        """
        Run the full Sayfos pipeline against a request.

        If budget_id is provided, the budget's remaining state is
        injected into the request before verification.  On ALLOW /
        ALLOW_WITH_CONSTRAINTS, the budget is auto-consumed based
        on the estimated deductions in the token.

        If chain_id is provided, the action is appended to the
        source chain with hash linking.
        """
        # Inject budget snapshot
        if budget_id:
            budget = self.store.get(budget_id)
            if budget:
                request = IntentVerificationRequest(
                    **{
                        **request.__dict__,
                        "budget_remaining": budget.remaining,
                        "budget_status": budget.status,
                    }
                )

        # Run pipeline
        token = self.pipeline.evaluate(request)

        # Auto-consume budget on non-block verdicts
        if budget_id and token.verdict not in (Verdict.BLOCK,):
            deductions = token.budget_deduction or {}
            if deductions:
                self.budgets.consume(budget_id, deductions)
                token = AdjudicationToken(
                    **{**token.__dict__, "budget_deduction_applied": True}
                )

        # Append to source chain
        if chain_id:
            entry = request.action.to_chain_entry()
            if token.verdict != Verdict.ALLOW:
                entry = ChainEntry(
                    **{
                        **entry.__dict__,
                        "break_tags": token.source_chain_break_tags,
                    }
                )
            self._append_to_chain(chain_id, entry)

        return token

    def adjudicate_and_audit(
        self,
        request: IntentVerificationRequest,
        budget_id: Optional[str] = None,
        chain_id: Optional[str] = None,
    ) -> tuple[AdjudicationToken, AuditSummary]:
        token = self.adjudicate(request, budget_id, chain_id)
        summary = self.pipeline._build_audit(request, token)
        return token, summary

    # ── Source chain operations ─────────────────────────────────

    def create_chain(self, chain_id: Optional[str] = None) -> str:
        chain = SourceChain()
        cid = chain_id or chain.chain_id
        self._chains[cid] = chain
        return cid

    def get_chain(self, chain_id: str) -> Optional[SourceChain]:
        return self._chains.get(chain_id)

    def verify_chain(self, chain_id: str):
        chain = self._chains.get(chain_id)
        if not chain:
            return None
        return chain.verify()

    def _append_to_chain(self, chain_id: str, entry: ChainEntry) -> None:
        chain = self._chains.get(chain_id)
        if chain:
            self._chains[chain_id] = chain.append(entry)
        else:
            entry = ChainEntry(
                **{**entry.__dict__, "entry_hash": entry.compute_entry_hash()}
            )
            self._chains[chain_id] = SourceChain([entry])
