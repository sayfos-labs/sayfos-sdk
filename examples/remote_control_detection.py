"""
Sayfos SDK example: silent remote-control detection.

Demonstrates the causal consistency verifier detecting a high-risk action
triggered while the screen is off, no touch input is present, and remote
control is flagged.

Run: python examples/remote_control_detection.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    runtime = SayfosRuntime()
    budget = runtime.create_budget(
        owner_id="user-device",
        quotas={"amount_cny": 10000.0, "tool_calls": 50},
    )

    legit = ActionDeclaration(
        actor_type="mobile_app",
        action_type="payment",
        target="acct_123",
        parameters={"amount": 500.0, "recipient": "merchant-a"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://shopping/checkout",
        decision_token_ref="token://checkout-approved",
        risk_level=2,
    )
    req = IntentVerificationRequest(
        action=legit,
        touch_events=15,
        key_events=0,
        screen_on=True,
        device_held=True,
        bio_presence=True,
    )
    token = runtime.adjudicate(req, budget_id=budget.budget_id)
    print(f"[Legitimate payment] touch_events={req.touch_events}, screen_on={req.screen_on}")
    print(f"  verdict: {token.verdict.value}")
    print(f"  causal_score: {token.embodied_consistency_score}")
    print(f"  reason_code: {token.reason_code}")

    attack = ActionDeclaration(
        actor_type="mobile_app",
        action_type="payment",
        target="acct_evil",
        parameters={"amount": 9999.0, "recipient": "attacker-account"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://unknown",
        decision_token_ref="token://stolen-session",
        risk_level=9,
    )
    req = IntentVerificationRequest(
        action=attack,
        touch_events=0,
        key_events=0,
        screen_on=False,
        device_held=False,
        bio_presence=False,
        remote_control_detected=True,
    )
    token = runtime.adjudicate(req, budget_id=budget.budget_id)
    print(
        f"\n[Remote-control attempt] touch_events={req.touch_events}, "
        f"screen_on={req.screen_on}, remote_control={req.remote_control_detected}"
    )
    print(f"  verdict: {token.verdict.value}")
    print(f"  causal_score: {token.embodied_consistency_score}")
    print(f"  reason_code: {token.reason_code}")
    print(f"  detail: {token.reason_detail}")

    if token.constraints:
        print(f"  constraints: {token.constraints}")

    b = runtime.get_budget(budget.budget_id)
    print(f"\n[Budget check] remaining after allowed action: {b.remaining}")
    print(f"  blocked attack did not consume budget: consumed={b.consumed}")


if __name__ == "__main__":
    main()
