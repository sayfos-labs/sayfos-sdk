"""
Sayfos Protocol — Budget store (budget governance runtime).

Abstract interface and in-memory implementation for machine-readable budget
lifecycle management. Budgets can be created, consumed, frozen, revoked, and
propagated across parent-child delegation trees.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sayfos.core.models import Budget
from sayfos.core.enums import BudgetStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Abstract store ───────────────────────────────────────────────────


class BudgetStore(ABC):
    """Pluggable storage backend for Budget objects."""

    @abstractmethod
    def create(self, budget: Budget) -> Budget:
        """Persist a new budget and return it."""

    @abstractmethod
    def get(self, budget_id: str) -> Optional[Budget]:
        """Retrieve a budget by ID."""

    @abstractmethod
    def update(self, budget: Budget) -> Budget:
        """Atomically replace a budget (used after immutable operations)."""

    @abstractmethod
    def delete(self, budget_id: str) -> bool:
        """Remove a budget."""

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[Budget]:
        """Return all budgets for an owner."""

    @abstractmethod
    def list_children(self, parent_id: str) -> list[Budget]:
        """Return all child budgets of a parent."""


# ── In-memory implementation ─────────────────────────────────────────


class InMemoryBudgetStore(BudgetStore):
    """Thread-safe in-memory budget store."""

    def __init__(self):
        self._data: dict[str, Budget] = {}
        self._lock = threading.Lock()

    def create(self, budget: Budget) -> Budget:
        with self._lock:
            self._data[budget.budget_id] = budget
            return budget

    def get(self, budget_id: str) -> Optional[Budget]:
        with self._lock:
            return self._data.get(budget_id)

    def update(self, budget: Budget) -> Budget:
        with self._lock:
            self._data[budget.budget_id] = budget
            return budget

    def delete(self, budget_id: str) -> bool:
        with self._lock:
            return self._data.pop(budget_id, None) is not None

    def list_by_owner(self, owner_id: str) -> list[Budget]:
        with self._lock:
            return [
                b for b in self._data.values()
                if b.owner_id == owner_id
            ]

    def list_children(self, parent_id: str) -> list[Budget]:
        with self._lock:
            return [
                b for b in self._data.values()
                if b.parent_budget_ref == parent_id
            ]


# ── Budget Manager ───────────────────────────────────────────────────


class BudgetManager:
    """
    budget governance runtime: creates, tracks, consumes, and propagates budgets.

    Wraps a BudgetStore with Sayfos pipeline integration.
    """

    def __init__(self, store: Optional[BudgetStore] = None):
        self.store = store or InMemoryBudgetStore()

    # ── S1: Budget creation ────────────────────────────────────

    def create_budget(
        self,
        owner_id: str,
        quotas: dict[str, float],
        parent_id: Optional[str] = None,
        time_window_start: Optional[datetime] = None,
        time_window_end: Optional[datetime] = None,
    ) -> Budget:
        budget = Budget(
            owner_id=owner_id,
            quotas=quotas,
            parent_budget_ref=parent_id,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
        )
        if parent_id:
            parent = self.store.get(parent_id)
            if parent:
                budget = parent.spawn_child(owner_id, quotas)
        return self.store.create(budget)

    # ── S2: Budget consumption ────────────────────────────────

    def consume(
        self,
        budget_id: str,
        deductions: dict[str, float],
    ) -> Optional[Budget]:
        budget = self.store.get(budget_id)
        if not budget:
            return None
        updated = budget.consume(deductions)
        self.store.update(updated)
        return updated

    # ── S3: Budget adjudication helper ─────────────────────────

    def get_remaining(self, budget_id: str) -> Optional[dict[str, float]]:
        budget = self.store.get(budget_id)
        return budget.remaining if budget else None

    def is_terminal(self, budget_id: str) -> bool:
        budget = self.store.get(budget_id)
        if not budget:
            return True
        return budget.status in (
            BudgetStatus.REVOKED,
            BudgetStatus.EXPIRED,
        )

    # ── S4: Revocation propagation ─────────────────────────────

    def freeze(
        self,
        budget_id: str,
        source: str = "",
        propagate: bool = True,
    ) -> list[Budget]:
        """Freeze a budget and optionally all children."""
        affected: list[Budget] = []
        budget = self.store.get(budget_id)
        if not budget:
            return affected

        frozen = budget.freeze(source)
        self.store.update(frozen)
        affected.append(frozen)

        if propagate:
            affected.extend(
                self._propagate_to_children(budget_id, "freeze", source)
            )
        return affected

    def revoke(
        self,
        budget_id: str,
        source: str = "",
        propagate: bool = True,
    ) -> list[Budget]:
        """Revoke a budget and propagate to all descendants."""
        affected: list[Budget] = []
        budget = self.store.get(budget_id)
        if not budget:
            return affected

        revoked = budget.revoke(source)
        self.store.update(revoked)
        affected.append(revoked)

        if propagate:
            affected.extend(
                self._propagate_to_children(budget_id, "revoke", source)
            )
        return affected

    def _propagate_to_children(
        self,
        parent_id: str,
        action: str,
        source: str,
        depth: int = 0,
        max_depth: int = 50,
    ) -> list[Budget]:
        if depth >= max_depth:
            return []

        affected: list[Budget] = []
        children = self.store.list_children(parent_id)

        for child in children:
            child = self.store.get(child.budget_id)
            if not child:
                continue
            if action == "revoke":
                child = child.revoke(source)
            else:
                child = child.freeze(source)
            child = Budget(
                **{**child.__dict__, "propagation_depth": depth + 1}
            )
            self.store.update(child)
            affected.append(child)

            # Recurse into grandchildren
            affected.extend(
                self._propagate_to_children(
                    child.budget_id, action, source, depth + 1, max_depth
                )
            )
        return affected

    def get_propagation_chain(self, budget_id: str) -> dict:
        """Return the full propagation tree from a root budget."""
        root = self.store.get(budget_id)
        if not root:
            return {}

        def walk(bid: str) -> dict:
            result: dict = {
                "budget_id": bid,
                "children": [],
            }
            for child in self.store.list_children(bid):
                result["children"].append(walk(child.budget_id))
            return result

        return walk(budget_id)
