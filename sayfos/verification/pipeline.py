"""
Sayfos Protocol — Pipeline orchestrator (configurable).

Supports:
  - Pluggable verifier engines via EngineRegistry
  - Configurable decision matrix (strict / balanced / permissive / custom)
  - Per-verifier thresholds
  - Custom engine ordering
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sayfos.core.models import (
    ActionConstraint,
    ActionDeclaration,
    AdjudicationToken,
    AuditSummary,
    Budget,
    IntentVerificationRequest,
)
from sayfos.core.enums import SourceChainBreakTag, Verdict
from sayfos.config import (
    DecisionPolicy,
    POLICY_MATRIX,
    PipelineConfig,
    VerifierThresholds,
)
from sayfos.verification.engines import (
    BaseVerifier,
    BudgetGovernanceVerifier,
    CausalConsistencyVerifier,
    SourceChainVerifier,
    VerificationResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Engine Registry ──────────────────────────────────────────────────


class EngineRegistry:
    """
    Pluggable verifier engine registry.

    Built-in engines: causal_consistency, budget_governance, source_chain.

    Usage::

        registry = EngineRegistry()
        registry.register("my_custom", MyVerifier())
        pipeline = SayfosPipeline(registry=registry, config=...)
    """

    _defaults: dict[str, type[BaseVerifier]] = {
        "causal_consistency": CausalConsistencyVerifier,
        "budget_governance": BudgetGovernanceVerifier,
        "source_chain": SourceChainVerifier,
    }

    def __init__(self):
        self._instances: dict[str, BaseVerifier] = {}

    def register(self, name: str, verifier: BaseVerifier) -> None:
        self._instances[name] = verifier

    def get(self, name: str) -> Optional[BaseVerifier]:
        if name in self._instances:
            return self._instances[name]
        if name in self._defaults:
            instance = self._defaults[name]()
            self._instances[name] = instance
            return instance
        return None

    def get_all(self, names: tuple[str, ...]) -> list[BaseVerifier]:
        engines: list[BaseVerifier] = []
        for name in names:
            engine = self.get(name)
            if engine:
                engines.append(engine)
        return engines

    def clear(self) -> None:
        self._instances.clear()


# ── Configurable Pipeline ────────────────────────────────────────────


class ConfigurablePipeline:
    """
    Fully configurable Sayfos pipeline.

    Usage::

        config = PipelineConfig.balanced()
        pipeline = ConfigurablePipeline(config=config)
        token = pipeline.evaluate(request)

        # Custom engine
        registry = EngineRegistry()
        registry.register("custom_risk", MyRiskVerifier())
        pipeline = ConfigurablePipeline(
            registry=registry,
            config=PipelineConfig(engines=("causal_consistency", "custom_risk")),
        )
    """

    def __init__(
        self,
        registry: Optional[EngineRegistry] = None,
        config: Optional[PipelineConfig] = None,
    ):
        self.registry = registry or EngineRegistry()
        self.config = config or PipelineConfig()

    def evaluate(
        self,
        request: IntentVerificationRequest,
    ) -> AdjudicationToken:
        engines = self.registry.get_all(self.config.engines)

        # Run all configured engines
        results: dict[str, VerificationResult] = {}
        for i, engine in enumerate(engines):
            name = self.config.engines[i]
            results[name] = engine.verify(request)

        # Get key results
        causal = results.get("causal_consistency")
        budget = results.get("budget_governance")
        source = results.get("source_chain")

        # Determine verdict via decision matrix
        verdict = self._resolve_verdict(
            causal, budget, source,
        )

        # Collect constraints
        constraints = self._collect_constraints(results)
        if constraints.get("block_execution"):
            verdict = Verdict.BLOCK
        elif budget and budget.reason_code == "BUDGET_LOW":
            verdict = Verdict.ALLOW_WITH_CONSTRAINTS

        # Build token
        return AdjudicationToken(
            issued_at=_now(),
            action_ref=request.action.action_id,
            verdict=verdict,
            reason_code=self._build_reason_code(results),
            reason_detail=self._build_detail(results),
            intent_consistency_score=1.0,
            embodied_consistency_score=causal.score if causal else 1.0,
            budget_adequacy_score=budget.score if budget else 1.0,
            source_chain_integrity_score=source.score if source else 1.0,
            constraints=constraints,
            budget_deduction=self._deductions_from_action(request.action),
            budget_deduction_applied=False,
            source_chain_break_tags=tuple(
                SourceChainBreakTag(t)
                for t in (source.metadata.get("break_tags", []) if source else [])
                if isinstance(t, str)
            ),
        )

    def evaluate_and_audit(
        self,
        request: IntentVerificationRequest,
    ) -> tuple[AdjudicationToken, AuditSummary]:
        token = self.evaluate(request)
        summary = self._build_audit(request, token)
        updated = AdjudicationToken(
            **{**token.__dict__, "audit_summary_ref": summary.summary_id}
        )
        return updated, summary

    # ── decision logic ──────────────────────────────────────────

    def _resolve_verdict(
        self,
        causal: Optional[VerificationResult],
        budget: Optional[VerificationResult],
        source: Optional[VerificationResult],
    ) -> Verdict:
        t = self.config.thresholds

        causal_pass = causal.passed if causal else True
        budget_pass = budget.passed if budget else True
        source_pass = source.passed if source else True
        if (
            self.config.policy == DecisionPolicy.STRICT
            and source
            and source.metadata.get("break_tags")
        ):
            source_pass = False

        # Check custom matrix first
        key = f"{int(causal_pass)}|{int(budget_pass)}|{int(source_pass)}"
        if key in self.config.custom_matrix:
            return self.config.custom_matrix[key]

        matrix = POLICY_MATRIX.get(
            self.config.policy,
            POLICY_MATRIX[DecisionPolicy.BALANCED],
        )
        return matrix.get(
            (causal_pass, budget_pass, source_pass),
            Verdict.BLOCK,
        )

    @staticmethod
    def _collect_constraints(
        results: dict[str, VerificationResult],
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "block_execution": False,
            "require_human_review": False,
            "downgrade_autonomy": False,
            "freeze_task_chain": False,
            "revoke_tool_tokens": False,
            "reasons": [],
        }
        for r in results.values():
            for c in r.constraints:
                if c.block_execution:
                    merged["block_execution"] = True
                if c.require_human_review:
                    merged["require_human_review"] = True
                if c.downgrade_autonomy:
                    merged["downgrade_autonomy"] = True
                if c.freeze_task_chain:
                    merged["freeze_task_chain"] = True
                if c.revoke_tool_tokens:
                    merged["revoke_tool_tokens"] = True
                if c.reason_code:
                    merged["reasons"].append(c.reason_code)
        return merged

    @staticmethod
    def _build_reason_code(
        results: dict[str, VerificationResult],
    ) -> str:
        codes = [
            r.reason_code
            for r in results.values()
            if r.reason_code and r.reason_code != "ALL_CLEAR"
        ]
        return "+".join(codes) if codes else "ALL_CLEAR"

    @staticmethod
    def _build_detail(
        results: dict[str, VerificationResult],
    ) -> str:
        parts = [
            f"{name}={r.detail}"
            for name, r in results.items()
            if r.detail and r.detail != "ok"
        ]
        return "; ".join(parts) if parts else "ok"

    @staticmethod
    def _build_audit(
        request: IntentVerificationRequest,
        token: AdjudicationToken,
    ) -> AuditSummary:
        return AuditSummary(
            recorded_at=_now(),
            action_ref=request.action.action_id,
            actor_id=request.action.actor_id,
            action_snapshot={
                "action_type": request.action.action_type,
                "target": request.action.target,
                "parameters": request.action.parameters,
            },
            final_verdict=token.verdict,
            final_reason_code=token.reason_code,
            token_ref=token.token_id,
            source_break_tags=token.source_chain_break_tags,
            budget_delta=token.budget_deduction,
        )

    @staticmethod
    def _deductions_from_action(
        action: ActionDeclaration,
    ) -> dict[str, float]:
        deductions: dict[str, float] = {}
        params = action.parameters
        if action.action_type in ("payment", "transfer"):
            deductions["amount_cny"] = float(params.get("amount", 0))
        deductions["tool_calls"] = 1.0
        return deductions


# ── Convenience pipeline ─────────────────────────────────────────────


class SayfosPipeline(ConfigurablePipeline):
    """Convenience pipeline with default BALANCED config."""

    def __init__(self):
        super().__init__(config=PipelineConfig())
