"""
Tests for Sayfos Preflight — 计划预适配四种策略。

Covers:
  - PlanDeclaration creation
  - Sequential strategy: step-by-step overflow detection
  - Full aggregate strategy: batch comparison
  - Key step strategy: deep-check high-risk, batch-estimate low-risk
  - Risk-weighted strategy: amplify consumption by risk_level
  - Strategy comparison and consistency
  - Integration with SayfosRuntime.preflight_plan()
"""

import pytest

from sayfos.core.models import ActionDeclaration
from sayfos.verification.preflight import (
    PlanDeclaration,
    PreflightEngine,
    PreflightResult,
    PlanVerdict,
    PreflightStrategy,
)
from sayfos.runtime import SayfosRuntime


class TestPlanDeclaration:
    def test_create(self):
        steps = (
            ActionDeclaration(action_type="read", target="f1"),
            ActionDeclaration(action_type="write", target="f2"),
        )
        plan = PlanDeclaration(
            owner_id="agent-1",
            plan_name="test-plan",
            steps=steps,
        )
        assert plan.step_count == 2
        assert plan.plan_id

    def test_empty_plan(self):
        plan = PlanDeclaration(owner_id="agent-1")
        assert plan.step_count == 0


class TestSequentialStrategy:
    def test_all_steps_fit(self):
        engine = PreflightEngine()
        steps = tuple(
            ActionDeclaration(action_type="read") for _ in range(5)
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(plan, {"tool_calls": 10})
        assert result.feasible
        assert result.verdict == PlanVerdict.APPROVE

    def test_overflow_detected(self):
        engine = PreflightEngine()
        steps = tuple(
            ActionDeclaration(
                action_type="payment",
                parameters={"amount": 1000},
            )
            for _ in range(5)
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(plan, {"amount_cny": 3000, "tool_calls": 10})
        assert not result.feasible
        assert result.verdict == PlanVerdict.REJECT
        assert result.first_overflow_step >= 0

    def test_first_overflow_position(self):
        """Should stop at the first step that exceeds budget."""
        engine = PreflightEngine()
        steps = (
            ActionDeclaration(action_type="payment", parameters={"amount": 100}),
            ActionDeclaration(action_type="payment", parameters={"amount": 100}),
            ActionDeclaration(action_type="payment", parameters={"amount": 9999}),
            ActionDeclaration(action_type="payment", parameters={"amount": 1}),
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(plan, {"amount_cny": 200, "tool_calls": 10})
        assert result.first_overflow_step == 2  # 0-indexed

    def test_reason_code_includes_step(self):
        engine = PreflightEngine()
        steps = (
            ActionDeclaration(action_type="payment", parameters={"amount": 9999}),
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(plan, {"amount_cny": 100, "tool_calls": 10})
        assert result.reason_code == "PLAN_BUDGET_OVERFLOW"
        assert "step 0" in result.overflow_detail

    def test_exact_budget_consumed(self):
        engine = PreflightEngine()
        steps = (
            ActionDeclaration(action_type="payment", parameters={"amount": 1000}),
            ActionDeclaration(action_type="read"),
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(plan, {"amount_cny": 1000, "tool_calls": 10})
        assert result.feasible
        assert result.budget_remaining_after["amount_cny"] == 0.0


class TestFullAggregateStrategy:
    def test_batch_comparison(self):
        engine = PreflightEngine()
        steps = tuple(
            ActionDeclaration(action_type="payment", parameters={"amount": 500})
            for _ in range(10)
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(
            plan,
            {"amount_cny": 6000, "tool_calls": 100},
            PreflightStrategy.FULL_AGGREGATE,
        )
        assert result.feasible

    def test_batch_overflow(self):
        engine = PreflightEngine()
        steps = tuple(
            ActionDeclaration(action_type="payment", parameters={"amount": 500})
            for _ in range(10)
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(
            plan,
            {"amount_cny": 4000, "tool_calls": 100},
            PreflightStrategy.FULL_AGGREGATE,
        )
        assert not result.feasible


class TestKeyStepStrategy:
    def test_high_risk_steps_checked(self):
        engine = PreflightEngine()
        steps = (
            ActionDeclaration(action_type="read"),
            ActionDeclaration(action_type="read"),
            ActionDeclaration(action_type="payment", parameters={"amount": 9999}),
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(
            plan,
            {"amount_cny": 10000, "tool_calls": 100},
            PreflightStrategy.KEY_STEP,
        )
        assert result.feasible

    def test_key_step_overflow(self):
        engine = PreflightEngine()
        steps = (
            ActionDeclaration(action_type="read"),
            ActionDeclaration(action_type="payment", parameters={"amount": 9999}),
        )
        plan = PlanDeclaration(steps=steps)
        result = engine.adapt(
            plan,
            {"amount_cny": 100, "tool_calls": 10},
            PreflightStrategy.KEY_STEP,
        )
        assert not result.feasible
        assert result.first_overflow_step == 1


class TestRiskWeightedStrategy:
    def test_high_risk_amplified(self):
        engine = PreflightEngine()
        low_risk = ActionDeclaration(
            action_type="payment",
            parameters={"amount": 500},
            risk_level=0,
        )
        high_risk = ActionDeclaration(
            action_type="payment",
            parameters={"amount": 500},
            risk_level=9,
        )
        plan = PlanDeclaration(steps=(low_risk, high_risk))

        # Budget may be enough for normal but not for risk-weighted
        result = engine.adapt(
            plan,
            {"amount_cny": 3000, "tool_calls": 10},
            PreflightStrategy.RISK_WEIGHTED,
        )
        assert result.feasible

    def test_risk_weighted_overflow(self):
        engine = PreflightEngine()
        high_risk = ActionDeclaration(
            action_type="payment",
            parameters={"amount": 500},
            risk_level=9,
        )
        plan = PlanDeclaration(steps=(high_risk,))
        # risk_level 9 → weight = 1.0 + 9*0.3 = 3.7 → 500*3.7 = 1850
        result = engine.adapt(
            plan,
            {"amount_cny": 1000, "tool_calls": 10},
            PreflightStrategy.RISK_WEIGHTED,
        )
        assert not result.feasible


class TestRuntimeIntegration:
    def test_preflight_plan_with_runtime(self):
        rt = SayfosRuntime()
        budget = rt.create_budget(
            owner_id="agent-1",
            quotas={"amount_cny": 5000, "tool_calls": 20},
        )
        steps = tuple(
            ActionDeclaration(action_type="payment", parameters={"amount": 1000})
            for _ in range(4)
        )
        plan = PlanDeclaration(steps=steps)
        result = rt.preflight_plan(plan, budget.budget_id)
        assert result.feasible
        assert result.verdict == PlanVerdict.APPROVE

    def test_preflight_rejects_over_budget_plan(self):
        rt = SayfosRuntime()
        budget = rt.create_budget(
            owner_id="agent-1",
            quotas={"amount_cny": 1000, "tool_calls": 5},
        )
        steps = tuple(
            ActionDeclaration(action_type="payment", parameters={"amount": 1000})
            for _ in range(10)
        )
        plan = PlanDeclaration(steps=steps)
        result = rt.preflight_plan(plan, budget.budget_id)
        assert not result.feasible
        assert result.first_overflow_step >= 0

    def test_preflight_missing_budget(self):
        rt = SayfosRuntime()
        steps = (ActionDeclaration(action_type="read"),)
        plan = PlanDeclaration(steps=steps)
        result = rt.preflight_plan(plan, "nonexistent")
        assert not result.feasible
        assert result.reason_code == "BUDGET_NOT_FOUND"