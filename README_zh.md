# Sayfos SDK

Sayfos SDK 是一个面向 AI Agent 和自动化执行体的轻量级运行时安全 SDK。

它提供动作声明、来源链、预算治理、计划预验真、提示注入隔离、裁决令牌等基础对象和参考实现，用于在 Agent 调用工具、API、数据系统、云资源或具身执行端之前加一道机器可验证的准入控制。

本仓库是社区参考实现，不包含完整企业网关、托管控制平面或商业化策略引擎。

## 采用政策

Sayfos SDK 的目标是尽可能降低采用门槛。

你可以在个人项目、商业产品、内部工具、研究原型、开源项目和生产应用中使用本社区 SDK。使用 SDK 代码不需要注册、不需要报备、不需要付费计划、不依赖 Sayfos Cloud，也不需要签署额外贡献协议。

你也可以 fork、修改、再分发，并基于本 SDK 构建应用或服务，但需要遵守 Apache 2.0 许可证，并保留适用的许可证和声明文件。

开源许可证不授予 Sayfos 商标、认证标识、官方服务名称的使用权，也不允许将 fork 或派生项目表述为官方 Sayfos SDK、Sayfos Enterprise、认证 Sayfos 网关或授权 Sayfos 服务。

## 官方上游

本仓库是 Sayfos SDK 的官方上游参考实现：

```text
https://github.com/sayfos-labs/sayfos-sdk
```

如果你基于本项目开发自己的项目，可以说明其“基于公开 Sayfos SDK 接口”或“兼容公开 Sayfos SDK 接口”，但不要将其表述为官方上游项目。

## Sayfos 解决什么问题

| 没有 Sayfos | 使用 Sayfos |
| --- | --- |
| Agent 夜间循环调用 API，第二天才发现账单暴涨 | 预算上限可在第 51 次调用前拦截 |
| 事后没人知道 Agent 为什么转账 | 来源链可追踪授权、任务和调用理由 |
| 提示注入诱导 Agent 执行危险命令 | 执行前检查来源和运行时证据 |
| 多步骤计划到第 7 步才发现越界 | 计划预验真在第 1 步执行前发现风险 |
| 机器人执行命令但缺少物理现场证据 | 具身一致性检查数字动作与物理状态 |

## 快速安装

```bash
pip install sayfos-sdk
```

## 最小示例

```python
from sayfos import BudgetManager

budget_mgr = BudgetManager()
budget = budget_mgr.create_budget(
    owner_id="my-agent",
    quotas={"api_calls": 50, "cost_usd": 5.00},
)

for task in tasks:
    remaining = budget_mgr.get_remaining(budget.budget_id) or {}
    if remaining.get("api_calls", 0) <= 0:
        print("[Sayfos] budget exhausted, call blocked")
        break
    budget_mgr.consume(budget.budget_id, {"api_calls": 1, "cost_usd": 0.10})
    call_llm_api(task)
```

## 开源边界

社区 SDK 包含公共接口、参考对象、轻量验证引擎、示例和适配器。

企业网关、托管策略引擎、认证服务、生产控制平面和商业支持属于独立商业能力，不包含在本社区 SDK 中。

## 相关声明

- Apache 2.0：见 LICENSE
- 专利声明：见 PATENT_NOTICE.md
- 贡献规则：见 CONTRIBUTING.md
- DCO 签署：见 DCO.md
- 治理规则：见 GOVERNANCE.md
- 商标声明：见 TRADEMARK.md
