"""
Sayfos SDK — Example: 黑屏远控检测（embodied consistency 具身验真）

Demonstrates the causal consistency verifier detecting a
black-screen remote control attack.

Scenario:
  A payment action is triggered while the device screen is OFF,
  no touch events are detected, and remote control is flagged.
  Sayfos blocks the action — even though the auth token is valid.

对比:
  合法动作: touch_events>0, screen_on=True  → ALLOW
  远控攻击:  touch_events=0, screen_on=False, remote_control_detected=True → BLOCK

Run: python examples/remote_control_detection.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    runtime = SayfosRuntime()
    budget = runtime.create_budget(
        owner_id="user-device",
        quotas={"amount_cny": 10000.0, "tool_calls": 50},
    )

    # ── 合法场景 ──────────────────────────────────────────────
    legit = ActionDeclaration(
        actor_type="mobile_app",
        action_type="payment",
        target="acct_123",
        parameters={"amount": 500.0, "recipient": "商户A"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://购物/checkout",
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
    print(f"[合法付款] 触摸={req.touch_events}, 亮屏={req.screen_on}")
    print(f"  裁决: {token.verdict.value} (因果一致性: {token.embodied_consistency_score})")
    print(f"  原因: {token.reason_code}")

    # ── 远控攻击场景 ──────────────────────────────────────────
    attack = ActionDeclaration(
        actor_type="mobile_app",
        action_type="payment",
        target="acct_evil",
        parameters={"amount": 9999.0, "recipient": "攻击者账户"},
        root_authorization_ref="auth://user/alice",  # token 合法但被滥用
        task_lineage_ref="task://unknown",
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
    print(f"\n[远控攻击] 触摸={req.touch_events}, 亮屏={req.screen_on}, 远控={req.remote_control_detected}")
    print(f"  裁决: {token.verdict.value} (因果一致性: {token.embodied_consistency_score})")
    print(f"  原因: {token.reason_code}")
    print(f"  详情: {token.reason_detail}")

    if token.constraints:
        print(f"  约束: {token.constraints}")

    # ── 预算未动 — 攻击被阻断不消耗预算 ──────────────────────
    b = runtime.get_budget(budget.budget_id)
    print(f"\n[预算检查] 合法动作消耗后剩余: {b.remaining}")
    print(f"  攻击被阻断，预算不应被消耗: consumed={b.consumed}")


if __name__ == "__main__":
    main()