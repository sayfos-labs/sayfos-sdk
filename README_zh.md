# Sayfos SDK

> 在 AI 和机器人动手之前，加上人类确认的门。

Sayfos SDK 是面向自动化执行体的轻量运行时准入控制层。在 AI Agent、代码代理、机器人或自动化系统触及你的钱、数据、云端或物理世界之前，加一道机器可验证的准入门。

---

## 四条治理线

| 治理线 | 回答的问题 |
|--------|-----------|
| **来源链** | 谁授权了这个动作？经过了哪些节点？ |
| **预算治理** | Agent 还剩多少调用额度？花完就停 |
| **计划预验真** | 10 步执行计划，第 7 步会越界吗？ |
| **具身验真** | 数字动作和物理证据一致吗？ |

---

## 5 分钟接入

```bash
pip install sayfos-sdk
```

```python
from sayfos import BudgetManager

# 设预算：50 次调用 / $5.00 上限
budget_mgr = BudgetManager()
budget_mgr.create_budget(
    owner_id="my-agent",
    quotas={"api_calls": 50, "cost_usd": 5.00},
)

budgets = budget_mgr.store.list_by_owner("my-agent")
budget_id = budgets[0].budget_id

for task in tasks:
    remaining = budget_mgr.get_remaining(budget_id) or {}
    if remaining.get("api_calls", 0) <= 0:
        print(f"[Sayfos] 预算耗尽，已拦截")
        break
    budget_mgr.consume(budget_id, {"api_calls": 1, "cost_usd": 0.10})
    call_llm_api(task)  # 你的真实 API 调用
```

---

## 开源地址

- **GitHub**：[github.com/sayfos-labs/sayfos-sdk](https://github.com/sayfos-labs/sayfos-sdk)
- **Gitee**：[gitee.com/sayfos-labs/sayfos-sdk](https://gitee.com/sayfos-labs/sayfos-sdk)
- **PyPI**：[pypi.org/project/sayfos-sdk](https://pypi.org/project/sayfos-sdk)

Apache 2.0 协议。社区版永久免费。
