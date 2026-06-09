"""
Sayfos Protocol — 全栈端到端演示：runtime checks组合裁决

单次工作流串联 embodied consistency + budget governance + source-chain integrity + plan preflight：

  embodied consistency 具身验真   → 每一步检查数字动作是否有物理交互证据
  plan preflight 计划预适配 → 执行前预判整个计划在预算内是否可行
  budget governance 代理权预算 → 每步消耗预算，超界阻断
  source-chain integrity 来源链     → 每步追加到哈希链，事后可验证完整链路

场景:
  财务 Agent 收到 8 笔报销，先生成执行计划 → 计划预适配通过 →
  逐笔执行 → 第 6 笔超预算被阻断 → 来源链完整可审计

Run: python examples/end_to_end.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)
from sayfos.verification.preflight import PlanDeclaration, PlanVerdict, PreflightStrategy


def main():
    rt = SayfosRuntime()

    # ═══════════════════════════════════════════════════════════
    # S1: 创建预算（budget governance S1）
    # ═══════════════════════════════════════════════════════════
    budget = rt.create_budget(
        owner_id="finance-agent",
        quotas={
            "amount_cny": 4000.0,
            "tool_calls": 20,
            "task_depth": 10,
        },
    )
    chain_id = rt.create_chain()
    print(f"[budget governance·S1] 预算创建: {budget.budget_id}")
    print(f"         额度: {budget.quotas}")

    # ═══════════════════════════════════════════════════════════
    # plan preflight: 计划预适配 — 8 步报销计划 vs 预算
    # ═══════════════════════════════════════════════════════════
    claims = [
        ("供应商A", 500), ("供应商B", 600), ("供应商C", 400),
        ("供应商D", 800), ("供应商E", 700), ("供应商F", 1200),  # 这步会超!
        ("供应商G", 300), ("供应商H", 200),
    ]

    plan = PlanDeclaration(
        owner_id="finance-agent",
        plan_name="批量报销-2026-06-06",
        steps=tuple(
            ActionDeclaration(
                action_type="payment",
                target=name,
                parameters={"amount": amount, "currency": "CNY"},
                root_authorization_ref="auth://user/cfo",
                task_lineage_ref=f"task://报销批次/{name}",
                tool_reason_ref=f"reason://审核通过/{name}",
                risk_level=2 if amount < 800 else 6,
            )
            for name, amount in claims
        ),
    )

    preflight_result = rt.preflight_plan(plan, budget.budget_id)
    print(f"\n[plan preflight·计划预适配]")
    print(f"  可行: {preflight_result.feasible}")
    print(f"  裁决: {preflight_result.verdict.value}")
    if not preflight_result.feasible:
        print(f"  首次超界: 步骤 {preflight_result.first_overflow_step} "
              f"({claims[preflight_result.first_overflow_step][0]})")
        print(f"  超界维度: {preflight_result.overflow_dimension}")
        print(f"  详情: {preflight_result.overflow_detail}")
    print(f"  预估总消耗: {preflight_result.estimated_consumption}")

    # ═══════════════════════════════════════════════════════════
    # 逐笔执行 — embodied consistency + budget governance + source-chain integrity 每条动作都走三引擎
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"逐笔执行 — 每笔经过 embodied consistency(因果) + budget governance(预算) + source-chain integrity(来源链)")
    print(f"{'='*60}")

    for i, (name, amount) in enumerate(claims):
        # ── embodied consistency: 构建带物理状态证据的请求 ──────────────────────
        is_last_few = i >= len(claims) - 3

        decl = ActionDeclaration(
            actor_type="finance_agent",
            action_type="payment",
            target=name,
            parameters={"amount": amount},
            root_authorization_ref="auth://user/cfo",
            task_lineage_ref=f"task://报销批次/{name}",
            tool_reason_ref=f"reason://审核通过/{name}",
            decision_token_ref="token://batch-approval",
            risk_level=2 if amount < 800 else 6,
        )

        req = IntentVerificationRequest(
            action=decl,
            touch_events=8 if not is_last_few else 0,
            screen_on=True if not is_last_few else False,
            device_held=True if not is_last_few else False,
            remote_control_detected=is_last_few,
        )

        # ── 执行管道 ───────────────────────────────────────────
        token = rt.adjudicate(
            req,
            budget_id=budget.budget_id,
            chain_id=chain_id,
        )

        # ── 输出多维裁决 ───────────────────────────────────────
        status = "✓" if token.verdict == Verdict.ALLOW else "✗"
        if is_last_few and token.verdict == Verdict.BLOCK:
            status = "⊘"

        print(f"\n  [{status}] 步骤 {i}: {name} ¥{amount}")
        print(f"      embodied consistency 因果一致性: {token.embodied_consistency_score:.2f}")
        print(f"      budget governance 预算充足性: {token.budget_adequacy_score:.2f}")
        print(f"      source-chain integrity 来源链完整: {token.source_chain_integrity_score:.2f}")
        print(f"      组合裁决: {token.verdict.value}")
        if token.reason_code != "ALL_CLEAR":
            print(f"      原因码: {token.reason_code}")
            print(f"      详情: {token.reason_detail}")
        if token.budget_deduction:
            print(f"      预算扣减: {token.budget_deduction}")
        if token.constraints.get("reasons"):
            print(f"      约束原因: {token.constraints['reasons']}")

    # ═══════════════════════════════════════════════════════════
    # 最终状态
    # ═══════════════════════════════════════════════════════════
    final = rt.get_budget(budget.budget_id)
    print(f"\n{'='*60}")
    print(f"最终状态")
    print(f"{'='*60}")
    print(f"[budget governance] 预算剩余: {final.remaining}")
    print(f"[budget governance] 预算状态: {final.status.value}")

    chain_result = rt.verify_chain(chain_id)
    print(f"\n[source-chain integrity] 来源链长度: {chain_result.chain_length}")
    print(f"[source-chain integrity] 来源链有效: {chain_result.valid}")
    print(f"[source-chain integrity] 链哈希: {chain_result.chain_hash[:24]}...")

    if not chain_result.valid:
        for b in chain_result.breaks:
            print(f"  [断裂] 位置={b.position} 标签={b.tag.value} 详情={b.detail}")

    # ═══════════════════════════════════════════════════════════
    # 撤销传播演示（budget governance S4）
    # ═══════════════════════════════════════════════════════════
    print(f"\n[budget governance·S4] 撤销授权 — 传播验证")
    affected = rt.revoke_budget(budget.budget_id, source="cfo_revoked")
    print(f"  受影响预算: {len(affected)}")
    revoked = rt.get_budget(budget.budget_id)
    print(f"  根预算状态: {revoked.status.value}")


if __name__ == "__main__":
    main()