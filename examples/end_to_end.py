"""
Sayfos SDK example: end-to-end runtime control.

Runs one workflow through plan preflight, budget governance, causal
consistency, source-chain integrity, and final runtime adjudication.

Run: python examples/end_to_end.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
    Verdict,
)
from sayfos.verification.preflight import PlanDeclaration


def main() -> None:
    rt = SayfosRuntime()

    budget = rt.create_budget(
        owner_id="finance-agent",
        quotas={
            "amount_cny": 4000.0,
            "tool_calls": 20,
            "task_depth": 10,
        },
    )
    chain_id = rt.create_chain()
    print(f"[Budget] created: {budget.budget_id}")
    print(f"         quotas: {budget.quotas}")

    claims = [
        ("vendor-a", 500),
        ("vendor-b", 600),
        ("vendor-c", 400),
        ("vendor-d", 800),
        ("vendor-e", 700),
        ("vendor-f", 1200),
        ("vendor-g", 300),
        ("vendor-h", 200),
    ]

    plan = PlanDeclaration(
        owner_id="finance-agent",
        plan_name="expense-batch-2026-06-06",
        steps=tuple(
            ActionDeclaration(
                action_type="payment",
                target=name,
                parameters={"amount": amount, "currency": "CNY"},
                root_authorization_ref="auth://user/cfo",
                task_lineage_ref=f"task://expense-batch/{name}",
                tool_reason_ref=f"reason://approved-expense/{name}",
                decision_token_ref="token://batch-approval",
                risk_level=2 if amount < 800 else 6,
            )
            for name, amount in claims
        ),
    )

    preflight_result = rt.preflight_plan(plan, budget.budget_id)
    print("\n[Plan preflight]")
    print(f"  feasible: {preflight_result.feasible}")
    print(f"  verdict: {preflight_result.verdict.value}")
    if not preflight_result.feasible:
        step = preflight_result.first_overflow_step
        print(f"  first_overflow_step: {step} ({claims[step][0]})")
        print(f"  overflow_dimension: {preflight_result.overflow_dimension}")
        print(f"  detail: {preflight_result.overflow_detail}")
    print(f"  estimated_consumption: {preflight_result.estimated_consumption}")

    print("\n" + "=" * 60)
    print("Executing each action through Sayfos runtime checks")
    print("=" * 60)

    for i, (name, amount) in enumerate(claims):
        is_last_few = i >= len(claims) - 3

        decl = ActionDeclaration(
            actor_type="finance_agent",
            action_type="payment",
            target=name,
            parameters={"amount": amount},
            root_authorization_ref="auth://user/cfo",
            task_lineage_ref=f"task://expense-batch/{name}",
            tool_reason_ref=f"reason://approved-expense/{name}",
            decision_token_ref="token://batch-approval",
            risk_level=2 if amount < 800 else 6,
        )

        req = IntentVerificationRequest(
            action=decl,
            touch_events=8 if not is_last_few else 0,
            screen_on=not is_last_few,
            device_held=not is_last_few,
            remote_control_detected=is_last_few,
        )

        token = rt.adjudicate(
            req,
            budget_id=budget.budget_id,
            chain_id=chain_id,
        )

        status = "OK" if token.verdict == Verdict.ALLOW else "BLOCK"
        print(f"\n  [{status}] step {i}: {name} {amount} CNY")
        print(f"      causal_score: {token.embodied_consistency_score:.2f}")
        print(f"      budget_score: {token.budget_adequacy_score:.2f}")
        print(f"      source_chain_score: {token.source_chain_integrity_score:.2f}")
        print(f"      verdict: {token.verdict.value}")
        if token.reason_code != "ALL_CLEAR":
            print(f"      reason_code: {token.reason_code}")
            print(f"      detail: {token.reason_detail}")
        if token.budget_deduction:
            print(f"      budget_deduction: {token.budget_deduction}")
        if token.constraints.get("reasons"):
            print(f"      constraint_reasons: {token.constraints['reasons']}")

    final = rt.get_budget(budget.budget_id)
    print("\n" + "=" * 60)
    print("Final state")
    print("=" * 60)
    print(f"[Budget] remaining: {final.remaining}")
    print(f"[Budget] status: {final.status.value}")

    chain_result = rt.verify_chain(chain_id)
    print(f"\n[Source chain] length: {chain_result.chain_length}")
    print(f"[Source chain] valid: {chain_result.valid}")
    print(f"[Source chain] hash: {chain_result.chain_hash[:24]}...")

    if not chain_result.valid:
        for break_item in chain_result.breaks:
            print(
                f"  [Break] position={break_item.position} "
                f"tag={break_item.tag.value} detail={break_item.detail}"
            )

    print("\n[Revocation] propagation check")
    affected = rt.revoke_budget(budget.budget_id, source="cfo_revoked")
    print(f"  affected_budgets: {len(affected)}")
    revoked = rt.get_budget(budget.budget_id)
    print(f"  root_budget_status: {revoked.status.value}")


if __name__ == "__main__":
    main()
