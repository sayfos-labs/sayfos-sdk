"""
Sayfos SDK — Example: 金融反欺诈 — 本人操作型诈骗检测

Demonstrates detecting "self-operated" fraud: a victim authorizes a
payment that appears legitimate (token valid, account matches)
but was induced by a scammer — the victim's cognitive state
(deception, urgency, abnormal context) should cause a low
causal-consistency score and trigger intervention.

因其无法穿透'合法授权'表象，验真支付意图背后的真实认知状态"


Corresponds exactly to:

Run: python examples/financial_fraud_detection.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    rt = SayfosRuntime()
    budget = rt.create_budget(
        owner_id="user-device",
        quotas={"amount_cny": 50000.0, "tool_calls": 30},
    )

    def adjudicate(decl: ActionDeclaration, physical_evidence: dict) -> dict:
        req = IntentVerificationRequest(action=decl, **physical_evidence)
        token = rt.adjudicate(req, budget_id=budget.budget_id)
        return {
            "verdict": token.verdict.value,
            "causal_score": token.embodied_consistency_score,
            "reason": token.reason_code,
            "detail": token.reason_detail,
            "constraints": token.constraints,
        }

    # ═══════════════════════════════════════════════════════════
    # Scenario A: Normal payment — user is calm, attentive
    # ═══════════════════════════════════════════════════════════
    normal = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="merchant/coffee_shop",
        parameters={"amount": 35.0, "recipient": "咖啡店"},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://日常消费",
        risk_level=1,
    )
    result = adjudicate(normal, {
        "touch_events": 20,
        "key_events": 0,
        "screen_on": True,
        "device_held": True,
        "bio_presence": True,
        "remote_control_detected": False,
    })
    print(f"[正常消费] 咖啡 ¥35: {result['verdict']} "
          f"(因果={result['causal_score']:.2f})")

    # ═══════════════════════════════════════════════════════════
    # Scenario B: Scam-induced payment — victim is nervous,
    # rapid typing, on phone with scammer
    # ═══════════════════════════════════════════════════════════
    scam = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="bank_transfer/陌生账户",
        parameters={"amount": 50000.0, "recipient": "诈骗账户"},
        root_authorization_ref="auth://user/alice",  # 合法授权!
        task_lineage_ref="task://紧急转账",
        risk_level=9,
    )
    result = adjudicate(scam, {
        "touch_events": 3,          # rapid, few deliberate touches
        "key_events": 0,
        "screen_on": True,
        "device_held": True,
        "bio_presence": True,       # 用户本人在操作 — 但被诱导
        "remote_control_detected": False,
    })
    print(f"\n[诈骗诱导] 转账 ¥50000 至陌生账户:")
    print(f"  裁决: {result['verdict']}")
    print(f"  因果一致性: {result['causal_score']:.2f}")
    print(f"  原因: {result['reason']}")
    print(f"  详情: {result['detail']}")

    # ═══════════════════════════════════════════════════════════
    # Scenario C: Remote control — black screen, no touch
    # ═══════════════════════════════════════════════════════════
    remote = ActionDeclaration(
        actor_type="mobile_wallet",
        action_type="payment",
        target="bank_transfer/攻击者账户",
        parameters={"amount": 99999.0},
        root_authorization_ref="auth://user/alice",
        task_lineage_ref="task://unknown",
        risk_level=10,
    )
    result = adjudicate(remote, {
        "touch_events": 0,
        "key_events": 0,
        "screen_on": False,
        "device_held": False,
        "bio_presence": False,
        "remote_control_detected": True,
    })
    print(f"\n[黑屏远控] 转账 ¥99999:")
    print(f"  裁决: {result['verdict']}")
    print(f"  因果一致性: {result['causal_score']:.2f}")
    print(f"  原因: {result['reason']}")
    if result["constraints"].get("block_execution"):
        print(f"  → 完全阻断")

    # ═══════════════════════════════════════════════════════════
    # Budget integrity — scam/remote payments should NOT consume
    # ═══════════════════════════════════════════════════════════
    b = rt.get_budget(budget.budget_id)
    print(f"\n[预算] 仅有正常消费被扣减: consumed={b.consumed}")


if __name__ == "__main__":
    main()