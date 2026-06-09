"""
Tests for Sayfos five-object protocol conformance.

Verify that all five standard objects are:
  - Frozen (immutable after creation)
  - Hashable
  - Have deterministic content_hash / token_hash
"""

import pytest

from sayfos.core.models import (
    ActionDeclaration,
    AdjudicationToken,
    AuditSummary,
    EmbodiedResponse,
    IntentVerificationRequest,
)
from sayfos.core.enums import Verdict


class TestActionDeclaration:
    def test_immutable(self):
        a = ActionDeclaration(action_type="payment", target="acct_123")
        with pytest.raises(Exception):
            a.action_type = "transfer"  # type: ignore[misc]

    def test_hashable(self):
        a = ActionDeclaration()
        assert hash(a) is not None
        {a: "test"}

    def test_content_hash_deterministic(self):
        a1 = ActionDeclaration(action_type="payment", target="acct_123", risk_level=5)
        a2 = ActionDeclaration(action_type="payment", target="acct_123", risk_level=5)
        assert a1.content_hash() == a2.content_hash()

    def test_content_hash_differs(self):
        a1 = ActionDeclaration(action_type="payment")
        a2 = ActionDeclaration(action_type="transfer")
        assert a1.content_hash() != a2.content_hash()

    def test_content_hash_chains(self):
        """previous_content_hash changes the content hash."""
        d1 = ActionDeclaration(action_type="read")
        h1 = d1.content_hash()
        d2 = ActionDeclaration(action_type="read", previous_content_hash=h1)
        h2 = d2.content_hash()
        d3 = ActionDeclaration(action_type="read")
        h3 = d3.content_hash()
        assert h2 != h3
        assert h1 != h2

    def test_to_chain_entry(self):
        decl = ActionDeclaration(
            action_type="payment",
            actor_id="agent-1",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://1",
            budget_state_ref="budget://preflight",
        )
        entry = decl.to_chain_entry()
        assert entry.action_ref == decl.action_id
        assert entry.action_type == "payment"
        assert entry.authorization_ref == "auth://alice"
        assert entry.budget_state_ref == "budget://preflight"

    def test_defaults(self):
        a = ActionDeclaration()
        assert a.action_id
        assert a.timestamp
        assert a.risk_level == 0
        assert a.parameters == {}


class TestAdjudicationToken:
    def test_default_verdict_is_allow(self):
        t = AdjudicationToken()
        assert t.verdict == Verdict.ALLOW

    def test_token_hash_deterministic(self):
        t1 = AdjudicationToken(
            action_ref="act-1",
            verdict=Verdict.BLOCK,
            reason_code="CAUSAL_BREAK",
            embodied_consistency_score=0.0,
        )
        t2 = AdjudicationToken(
            action_ref="act-1",
            verdict=Verdict.BLOCK,
            reason_code="CAUSAL_BREAK",
            embodied_consistency_score=0.0,
        )
        assert t1.token_hash() == t2.token_hash()


class TestAuditSummary:
    def test_defaults(self):
        s = AuditSummary()
        assert s.summary_id
        assert s.recorded_at
        assert s.final_verdict == Verdict.ALLOW


class TestIntentVerificationRequest:
    def test_carries_action(self):
        a = ActionDeclaration(action_type="deploy")
        r = IntentVerificationRequest(action=a)
        assert r.action.action_type == "deploy"

    def test_default_budget_status(self):
        r = IntentVerificationRequest()
        assert r.budget_status.value == "active"


class TestEmbodiedResponse:
    def test_default_consistency(self):
        r = EmbodiedResponse()
        assert r.causal_consistency_score == 1.0
        assert not r.break_detected

    def test_break_state(self):
        r = EmbodiedResponse(
            causal_consistency_score=0.0,
            break_detected=True,
            break_reason="no_physical_interaction",
        )
        assert r.break_detected
        assert r.causal_consistency_score == 0.0