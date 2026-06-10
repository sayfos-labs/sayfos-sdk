"""
Sayfos SDK example: budget-governed expense reimbursement.

Demonstrates the complete Sayfos runtime workflow:
  1. Create a budget for a finance agent.
  2. Adjudicate payment actions through the pipeline.
  3. Consume budget only for allowed actions.
  4. Block actions that exceed budget or trust boundaries.
  5. Record source-chain entries for later review.

Run: python examples/finance_agent.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
    Verdict,
)


def main() -> None:
    runtime = SayfosRuntime()

    budget = runtime.create_budget(
        owner_id="finance-agent",
        quotas={
            "amount_cny": 5000.0,
            "tool_calls": 20,
            "task_depth": 5,
        },
    )
    chain_id = runtime.create_chain()
    print(f"[Budget] created {budget.budget_id}: {budget.quotas}")

    claims = [
        {"action_type": "payment", "amount": 800, "recipient": "vendor-a"},
        {"action_type": "payment", "amount": 1200, "recipient": "vendor-b"},
        {"action_type": "payment", "amount": 3500, "recipient": "vendor-c"},
        {"action_type": "payment", "amount": 500, "recipient": "vendor-d"},
    ]

    for i, claim in enumerate(claims, 1):
        decl = ActionDeclaration(
            actor_type="finance_agent",
            action_type=claim["action_type"],
            target=claim["recipient"],
            parameters={"amount": claim["amount"]},
            root_authorization_ref="auth://user/cfo",
            task_lineage_ref=f"task://expense-batch/claim-{i}",
            tool_reason_ref=f"reason://expense-claim/{claim['recipient']}",
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

        status = "OK" if token.verdict == Verdict.ALLOW else "BLOCK"
        print(
            f"  [{status}] {claim['recipient']}: {claim['amount']} CNY "
            f"-> {token.verdict.value} ({token.reason_code})"
        )

        if token.verdict == Verdict.BLOCK:
            print(f"        detail: {token.reason_detail}")

    final = runtime.get_budget(budget.budget_id)
    print(f"\n[Budget] final: consumed={final.consumed}, remaining={final.remaining}")

    result = runtime.verify_chain(chain_id)
    print(
        f"\n[Chain] length={result.chain_length}, "
        f"valid={result.valid}, hash={result.chain_hash[:16]}..."
    )


if __name__ == "__main__":
    main()
