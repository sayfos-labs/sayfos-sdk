"""
Sayfos SDK example: financial-risk intervention.

Demonstrates how embodied and contextual evidence can reduce trust in a
payment action even when the apparent account authorization is valid.

Run: python examples/financial_fraud_detection.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    rt = SayfosRuntime()
    budget = rt.create_budget(
        owner_id="user-device",
        quotas={"amount_cny": 50000.0, "tool_calls": 30},
    )

    def adjudicate(decl: ActionDeclaration, evidence: dict) -> dict:
        req = IntentVerificationRequest(action=decl, **evidence)
        token = rt.adjudicate(req, budget_id=budget.budget_id)
        return {
            "verdict": token.verdict.value,
            "causal_score": token.embodied_consistency_score,
            "reason": token.reason_code,
            "detail": token.reason_detail,
            "constraints": token.constraints,
        }

    normal = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="merchant/coffee_shop",
        parameters={"amount": 35.0, "recipient": "coffee-shop"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://daily-purchase",
        decision_token_ref="token://wallet-approved",
        risk_level=1,
    )
    result = adjudicate(
        normal,
        {
            "touch_events": 20,
            "key_events": 0,
            "screen_on": True,
            "device_held": True,
            "bio_presence": True,
            "remote_control_detected": False,
        },
    )
    print(
        f"[Normal payment] coffee-shop 35 CNY: {result['verdict']} "
        f"(causal_score={result['causal_score']:.2f})"
    )

    scam = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="bank_transfer/unknown-account",
        parameters={"amount": 50000.0, "recipient": "unknown-account"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://urgent-transfer",
        decision_token_ref="token://wallet-approved",
        risk_level=9,
    )
    result = adjudicate(
        scam,
        {
            "touch_events": 3,
            "key_events": 0,
            "screen_on": True,
            "device_held": True,
            "bio_presence": True,
            "remote_control_detected": False,
        },
    )
    print("\n[High-risk induced transfer] 50000 CNY to unknown account")
    print(f"  verdict: {result['verdict']}")
    print(f"  causal_score: {result['causal_score']:.2f}")
    print(f"  reason: {result['reason']}")
    print(f"  detail: {result['detail']}")

    remote = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="bank_transfer/attacker-account",
        parameters={"amount": 99999.0},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://unknown",
        decision_token_ref="token://wallet-approved",
        risk_level=10,
    )
    result = adjudicate(
        remote,
        {
            "touch_events": 0,
            "key_events": 0,
            "screen_on": False,
            "device_held": False,
            "bio_presence": False,
            "remote_control_detected": True,
        },
    )
    print("\n[Silent remote-control transfer] 99999 CNY")
    print(f"  verdict: {result['verdict']}")
    print(f"  causal_score: {result['causal_score']:.2f}")
    print(f"  reason: {result['reason']}")
    if result["constraints"].get("block_execution"):
        print("  fully blocked")

    current = rt.get_budget(budget.budget_id)
    print(f"\n[Budget] only allowed payments were consumed: consumed={current.consumed}")


if __name__ == "__main__":
    main()
