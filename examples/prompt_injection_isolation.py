"""
Sayfos SDK example: prompt-injection isolation.

Demonstrates Sayfos detecting and isolating actions triggered by untrusted
input sources, including indirect prompt-injection attempts.

Run: python examples/prompt_injection_isolation.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    rt = SayfosRuntime()

    budget = rt.create_budget(
        owner_id="refund-agent",
        quotas={
            "amount_cny": 10000.0,
            "tool_calls": 30,
        },
    )
    chain_id = rt.create_chain()
    print(f"[Refund agent] budget: {budget.quotas}")

    normal = ActionDeclaration(
        actor_type="refund_agent",
        action_type="payment",
        target="refund/order-12345",
        parameters={"amount": 299.0, "reason": "customer_request"},
        root_authorization_ref="auth://crm/system",
        task_lineage_ref="task://refund/order-12345",
        tool_reason_ref="reason://customer-requested-refund",
        decision_token_ref="token://crm-approved",
        input_source_ref="trusted://crm/ticket-5678",
        risk_level=2,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=normal,
            touch_events=5,
            screen_on=True,
            device_held=True,
        ),
        budget_id=budget.budget_id,
        chain_id=chain_id,
    )
    print(f"\n[Normal refund] order-12345: {token.verdict.value}")
    print(f"  source_chain_score: {token.source_chain_integrity_score}")

    injected = ActionDeclaration(
        actor_type="refund_agent",
        action_type="payment",
        target="refund/order-99999",
        parameters={"amount": 9999.0, "reason": "system_refund"},
        root_authorization_ref="auth://crm/system",
        task_lineage_ref="task://refund/order-99999",
        tool_reason_ref="reason://uploaded-file-triggered",
        decision_token_ref="token://crm-approved",
        input_source_ref="untrusted://user-uploaded-file/evil.pdf",
        risk_level=10,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=injected,
            touch_events=0,
            screen_on=True,
            device_held=False,
        ),
        budget_id=budget.budget_id,
        chain_id=chain_id,
    )
    print(f"\n[Injected refund] order-99999: {token.verdict.value}")
    print(f"  source_chain_score: {token.source_chain_integrity_score}")
    print(f"  reason_code: {token.reason_code}")
    print(f"  detail: {token.reason_detail}")
    print(f"  break_tags: {[tag.value for tag in token.source_chain_break_tags]}")

    if token.constraints.get("require_human_review"):
        print("  action isolated: human review required")
    if token.constraints.get("block_execution"):
        print("  action blocked")

    sub_task = ActionDeclaration(
        actor_type="refund_sub_agent",
        action_type="payment",
        target="refund/order-88888",
        parameters={"amount": 5000.0},
        root_authorization_ref="auth://parent-agent",
        task_lineage_ref="task://subtask/inherited-pollution",
        tool_reason_ref="reason://parent-task",
        decision_token_ref="token://parent-decision",
        input_source_ref="untrusted://parent-task/inherited",
        parent_action_id="act-injected-99999",
        risk_level=9,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=sub_task,
            touch_events=0,
            screen_on=True,
            device_held=False,
            source_chain_entries=("act-injected-99999",),
            previous_chain_hash="abc123",
        ),
        budget_id=budget.budget_id,
        chain_id=chain_id,
    )
    print(f"\n[Inherited pollution] order-88888: {token.verdict.value}")
    print(f"  source_chain_score: {token.source_chain_integrity_score}")
    print(f"  break_tags: {[tag.value for tag in token.source_chain_break_tags]}")

    final = rt.get_budget(budget.budget_id)
    print(f"\n[Budget] remaining: {final.remaining}")
    chain = rt.verify_chain(chain_id)
    print(f"[Source chain] valid={chain.valid}, length={chain.chain_length}")


if __name__ == "__main__":
    main()
