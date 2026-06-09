"""
Tests for Sayfos source chain — hash-chain integrity, tamper detection,
and verifiable provenance (source-chain integrity).

Verifies:
  - ChainEntry hash computation
  - SourceChain append + hash linking
  - Chain verification (valid chain)
  - Tamper detection (modified entry, broken link, reordered entries)
  - Serialization round-trip
  - ActionDeclaration → ChainEntry conversion
  - Integration with SourceChainVerifier
"""

import pytest

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.chain import (
    ChainBreak,
    ChainEntry,
    ChainVerification,
    SourceChain,
)
from sayfos.core.enums import SourceChainBreakTag, Verdict
from sayfos.verification.engines import SourceChainVerifier
from sayfos.verification.pipeline import SayfosPipeline


class TestChainEntry:
    def test_create(self):
        e = ChainEntry(
            action_ref="act-1",
            action_type="payment",
            actor_id="agent-1",
            authorization_ref="auth://alice",
        )
        assert e.entry_id
        assert e.timestamp
        assert e.action_ref == "act-1"

    def test_hash_deterministic(self):
        e1 = ChainEntry(
            action_ref="act-1",
            action_type="payment",
            actor_id="agent-1",
        )
        e2 = ChainEntry(
            action_ref="act-1",
            action_type="payment",
            actor_id="agent-1",
        )
        assert e1.compute_entry_hash() == e2.compute_entry_hash()

    def test_hash_depends_on_previous(self):
        e1 = ChainEntry(action_ref="act-1", action_type="read")
        e2 = ChainEntry(
            action_ref="act-1",
            action_type="read",
            previous_entry_hash="abc123",
        )
        e3 = ChainEntry(
            action_ref="act-1",
            action_type="read",
            previous_entry_hash="xyz789",
        )
        assert e2.compute_entry_hash() != e3.compute_entry_hash()

    def test_hash_differs_by_position(self):
        e1 = ChainEntry(action_ref="act-1", action_type="read", chain_position=0)
        e2 = ChainEntry(action_ref="act-1", action_type="read", chain_position=5)
        assert e1.compute_entry_hash() != e2.compute_entry_hash()


class TestSourceChainBasic:
    def test_empty_chain(self):
        c = SourceChain()
        assert c.length == 0
        assert c.last_entry is None
        result = c.verify()
        assert not result.valid

    def test_single_entry(self):
        e = ChainEntry(action_ref="act-1", action_type="read", actor_id="agent-1")
        # Manually set entry_hash with correct position
        e = ChainEntry(**{**e.__dict__, "entry_hash": e.compute_entry_hash()})
        c = SourceChain([e])
        assert c.length == 1
        result = c.verify()
        assert result.valid
        assert len(result.breaks) == 0

    def test_append_links_hashes(self):
        """Append() should automatically link previous_entry_hash."""
        e1 = ChainEntry(action_ref="act-1", action_type="read")
        e1 = ChainEntry(**{**e1.__dict__, "entry_hash": e1.compute_entry_hash()})

        c = SourceChain([e1])

        e2 = ChainEntry(action_ref="act-2", action_type="write")
        c2 = c.append(e2)

        assert c2.length == 2
        assert c2.entries[1].previous_entry_hash == c2.entries[0].entry_hash
        assert c2.entries[1].entry_hash == c2.entries[1].compute_entry_hash()

    def test_multi_entry_chain(self):
        e1 = ChainEntry(action_ref="act-1", action_type="read")
        e1 = ChainEntry(**{**e1.__dict__, "entry_hash": e1.compute_entry_hash()})
        c = SourceChain([e1])

        for i in range(2, 6):
            e = ChainEntry(action_ref=f"act-{i}", action_type="read")
            c = c.append(e)

        assert c.length == 5
        result = c.verify()
        assert result.valid

    def test_chain_hash_changes_on_append(self):
        e1 = ChainEntry(action_ref="act-1", action_type="read")
        e1 = ChainEntry(**{**e1.__dict__, "entry_hash": e1.compute_entry_hash()})
        c = SourceChain([e1])
        h1 = c.chain_hash

        e2 = ChainEntry(action_ref="act-2", action_type="write")
        c = c.append(e2)
        h2 = c.chain_hash

        assert h1 != h2

    def test_immutable_append(self):
        """Append returns new chain; original is unchanged."""
        e1 = ChainEntry(action_ref="act-1", action_type="read")
        e1 = ChainEntry(**{**e1.__dict__, "entry_hash": e1.compute_entry_hash()})
        c1 = SourceChain([e1])

        e2 = ChainEntry(action_ref="act-2", action_type="write")
        c2 = c1.append(e2)

        assert c1.length == 1
        assert c2.length == 2
        assert c1 is not c2


