"""

Demonstrates proxy-authority budget governance for a code agent:
  - Budget constrains repository scope, directory, file types, test pass rate,
    static scan results, credential access, and deployment permissions.
  - Allowed changes consume budget; touching credentials or security config
    triggers downgrade, freeze, or block.
  - Implements Agent 数字执行质量预算 dimensions.

Corresponds exactly to:

Run: python examples/code_agent_deploy.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    rt = SayfosRuntime()

    # ── 1. Create deployment budget per patent embodiment ───────
    #   测试通过率、静态扫描结果、部署权限、生产配置修改预算、
    #   凭证访问限制和人工审查要求"
    budget = rt.create_budget(
        owner_id="code-agent",
        quotas={
            "code_changes": 20,          # max file modifications
            "security_touches": 3,        # credential/config touches before freeze
            "deploy_permission": 1,       # deploy tokens
            "tool_calls": 50,
            "test_pass_rate": 0.95,       # minimum acceptable test pass rate
        },
    )
    print(f"[预算] code-agent: {budget.quotas}")

    chain_id = rt.create_chain()

    # ── 2. Normal code change (within scope) ────────────────────
    #   系统可允许生成提交或合并请求，并扣减代码变更预算"
    for i in range(3):
        decl = ActionDeclaration(
            actor_type="code_agent",
            action_type="write",
            target=f"src/module/file_{i}.py",
            parameters={"lines_changed": 50, "test_pass": True},
            root_authorization_ref="auth://devops/lead",
            task_lineage_ref=f"task://sprint-42/refactor-{i}",
            tool_reason_ref="reason://code-review-passed",
            risk_level=1,
        )
        req = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
        )
        token = rt.adjudicate(req, budget_id=budget.budget_id, chain_id=chain_id)
        print(f"  [{token.verdict.value}] {decl.target}: {token.reason_code}")

    # ── 3. Sensitive config change — detect credential touch ────
    #   或跨仓库文件，系统可降低自主执行等级、冻结部署令牌、
    #   要求人工审查或阻断动作"
    sensitive = ActionDeclaration(
        actor_type="code_agent",
        action_type="write",
        target="config/production/secrets.yaml",
        parameters={"lines_changed": 3, "test_pass": True},
        root_authorization_ref="auth://devops/lead",
        task_lineage_ref="task://sprint-42/hotfix",
        risk_level=9,  # triggers risk-weighted budget consumption
    )
    req = IntentVerificationRequest(
        action=sensitive,
        touch_events=5,
        screen_on=True,
        device_held=True,
    )
    token = rt.adjudicate(req, budget_id=budget.budget_id, chain_id=chain_id)

    print(f"\n  [敏感文件] {sensitive.target}")
    print(f"  裁决: {token.verdict.value}")
    print(f"  原因: {token.reason_code}")
    print(f"  约束: {token.constraints}")

    # ── 4. CI/CD config change — blocked ────────────────────────
    cicd = ActionDeclaration(
        actor_type="code_agent",
        action_type="write",
        target=".github/workflows/deploy.yml",
        parameters={"lines_changed": 10},
        root_authorization_ref="auth://devops/lead",
        task_lineage_ref="task://sprint-42/ci-update",
        risk_level=8,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=cicd, touch_events=5, screen_on=True, device_held=True),
        budget_id=budget.budget_id, chain_id=chain_id,
    )
    print(f"\n  [CI/CD] {cicd.target}")
    print(f"  裁决: {token.verdict.value}")
    print(f"  原因: {token.reason_code}")

    b = rt.get_budget(budget.budget_id)
    print(f"\n[数字执行质量预算] consumed={b.consumed}, remaining={b.remaining}")

    verification = rt.verify_chain(chain_id)
    print(f"[来源链] 有效={verification.valid}, 长度={verification.chain_length}")


if __name__ == "__main__":
    main()