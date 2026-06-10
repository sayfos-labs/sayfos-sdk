"""
Sayfos SDK — Example: AI 费用上限拦截

Demonstrates using Sayfos budget governance to cap an AI Agent's
API calls and cost before your OpenAI / Anthropic bill explodes.

Run: python examples/api_cost_budget.py

Replace the mock `call_llm_api` with your real endpoint to use in production.
"""

import textwrap
from sayfos import BudgetManager, Budget


# ── Mock LLM API ────────────────────────────────────────────────────
# Replace this function body with your actual LLM call.
# Sayfos doesn't care who the callee is — it only gates on budget.

_CALL_COUNT = 0


def call_llm_api(prompt: str) -> str:
    """Mock LLM API endpoint.  Each call costs ~$0.10."""
    global _CALL_COUNT
    _CALL_COUNT += 1
    return f"[LLM response #{_CALL_COUNT}] Got it — '{prompt[:40]}...' processed."


# ── Budget setup ────────────────────────────────────────────────────

def create_agent_budget() -> BudgetManager:
    """
    Create a budget that limits the agent to:
      50 API calls
      $5.00 total cost
    After either limit is hit, Sayfos blocks further calls.
    """
    mgr = BudgetManager()
    mgr.create_budget(
        owner_id="demo-agent",
        quotas={
            "api_calls": 50,
            "cost_usd": 5.00,
        },
    )
    return mgr


# ── Agent loop ──────────────────────────────────────────────────────

def run_agent(
    tasks: list[str],
    budget_mgr: BudgetManager,
    budget_id: str,
    cost_per_call: float = 0.10,
):
    """
    Process a list of tasks through the agent.
    Before each API call the budget is checked — if exhausted, the
    agent is blocked exactly *before* money leaves your account.

    `cost_per_call` is just a mock; in production this would be
    derived from the actual model pricing (e.g. token counts).
    """
    blocked_count = 0

    for i, task in enumerate(tasks, 1):
        # ── Budget check (the Sayfos layer) ──────────────────────
        remaining = budget_mgr.get_remaining(budget_id) or {}
        calls_left = int(remaining.get("api_calls", 0))
        cost_left = round(remaining.get("cost_usd", 0), 2)

        if calls_left <= 0 or cost_left < cost_per_call:
            blocked_count += 1
            print(
                f"[Sayfos] BLOCKED — "
                f"calls_left={calls_left}  "
                f"cost_left=${cost_left:.2f}  "
                f"task='{task[:40]}...'"
            )
            continue  # ← the API call never happens

        # ── Deduct budget ────────────────────────────────────────
        budget_mgr.consume(
            budget_id,
            {"api_calls": 1, "cost_usd": cost_per_call},
        )

        # ── Real API call (replace this block with your own) ─────
        response = call_llm_api(task)

        print(
            f"[Agent]   #{i:03d}  "
            f"bgt={calls_left - 1}/{int(remaining['api_calls'])} calls  "
            f"${cost_left - cost_per_call:.2f} left  →  {response}"
        )

    # ── Summary ──────────────────────────────────────────────────
    budget = budget_mgr.store.get(budget_id)
    print()
    print("=" * 72)
    print("SUMMARY")
    print(f"  Total tasks submitted:  {len(tasks)}")
    print(f"  API calls executed:     {_CALL_COUNT}")
    print(f"  Calls blocked at gate:  {blocked_count}")
    if budget:
        print(f"  Final budget state:     {budget.status.value}")
        print(f"  Remaining:              {budget.remaining}")
    print(
        f"\n  Estimated cost saved:   ${blocked_count * cost_per_call:.2f}"
        f" (money that never left your account)"
    )
    print("=" * 72)


# ── Main ────────────────────────────────────────────────────────────

def main():
    budget_mgr = create_agent_budget()
    budgets = budget_mgr.store.list_by_owner("demo-agent")
    budget_id = budgets[0].budget_id

    print("=" * 72)
    print("Demo: AI Agent API Cost Budget Cutoff")
    print("=" * 72)
    print(
        textwrap.dedent("""\
        An agent loop processes 65 tasks in a batch.
        Each call to the LLM endpoint costs ~$0.10.
        Budget is hard-capped at 50 calls / $5.00.
        After either limit, Sayfos blocks the call BEFORE
        the request leaves your machine — no bill shock.
        """)
    )

    # 65 tasks — the budget only allows 50 calls
    tasks = [f"Process invoice #{n:04d}" for n in range(1, 66)]
    run_agent(tasks, budget_mgr, budget_id)


if __name__ == "__main__":
    main()
