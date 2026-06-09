"""
Sayfos SDK — Example: 财务 Agent 批量报销

Demonstrates the complete Sayfos workflow:
  1. Create a proxy-authority budget for a financial agent
  2. Adjudicate payment actions through the pipeline
  3. Budget auto-consumption on approved actions
  4. Block actions that exceed budget
  5. Source chain tracking for audit

Run: python examples/finance_agent.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosPipeline,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    # ── 1. Set up the runtime ──────────────────────────────────
    runtime = SayfosRuntime()

    # Create a budget: 5000 CNY, 20 tool calls, 5 task depth
    budget = runtime.create_budget(
        owner_id="finance-agent",
        quotas={
            "amount_cny": 5000.0,
            "tool_calls": 20,
            "task_depth": 5,
        },
    )
    chain_id = runtime.create_chain()
    print(f"[Budget]  created {budget.budget_id}: {budget.quotas}")

    # ── 2. Process a batch of expense claims ────────────────────
    claims = [
        {"action_type": "payment", "amount": 800, "recipient": "供应商A"},
        {"action_type": "payment", "amount": 1200, "recipient": "供应商B"},
        {"action_type": "payment", "amount": 3500, "recipient": "供应商C"},  # 会超预算!
        {"action_type": "payment", "amount": 500, "recipient": "供应商D"},
    ]

    for i, claim in enumerate(claims, 1):
        decl = ActionDeclaration(
            actor_type="finance_agent",
            action_type=claim["action_type"],
            target=claim["recipient"],
            parameters={"amount": claim["amount"]},
            root_authorization_ref="auth://user/cfo",
            task_lineage_ref=f"task://报销批次/claim-{i}",
            tool_reason_ref=f"reason://报销单/{claim['recipient']}",
            decision_token_ref="token://prev-allowed",
            risk_level=3,
        )

        request = IntentVerificationRequest(
            action=decl,
            touch_events=10,
            screen_on=True,
            device_held=True,
        )

        token = runtime.adjudicate(
            request,
            budget_id=budget.budget_id,
            chain_id=chain_id,
        )

        status = "✓" if token.verdict == Verdict.ALLOW else "✗"
        print(
            f"  [{status}] {claim['recipient']}: {claim['amount']} CNY "
            f"→ {token.verdict.value} ({token.reason_code})"
        )

        if token.verdict == Verdict.BLOCK:
            print(f"        原因: {token.reason_detail}")

    # ── 3. Check final budget state ─────────────────────────────
    final = runtime.get_budget(budget.budget_id)
    print(f"\n[Budget] final: consumed={final.consumed}, remaining={final.remaining}")

    # ── 4. Verify the source chain ──────────────────────────────
    result = runtime.verify_chain(chain_id)
    print(f"\n[Chain]  长度={result.chain_length}, 有效={result.valid}, 哈希={result.chain_hash[:16]}...")


if __name__ == "__main__":
    main()