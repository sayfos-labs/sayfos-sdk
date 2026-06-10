"""
Sayfos SDK example: parent and child agent budgets.

Demonstrates constrained sub-budgets for delegated agents and revocation
propagation from a parent agent to its children.

Run: python examples/multi_agent.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    runtime = SayfosRuntime()

    parent = runtime.create_budget(
        owner_id="orchestrator-agent",
        quotas={
            "amount_cny": 10000.0,
            "tool_calls": 50,
            "data_egress_mb": 100.0,
        },
    )
    print(f"[Parent budget] {parent.budget_id}: {parent.quotas}")

    children = {}
    for name, amount in [
        ("collector-agent", 3000),
        ("analysis-agent", 4000),
        ("report-agent", 2000),
    ]:
        child = runtime.create_budget(
            owner_id=name,
            quotas={"amount_cny": float(amount), "tool_calls": 10},
            parent_id=parent.budget_id,
        )
        children[name] = child
        print(f"  [Child budget] {name} -> {child.budget_id}: {child.quotas}")

    chain_id = runtime.create_chain()

    for name, child in children.items():
        decl = ActionDeclaration(
            actor_type=name,
            action_type="data_egress" if "collector" in name else "read",
            target=f"api/{name}",
            parameters={"amount": 500},
            root_authorization_ref=f"auth://parent/{parent.budget_id}",
            task_lineage_ref=f"task://market-analysis/{name}",
            tool_reason_ref=f"reason://delegated-task/{name}",
            decision_token_ref="token://parent-approved",
            budget_state_ref=child.budget_id,
        )
        request = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
        )
        token = runtime.adjudicate(
            request,
            budget_id=child.budget_id,
            chain_id=chain_id,
        )
        print(f"  [{name}] -> {token.verdict.value}")

    print("\n[Revocation] parent authorization revoked")
    affected = runtime.revoke_budget(parent.budget_id, source="user_revoked")

    for budget in affected:
        print(f"  {budget.owner_id}: status={budget.status.value}")

    for name, child in children.items():
        current = runtime.get_budget(child.budget_id)
        print(f"  [{name}] status: {current.status.value}")

    result = runtime.verify_chain(chain_id)
    print(f"\n[Source chain] valid={result.valid}, length={result.chain_length}")


if __name__ == "__main__":
    main()
