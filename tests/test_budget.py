"""
Tests for BudgetStore and BudgetManager — budget governance runtime budget lifecycle.

Covers:
  - Budget creation and retrieval
  - Immutable consumption via store
  - Freeze and revoke with propagation to children
  - Propagation chain traversal
  - Thread safety (InMemoryBudgetStore)
"""

import threading
import pytest

from sayfos.budget import BudgetManager, InMemoryBudgetStore
from sayfos.core.models import Budget
from sayfos.core.enums import BudgetStatus


class TestInMemoryBudgetStore:
    def test_create_and_get(self):
        store = InMemoryBudgetStore()
        b = store.create(Budget(owner_id="agent-1", quotas={"amount": 1000}))
        retrieved = store.get(b.budget_id)
        assert retrieved is not None
        assert retrieved.owner_id == "agent-1"

    def test_update(self):
        store = InMemoryBudgetStore()
        b = store.create(Budget(owner_id="agent-1", quotas={"amount": 1000}))
        consumed = b.consume({"amount": 500})
        store.update(consumed)
        retrieved = store.get(b.budget_id)
        assert retrieved.remaining["amount"] == 500.0
        assert retrieved.consumed["amount"] == 500.0

    def test_delete(self):
        store = InMemoryBudgetStore()
        b = store.create(Budget(owner_id="agent-1", quotas={"amount": 1000}))
        assert store.delete(b.budget_id)
        assert store.get(b.budget_id) is None

    def test_list_by_owner(self):
        store = InMemoryBudgetStore()
        store.create(Budget(owner_id="agent-1", quotas={"amount": 100}))
        store.create(Budget(owner_id="agent-1", quotas={"amount": 200}))
        store.create(Budget(owner_id="agent-2", quotas={"amount": 300}))
        assert len(store.list_by_owner("agent-1")) == 2
        assert len(store.list_by_owner("agent-2")) == 1

    def test_list_children(self):
        store = InMemoryBudgetStore()
        parent = store.create(Budget(owner_id="root", quotas={"amount": 5000}))
        c1 = Budget(
            owner_id="child-1",
            quotas={"amount": 1000},
            parent_budget_ref=parent.budget_id,
        )
        c2 = Budget(
            owner_id="child-2",
            quotas={"amount": 500},
            parent_budget_ref=parent.budget_id,
        )
        store.create(c1)
        store.create(c2)
        children = store.list_children(parent.budget_id)
        assert len(children) == 2

    def test_thread_safety(self):
        store = InMemoryBudgetStore()
        store.create(Budget(owner_id="shared", quotas={"amount": 10000}))

        results = []

        def worker():
            for _ in range(100):
                budgets = store.list_by_owner("shared")
                results.append(len(budgets))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 1 for r in results)


class TestBudgetManager:
    def test_create_budget(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        assert b.owner_id == "agent-1"
        assert b.status == BudgetStatus.ACTIVE

    def test_consume_via_manager(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        updated = mgr.consume(b.budget_id, {"amount_cny": 1000})
        assert updated is not None
        assert updated.remaining["amount_cny"] == 4000.0

        retrieved = mgr.store.get(b.budget_id)
        assert retrieved.remaining["amount_cny"] == 4000.0

    def test_get_remaining(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        remaining = mgr.get_remaining(b.budget_id)
        assert remaining == {"amount_cny": 5000.0}

    def test_is_terminal_revoked(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        mgr.revoke(b.budget_id)
        assert mgr.is_terminal(b.budget_id)

    def test_freeze_no_children(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        affected = mgr.freeze(b.budget_id, source="admin")
        assert len(affected) == 1
        assert affected[0].status == BudgetStatus.FROZEN

    def test_revoke_no_children(self):
        mgr = BudgetManager()
        b = mgr.create_budget(owner_id="agent-1", quotas={"amount_cny": 5000})
        affected = mgr.revoke(b.budget_id, source="user")
        assert len(affected) == 1
        assert affected[0].status == BudgetStatus.REVOKED

    def test_revoke_propagation_to_children(self):
        """Revoking a parent budget propagates to all child budgets."""
        mgr = BudgetManager()
        parent = mgr.create_budget(owner_id="root", quotas={"amount_cny": 10000})

        c1 = mgr.create_budget(
            owner_id="child-1",
            quotas={"amount_cny": 3000},
            parent_id=parent.budget_id,
        )
        c2 = mgr.create_budget(
            owner_id="child-2",
            quotas={"amount_cny": 2000},
            parent_id=parent.budget_id,
        )
        gc = mgr.create_budget(
            owner_id="grandchild",
            quotas={"amount_cny": 500},
            parent_id=c1.budget_id,
        )
        mgr.consume(c2.budget_id, {"amount_cny": 500})

        affected = mgr.revoke(parent.budget_id, source="user_revoked")

        assert len(affected) >= 3
        statuses = {b.budget_id: b.status for b in affected}
        assert statuses[parent.budget_id] == BudgetStatus.REVOKED
        assert statuses[c1.budget_id] == BudgetStatus.REVOKED
        assert statuses[c2.budget_id] == BudgetStatus.REVOKED

    def test_freeze_propagation_to_children(self):
        mgr = BudgetManager()
        parent = mgr.create_budget(owner_id="root", quotas={"amount_cny": 10000})
        child = mgr.create_budget(
            owner_id="child",
            quotas={"amount_cny": 3000},
            parent_id=parent.budget_id,
        )
        affected = mgr.freeze(parent.budget_id, source="risk_detected")
        assert len(affected) >= 2
        for b in affected:
            assert b.status == BudgetStatus.FROZEN

    def test_revoke_without_propagation(self):
        mgr = BudgetManager()
        parent = mgr.create_budget(owner_id="root", quotas={"amount_cny": 10000})
        child = mgr.create_budget(
            owner_id="child",
            quotas={"amount_cny": 3000},
            parent_id=parent.budget_id,
        )
        affected = mgr.revoke(parent.budget_id, source="user", propagate=False)
        assert len(affected) == 1
        assert affected[0].budget_id == parent.budget_id

        child_retrieved = mgr.store.get(child.budget_id)
        assert child_retrieved.status == BudgetStatus.ACTIVE

    def test_create_child_budget_auto_links(self):
        mgr = BudgetManager()
        parent = mgr.create_budget(owner_id="root", quotas={"amount_cny": 10000})
        child = mgr.create_budget(
            owner_id="child",
            quotas={"amount_cny": 2000},
            parent_id=parent.budget_id,
        )
        assert child.parent_budget_ref == parent.budget_id

    def test_propagation_chain(self):
        mgr = BudgetManager()
        parent = mgr.create_budget(owner_id="root", quotas={"amount_cny": 10000})
        mgr.create_budget(owner_id="c1", quotas={"amount_cny": 3000}, parent_id=parent.budget_id)
        mgr.create_budget(owner_id="c2", quotas={"amount_cny": 2000}, parent_id=parent.budget_id)

        tree = mgr.get_propagation_chain(parent.budget_id)
        assert tree["budget_id"] == parent.budget_id
        assert len(tree["children"]) == 2

    def test_consume_nonexistent_returns_none(self):
        mgr = BudgetManager()
        assert mgr.consume("nonexistent", {"amount": 100}) is None

    def test_is_terminal_nonexistent(self):
        mgr = BudgetManager()
        assert mgr.is_terminal("nonexistent")

    def test_freeze_nonexistent(self):
        mgr = BudgetManager()
        assert mgr.freeze("nonexistent") == []
