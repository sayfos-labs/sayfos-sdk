"""
Sayfos SDK example: AI agent API cost cutoff.

This example places a lightweight Sayfos budget gate in front of a metered
LLM/API provider. The agent submits 65 tasks, while the budget allows only
50 provider calls and $5.00 of estimated spend. After the budget is exhausted,
the remaining calls are blocked before they reach the provider.

Run:
    python examples/api_cost_budget.py

To adapt this pattern, replace MockLLMProvider.call() with your real provider
call and keep the check_budget_then_call() gate in front of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sayfos import BudgetManager


OWNER_ID = "demo-agent"
MAX_API_CALLS = 50
MAX_COST_USD = 5.00
DEFAULT_COST_PER_CALL_USD = 0.10
TASK_COUNT = 65


@dataclass(frozen=True)
class DemoConfig:
    """Configuration for the metered API budget demo."""

    owner_id: str = OWNER_ID
    max_api_calls: int = MAX_API_CALLS
    max_cost_usd: float = MAX_COST_USD
    cost_per_call_usd: float = DEFAULT_COST_PER_CALL_USD


@dataclass
class DemoStats:
    """Execution counters collected by the demo runner."""

    submitted: int = 0
    executed: int = 0
    blocked: int = 0
    estimated_cost_avoided_usd: float = 0.0


class MockLLMProvider:
    """Small stand-in for a metered LLM/API provider."""

    def __init__(self) -> None:
        self.call_count = 0

    def call(self, prompt: str) -> str:
        self.call_count += 1
        return f"[LLM response #{self.call_count}] processed: {prompt[:40]}..."


def create_budget_manager(config: DemoConfig) -> tuple[BudgetManager, str]:
    """Create a Sayfos budget and return the manager plus budget ID."""
    manager = BudgetManager()
    budget = manager.create_budget(
        owner_id=config.owner_id,
        quotas={
            "api_calls": float(config.max_api_calls),
            "cost_usd": config.max_cost_usd,
        },
    )
    return manager, budget.budget_id


def check_budget_then_call(
    *,
    prompt: str,
    budget_manager: BudgetManager,
    budget_id: str,
    provider: MockLLMProvider,
    cost_per_call_usd: float,
) -> tuple[bool, str]:
    """
    Gate a metered provider call with Sayfos budget checks.

    Returns (executed, message). In production, this function is the part that
    would sit in front of an OpenAI, Anthropic, local model, tool API, or other
    metered endpoint.
    """
    remaining = budget_manager.get_remaining(budget_id) or {}
    calls_left = int(remaining.get("api_calls", 0))
    cost_left = round(float(remaining.get("cost_usd", 0.0)), 2)

    if calls_left <= 0 or cost_left + 1e-9 < cost_per_call_usd:
        return (
            False,
            f"[Sayfos] BLOCKED: calls_left={calls_left} "
            f"cost_left=${max(cost_left, 0.0):.2f} prompt='{prompt[:40]}...'",
        )

    budget_manager.consume(
        budget_id,
        {"api_calls": 1.0, "cost_usd": cost_per_call_usd},
    )
    response = provider.call(prompt)

    remaining_calls = calls_left - 1
    remaining_cost = max(cost_left - cost_per_call_usd, 0.0)
    return (
        True,
        f"[Agent] remaining_calls={remaining_calls:02d} "
        f"remaining_cost=${remaining_cost:.2f} -> {response}",
    )


def run_tasks(
    tasks: Sequence[str],
    config: DemoConfig,
    budget_manager: BudgetManager,
    budget_id: str,
    provider: MockLLMProvider,
) -> DemoStats:
    """Run tasks through the Sayfos budget gate."""
    stats = DemoStats(submitted=len(tasks))

    for index, task in enumerate(tasks, 1):
        executed, message = check_budget_then_call(
            prompt=task,
            budget_manager=budget_manager,
            budget_id=budget_id,
            provider=provider,
            cost_per_call_usd=config.cost_per_call_usd,
        )

        if executed:
            stats.executed += 1
            print(f"[{index:03d}] {message}")
        else:
            stats.blocked += 1
            stats.estimated_cost_avoided_usd += config.cost_per_call_usd
            print(f"[{index:03d}] {message}")

    return stats


def format_remaining_budget(budget_manager: BudgetManager, budget_id: str) -> dict[str, float]:
    """Return a stable, display-friendly remaining budget snapshot."""
    remaining = budget_manager.get_remaining(budget_id) or {}
    return {
        key: round(float(value), 4)
        for key, value in remaining.items()
        if isinstance(value, (int, float))
    }


def print_summary(
    stats: DemoStats,
    budget_manager: BudgetManager,
    budget_id: str,
) -> None:
    """Print a compact summary suitable for terminal examples."""
    budget = budget_manager.store.get(budget_id)
    print()
    print("=" * 72)
    print("SUMMARY")
    print(f"  Total tasks submitted:  {stats.submitted}")
    print(f"  API calls executed:     {stats.executed}")
    print(f"  Calls blocked at gate:  {stats.blocked}")
    if budget:
        print(f"  Final budget state:     {budget.status.value}")
    print(f"  Remaining:              {format_remaining_budget(budget_manager, budget_id)}")
    print(f"  Estimated cost avoided: ${stats.estimated_cost_avoided_usd:.2f}")
    print("=" * 72)


def main() -> None:
    config = DemoConfig()
    budget_manager, budget_id = create_budget_manager(config)
    provider = MockLLMProvider()
    tasks = [f"Process invoice #{number:04d}" for number in range(1, TASK_COUNT + 1)]

    print("=" * 72)
    print("Demo: AI Agent API Cost Budget Cutoff")
    print("=" * 72)
    print(f"Tasks submitted: {len(tasks)}")
    print(f"Budget: {config.max_api_calls} calls / ${config.max_cost_usd:.2f}")
    print(f"Estimated cost per provider call: ${config.cost_per_call_usd:.2f}")
    print()

    stats = run_tasks(
        tasks=tasks,
        config=config,
        budget_manager=budget_manager,
        budget_id=budget_id,
        provider=provider,
    )
    print_summary(stats, budget_manager, budget_id)


if __name__ == "__main__":
    main()