class TestTamperDetection:
    def _build_chain(self, n: int = 3) -> SourceChain:
        e = ChainEntry(action_ref="act-1", action_type="read")
        e = ChainEntry(**{**e.__dict__, "entry_hash": e.compute_entry_hash()})
        c = SourceChain([e])
        for i in range(2, n + 1):
            e = ChainEntry(action_ref=f"act-{i}", action_type="read")
            c = c.append(e)
        return c

    def test_valid_chain_passes(self):
        c = self._build_chain(5)
        result = c.verify()
        assert result.valid
        assert len(result.breaks) == 0

    def test_tampered_content_detected(self):
        """Modifying an entry's content should break the chain."""
        c = self._build_chain(3)

        # Tamper: change action_ref of entry 1 without updating hash
        entries = list(c.entries)
        tampered = ChainEntry(
            **{**entries[1].__dict__, "action_ref": "evil-action"}
        )
        entries[1] = tampered
        tampered_chain = SourceChain(entries)

        result = tampered_chain.verify()
        assert not result.valid
        assert any(
            b.position == 1 and b.tag == SourceChainBreakTag.CHAIN_HASH_MISMATCH
            for b in result.breaks
        )

    def test_broken_link_detected(self):
        """Removing the middle link should break continuity."""
        c = self._build_chain(3)

        # Remove entry at position 1
        entries = (c.entries[0], c.entries[2])
        broken_chain = SourceChain(entries)

        result = broken_chain.verify()

        # Entry at new position 1 should fail because its
        # previous_entry_hash still points to the removed entry
        assert not result.valid
        assert any(
            b.position == 1 for b in result.breaks
        )

    def test_reorder_detected(self):
        """Swapping two entries should break the chain."""
        c = self._build_chain(3)

        # Swap entries 1 and 2
        entries = (c.entries[0], c.entries[2], c.entries[1])
        reordered = SourceChain(entries)

        result = reordered.verify()
        # Position 1: entry originally at position 2 has wrong position
        # Position 1: previous_entry_hash points to original prev, not entry 0
        assert not result.valid

    def test_insertion_detected(self):
        """Inserting a forged entry should break the chain."""
        c = self._build_chain(2)

        forged = ChainEntry(
            action_ref="forged-act",
            action_type="transfer",
            actor_id="attacker",
        )
        entries = (c.entries[0], forged, c.entries[1])
        inserted = SourceChain(entries)

        result = inserted.verify()
        assert not result.valid


class TestSerialization:
    def _build_chain(self, n: int = 2) -> SourceChain:
        e = ChainEntry(
            action_ref="act-1",
            action_type="payment",
            actor_id="agent-1",
            authorization_ref="auth://alice",
            task_lineage_ref="task://report",
        )
        e = ChainEntry(**{**e.__dict__, "entry_hash": e.compute_entry_hash()})
        c = SourceChain([e])
        for i in range(2, n + 1):
            e = ChainEntry(
                action_ref=f"act-{i}",
                action_type="read",
            )
            c = c.append(e)
        return c

    def test_round_trip(self):
        c1 = self._build_chain(3)
        data = c1.to_dict()
        c2 = SourceChain.from_dict(data)

        assert c2.length == c1.length
        assert c2.chain_hash == c1.chain_hash
        for e1, e2 in zip(c1.entries, c2.entries):
            assert e1.action_ref == e2.action_ref
            assert e1.entry_hash == e2.entry_hash

    def test_round_trip_preserves_verification(self):
        c1 = self._build_chain(3)
        r1 = c1.verify()
        assert r1.valid

        data = c1.to_dict()
        c2 = SourceChain.from_dict(data)
        r2 = c2.verify()
        assert r2.valid
        assert r2.chain_hash == r1.chain_hash


