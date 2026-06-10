"""
Sayfos SDK example: code-agent deployment guard.

Demonstrates budget governance for a code agent. The budget constrains file
changes, security-sensitive touches, deployment permission, tool calls, and
test quality. Allowed changes consume budget; sensitive changes trigger
review, downgrade, freeze, or block behavior.

Run: python examples/code_agent_deploy.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    rt = SayfosRuntime()

    budget = rt.create_budget(
        owner_id="code-agent",
        quotas={
            "code_changes": 20,
            "security_touches": 3,
            "deploy_permission": 1,
            "tool_calls": 50,
            "test_pass_rate": 0.95,
        },
    )
    print(f"[Budget] code-agent: {budget.quotas}")

    chain_id = rt.create_chain()

    for i in range(3):
        decl = ActionDeclaration(
            actor_type="code_agent",
            action_type="write",
            target=f"src/module/file_{i}.py",
            parameters={"lines_changed": 50, "test_pass": True},
            root_authorization_ref="auth://devops/lead",
            task_lineage_ref=f"task://sprint-42/refactor-{i}",
            tool_reason_ref="reason://code-review-passed",
            decision_token_ref="token://repository-approved",
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

    sensitive = ActionDeclaration(
        actor_type="code_agent",
        action_type="write",
        target="config/production/secrets.yaml",
        parameters={"lines_changed": 3, "test_pass": True},
        root_authorization_ref="auth://devops/lead",
        task_lineage_ref="task://sprint-42/hotfix",
        tool_reason_ref="reason://urgent-hotfix",
        decision_token_ref="token://repository-approved",
        risk_level=9,
    )
    req = IntentVerificationRequest(
        action=sensitive,
        touch_events=5,
        screen_on=True,
        device_held=True,
    )
    token = rt.adjudicate(req, budget_id=budget.budget_id, chain_id=chain_id)

    print(f"\n  [Sensitive file] {sensitive.target}")
    print(f"  verdict: {token.verdict.value}")
    print(f"  reason_code: {token.reason_code}")
    print(f"  constraints: {token.constraints}")

    cicd = ActionDeclaration(
        actor_type="code_agent",
        action_type="write",
        target=".github/workflows/deploy.yml",
        parameters={"lines_changed": 10},
        root_authorization_ref="auth://devops/lead",
        task_lineage_ref="task://sprint-42/ci-update",
        tool_reason_ref="reason://deployment-update",
        decision_token_ref="token://repository-approved",
        risk_level=8,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=cicd,
            touch_events=5,
            screen_on=True,
            device_held=True,
        ),
        budget_id=budget.budget_id,
        chain_id=chain_id,
    )
    print(f"\n  [CI/CD] {cicd.target}")
    print(f"  verdict: {token.verdict.value}")
    print(f"  reason_code: {token.reason_code}")

    current = rt.get_budget(budget.budget_id)
    print(f"\n[Execution-quality budget] consumed={current.consumed}, remaining={current.remaining}")

    verification = rt.verify_chain(chain_id)
    print(f"[Source chain] valid={verification.valid}, length={verification.chain_length}")


if __name__ == "__main__":
    main()
