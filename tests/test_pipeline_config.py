"""
Tests for configurable pipeline and engine registry.
"""

import pytest

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.enums import Verdict
from sayfos.verification.engines import (
    BaseVerifier,
    VerificationResult,
)
from sayfos.verification.pipeline import ConfigurablePipeline, EngineRegistry
from sayfos.config import DecisionPolicy, PipelineConfig


class AlwaysPassVerifier(BaseVerifier):
    def verify(self, request):
        return VerificationResult(passed=True, score=1.0, reason_code="PASS")


class AlwaysBlockVerifier(BaseVerifier):
    def verify(self, request):
        return VerificationResult(passed=False, score=0.0, reason_code="BLOCK")


class TestEngineRegistry:
    def test_builtin_engines(self):
        reg = EngineRegistry()
        assert reg.get("causal_consistency") is not None
        assert reg.get("budget_governance") is not None
        assert reg.get("source_chain") is not None

    def test_register_custom(self):
        reg = EngineRegistry()
        reg.register("my_pass", AlwaysPassVerifier())
        engine = reg.get("my_pass")
        assert engine is not None
        assert isinstance(engine, AlwaysPassVerifier)

    def test_unknown_returns_none(self):
        reg = EngineRegistry()
        assert reg.get("nonexistent") is None

    def test_get_all_filters_unknown(self):
        reg = EngineRegistry()
        engines = reg.get_all(("causal_consistency", "nonexistent"))
        assert len(engines) == 1


class TestConfigurablePipeline:
    def _request(self):
        decl = ActionDeclaration(
            action_type="read",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://1",
        )
        return IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000},
        )

    def test_default_balanced(self):
        pipe = ConfigurablePipeline()
        token = pipe.evaluate(self._request())
        assert token.verdict == Verdict.ALLOW

    def test_strict_policy_blocks_on_source_fail(self):
        config = PipelineConfig.strict()
        pipe = ConfigurablePipeline(config=config)
        # source chain is incomplete → strict should block
        decl = ActionDeclaration(action_type="read")  # no auth/task refs
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
        )
        token = pipe.evaluate(req)
        assert token.verdict == Verdict.BLOCK

    def test_permissive_allows_with_constraints(self):
        config = PipelineConfig.permissive()
        pipe = ConfigurablePipeline(config=config)
        decl = ActionDeclaration(action_type="read")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={},  # no budget info → budget gov may not block
        )
        token = pipe.evaluate(req)
        # With permissive, source chain fail → ALLOW_WITH_CONSTRAINTS
        assert token.verdict in (Verdict.ALLOW, Verdict.ALLOW_WITH_CONSTRAINTS)

    def test_custom_engine_in_pipeline(self):
        reg = EngineRegistry()
        reg.register("always_pass", AlwaysPassVerifier())

        config = PipelineConfig(
            engines=("always_pass",),
            policy=DecisionPolicy.STRICT,
        )
        pipe = ConfigurablePipeline(registry=reg, config=config)
        token = pipe.evaluate(self._request())
        assert token.verdict == Verdict.ALLOW

    def test_custom_decision_matrix(self):
        config = PipelineConfig.from_dict({
            "policy": "balanced",
            "custom_matrix": {
                # (causal_pass, budget_pass, source_pass) → verdict
                "1|1|1": "allow",         # all pass → allow
                "1|1|0": "allow_with_constraints",  # source fail → constraints
                "0|1|1": "block",          # causal fail → block
            },
        })
        pipe = ConfigurablePipeline(config=config)
        token = pipe.evaluate(self._request())
        assert token.verdict == Verdict.ALLOW

    def test_engine_ordering(self):
        """Custom engine ordering should work."""
        config = PipelineConfig(
            engines=("source_chain", "budget_governance", "causal_consistency"),
        )
        pipe = ConfigurablePipeline(config=config)
        token = pipe.evaluate(self._request())
        assert token.verdict in (Verdict.ALLOW, Verdict.HUMAN_REVIEW)

    def test_production_config(self):
        config = PipelineConfig.production()
        pipe = ConfigurablePipeline(config=config)
        token = pipe.evaluate(self._request())
        assert token.verdict == Verdict.ALLOW