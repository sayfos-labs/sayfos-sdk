"""
Tests for Sayfos verification pipeline with budget governance and
constraint propagation (budget governance four-step skeleton).
"""

import pytest

from sayfos.core.models import ActionDeclaration, Budget, IntentVerificationRequest
from sayfos.core.enums import BudgetStatus, Verdict
from sayfos.verification.pipeline import SayfosPipeline


class TestBudgetModel:
    def test_create(self):
        b = Budget(owner_id="agent-1", quotas={"amount_cny": 5000, "tool_calls": 50})
        assert b.status == BudgetStatus.ACTIVE
        assert b.remaining == {"amount_cny": 5000.0, "tool_calls": 50.0}
        assert not b.is_exhausted

    def test_consume_immutable(self):
        budget = Budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        b2 = budget.consume({"amount_cny": 1000})
        assert budget.remaining["amount_cny"] == 5000.0
        assert b2.remaining["amount_cny"] == 4000.0
        assert b2.consumed["amount_cny"] == 1000.0
        assert budget is not b2

    def test_consume_exhausted(self):
        b = Budget(owner_id="agent-1", quotas={"amount_cny": 100})
        b = b.consume({"amount_cny": 100})
        assert b.remaining["amount_cny"] == 0.0
        assert b.is_exhausted
        assert b.status == BudgetStatus.CONSTRAINED

    def test_freeze(self):
        b = Budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        b = b.freeze("parent_revoked")
        assert b.status == BudgetStatus.FROZEN
        assert b.revocation_source == "parent_revoked"

    def test_revoke(self):
        b = Budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        b = b.revoke("user_revoked")
        assert b.status == BudgetStatus.REVOKED

    def test_spawn_child(self):
        parent = Budget(owner_id="parent", quotas={"amount_cny": 5000, "tool_calls": 50})
        parent = parent.consume({"amount_cny": 1000})
        child = parent.spawn_child("child-1", {"amount_cny": 2000, "tool_calls": 20})
        assert child.parent_budget_ref == parent.budget_id
        assert child.owner_id == "child-1"
        assert child.remaining["amount_cny"] == 2000.0

    def test_spawn_child_exceeds_parent(self):
        parent = Budget(owner_id="parent", quotas={"amount_cny": 1000})
        with pytest.raises(ValueError):
            parent.spawn_child("child-1", {"amount_cny": 2000})


class TestPipelineWithBudget:
    def test_allow_with_sufficient_budget(self):
        decl = ActionDeclaration(action_type="read", target="config.json")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000, "tool_calls": 50},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.ALLOW

    def test_allow_with_constraints_low_budget(self):
        """Budget low but not exhausted → allowed with constraints."""
        decl = ActionDeclaration(action_type="payment", target="acct_123")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 50, "tool_calls": 50},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.ALLOW_WITH_CONSTRAINTS
        assert "BUDGET_LOW" in token.reason_code

    def test_block_budget_exhausted(self):
        decl = ActionDeclaration(action_type="payment")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 0, "tool_calls": 0},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.BLOCK
        assert "BUDGET_EXHAUSTED" in token.reason_code

    def test_block_budget_revoked(self):
        decl = ActionDeclaration(action_type="read")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_status=BudgetStatus.REVOKED,
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.BLOCK

    def test_block_budget_frozen(self):
        decl = ActionDeclaration(action_type="read")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_status=BudgetStatus.FROZEN,
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.BLOCK

    def test_block_causal_takes_priority(self):
        """Causal break should block even if budget is sufficient."""
        decl = ActionDeclaration(action_type="read")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=0,
            key_events=0,
            screen_on=False,
            device_held=False,
            budget_remaining={"amount_cny": 99999, "tool_calls": 999},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.BLOCK
        assert "CAUSAL_BREAK" in token.reason_code

    def test_source_chain_human_review(self):
        """Missing source chain on high-risk action → human review."""
        decl = ActionDeclaration(action_type="payment", target="acct_123")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.HUMAN_REVIEW
        assert "SOURCE_CHAIN" in token.reason_code

    def test_constraint_propagation(self):
        """Blocked action should carry constraints in the token."""
        decl = ActionDeclaration(action_type="transfer", target="acct_evil")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=0,
            screen_on=False,
            device_held=False,
            remote_control_detected=True,
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.BLOCK
        assert token.constraints  # constraints dict should not be empty
        assert token.constraints.get("block_execution") is True

    def test_evaluate_and_audit_with_budget(self):
        decl = ActionDeclaration(action_type="read", target="config.json")
        req = IntentVerificationRequest(
            action=decl,
            touch_events=1,
            screen_on=True,
            budget_remaining={"amount_cny": 5000},
        )
        token, summary = SayfosPipeline().evaluate_and_audit(req)
        assert token.verdict == Verdict.ALLOW
        assert summary.action_ref == decl.action_id
        assert summary.token_ref == token.token_id

    def test_budget_deduction_in_token(self):
        """Token should carry estimated budget deductions."""
        decl = ActionDeclaration(
            action_type="payment",
            target="acct_123",
            parameters={"amount": 150.0},
        )
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000, "tool_calls": 50},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.budget_deduction
        assert token.budget_deduction.get("amount_cny") == 150.0
        assert token.budget_deduction.get("tool_calls") == 1.0