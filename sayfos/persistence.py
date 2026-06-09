"""
Sayfos Protocol — JSON file-backed budget store.

Thread-safe persistent storage using a JSON file on disk.
Suitable for local development, testing, and single-node deployments.

Usage::

    from sayfos.persistence import JSONBudgetStore
    store = JSONBudgetStore("budgets.json")
    runtime = SayfosRuntime(store=store)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from sayfos.core.models import Budget
from sayfos.core.enums import BudgetStatus
from sayfos.budget import BudgetStore


def _serialize(budget: Budget) -> dict:
    return {
        "budget_id": budget.budget_id,
        "created_at": budget.created_at.isoformat(),
        "owner_id": budget.owner_id,
        "quotas": budget.quotas,
        "consumed": budget.consumed,
        "status": budget.status.value,
        "parent_budget_ref": budget.parent_budget_ref,
        "child_budget_refs": list(budget.child_budget_refs),
        "time_window_start": budget.time_window_start.isoformat() if budget.time_window_start else None,
        "time_window_end": budget.time_window_end.isoformat() if budget.time_window_end else None,
        "consequence_boundary": budget.consequence_boundary,
        "revocation_source": budget.revocation_source,
        "propagation_depth": budget.propagation_depth,
    }


def _deserialize(data: dict) -> Budget:
    return Budget(
        budget_id=data["budget_id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        owner_id=data["owner_id"],
        quotas=data["quotas"],
        consumed=data["consumed"],
        status=BudgetStatus(data["status"]),
        parent_budget_ref=data.get("parent_budget_ref"),
        child_budget_refs=tuple(data.get("child_budget_refs", [])),
        time_window_start=datetime.fromisoformat(data["time_window_start"]) if data.get("time_window_start") else None,
        time_window_end=datetime.fromisoformat(data["time_window_end"]) if data.get("time_window_end") else None,
        consequence_boundary=data.get("consequence_boundary", {}),
        revocation_source=data.get("revocation_source"),
        propagation_depth=data.get("propagation_depth", 0),
    )


class JSONBudgetStore(BudgetStore):
    """
    File-backed budget store.  Flushes to disk on every mutation.

    Thread-safe via internal lock.
    """

    def __init__(self, path: str = "budgets.json"):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, Budget] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)
        self._data = {
            bid: _deserialize(d) for bid, d in raw.items()
        }

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {bid: _serialize(b) for bid, b in self._data.items()},
                f,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    def create(self, budget: Budget) -> Budget:
        with self._lock:
            self._data[budget.budget_id] = budget
            self._save()
            return budget

    def get(self, budget_id: str) -> Optional[Budget]:
        with self._lock:
            return self._data.get(budget_id)

    def update(self, budget: Budget) -> Budget:
        with self._lock:
            self._data[budget.budget_id] = budget
            self._save()
            return budget

    def delete(self, budget_id: str) -> bool:
        with self._lock:
            if budget_id in self._data:
                del self._data[budget_id]
                self._save()
                return True
            return False

    def list_by_owner(self, owner_id: str) -> list[Budget]:
        with self._lock:
            return [b for b in self._data.values() if b.owner_id == owner_id]

    def list_children(self, parent_id: str) -> list[Budget]:
        with self._lock:
            return [b for b in self._data.values() if b.parent_budget_ref == parent_id]