class TestActionDeclarationToChainEntry:
    def test_conversion(self):
        decl = ActionDeclaration(
            action_type="payment",
            target="acct_123",
            actor_id="agent-1",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://report/step-3",
            budget_state_ref="budget://preflight",
        )
        entry = decl.to_chain_entry()
        assert entry.action_ref == decl.action_id
        assert entry.action_type == "payment"
        assert entry.authorization_ref == "auth://alice"
        assert entry.task_lineage_ref == "task://report/step-3"
        assert entry.budget_state_ref == "budget://preflight"

    def test_content_hash_includes_previous(self):
        d1 = ActionDeclaration(action_type="read", target="f1")
        h1 = d1.content_hash()

        d2 = ActionDeclaration(
            action_type="write",
            target="f2",
            previous_content_hash=h1,
        )
        h2 = d2.content_hash()

        d2_no_link = ActionDeclaration(action_type="write", target="f2")
        h2_no_link = d2_no_link.content_hash()

        assert h2 != h2_no_link  # previous_content_hash affects the hash

    def test_chain_with_declarations(self):
        d1 = ActionDeclaration(
            action_type="read",
            target="config.json",
            actor_id="agent-1",
            root_authorization_ref="auth://alice",
        )
        entry1 = d1.to_chain_entry()
        entry1 = ChainEntry(**{**entry1.__dict__, "entry_hash": entry1.compute_entry_hash()})
        chain = SourceChain([entry1])

        d2 = ActionDeclaration(
            action_type="write",
            target="config.json",
            actor_id="agent-1",
            root_authorization_ref="auth://alice",
            previous_content_hash=d1.content_hash(),
        )
        entry2 = d2.to_chain_entry()
        chain = chain.append(entry2)

        assert chain.length == 2
        result = chain.verify()
        assert result.valid


class TestSourceChainVerifierWithChain:
    def test_passes_with_complete_chain(self):
        decl = ActionDeclaration(
            action_type="read",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://1",
            tool_reason_ref="reason://1",
            decision_token_ref="token://1",
        )
        req = IntentVerificationRequest(action=decl)
        result = SourceChainVerifier().verify(req)
        assert result.passed
        assert result.score == 1.0

    def test_chain_hash_break_detected(self):
        """Mismatched previous_content_hash should be flagged."""
        decl = ActionDeclaration(
            action_type="read",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://1",
            previous_content_hash="fake_previous_hash",
        )
        req = IntentVerificationRequest(
            action=decl,
            previous_chain_hash="real_chain_hash_abc",
        )
        result = SourceChainVerifier().verify(req)
        assert not result.passed
        assert any(
            t == SourceChainBreakTag.CHAIN_HASH_MISMATCH.value
            for t in result.metadata["break_tags"]
        )

    def test_chain_break_triggers_human_review(self):
        decl = ActionDeclaration(
            action_type="payment",
            target="acct_123",
            previous_content_hash="fake_hash",
        )
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000},
            previous_chain_hash="real_hash",
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.HUMAN_REVIEW

    def test_chain_intact_passes_pipeline(self):
        """A complete chain should pass through the pipeline."""
        decl = ActionDeclaration(
            action_type="read",
            target="config.json",
            root_authorization_ref="auth://alice",
            task_lineage_ref="task://report",
            tool_reason_ref="reason://audit",
            decision_token_ref="token://prev",
        )
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
            budget_remaining={"amount_cny": 5000},
        )
        token = SayfosPipeline().evaluate(req)
        assert token.verdict == Verdict.ALLOW