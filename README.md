# Sayfos SDK

Sayfos SDK is an AI agent security SDK for runtime guardrails: tool-call
control, source-chain provenance, budget limits, plan preflight,
prompt-injection isolation, and adjudication tokens.

It provides reference data objects, verification hooks, and framework adapters
for checking automated actions before they reach tools, APIs, data systems,
cloud resources, or embodied endpoints.

This repository is a community reference implementation, not the full
enterprise gateway or managed control plane.

## Official Upstream

This repository is the official upstream reference implementation of the
Sayfos SDK:

```text
https://github.com/sayfos-labs/sayfos-sdk
```

Forks and derivative projects are welcome under the Apache 2.0 license, but
they must preserve applicable license and notice files and must not imply that
they are the official Sayfos SDK, Sayfos Enterprise, a certified Sayfos gateway,
or an authorized Sayfos service unless separately approved in writing.

If you build on this project, please identify your work as based on or
compatible with the public Sayfos SDK interfaces rather than as the official
upstream project.

## What Sayfos Helps With

Automated execution agents often need to answer three questions before a
high-risk action is allowed:

1. Does the action have a verifiable source chain?
2. Is the action still within its delegated budget and runtime authority?
3. Does the digital action have enough contextual or embodied evidence?

Sayfos SDK exposes common objects and lightweight reference engines for those
checks so developers can add runtime guardrails around AI agents, RPA systems,
workflow engines, coding agents, cloud-operation agents, robots, vehicle
agents, and IoT agents.

## Installation

```bash
pip install sayfos-sdk
```

With the LangChain adapter:

```bash
pip install sayfos-sdk[langchain]
```

With the development API server:

```bash
pip install sayfos-sdk[api]
```

## Quick Start

```python
from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosPipeline,
    Verdict,
)

declaration = ActionDeclaration(
    actor_type="langchain_tool",
    action_type="send_payment",
    target="acct_42",
    parameters={"amount": 150.0, "currency": "CNY"},
    root_authorization_ref="auth://user/alice",
    task_lineage_ref="task://report/step-3",
    risk_level=5,
)

request = IntentVerificationRequest(
    action=declaration,
    touch_events=12,
    screen_on=True,
    device_held=True,
    budget_remaining={"amount": 500.0, "tool_calls": 10},
)

pipeline = SayfosPipeline()
token = pipeline.evaluate(request)

if token.verdict != Verdict.ALLOW:
    raise RuntimeError(f"Blocked: {token.reason_code}")

result = execute_payment(**declaration.parameters)
```

## Standard Objects

The community SDK centers on a small set of machine-readable objects:

| Object | Role |
| --- | --- |
| ActionDeclaration | Proposed automated action |
| IntentVerificationRequest | Action plus runtime evidence |
| EmbodiedResponse | Contextual or embodied consistency result |
| Budget | Delegated runtime authority and quotas |
| PreflightPlan | Multi-step execution plan |
| ExecutionBoundary | Machine-readable plan or step boundary |
| AdjudicationToken | Binding verdict and constraints |
| AuditSummary | Machine-verifiable audit summary |

## Reference Verification Dimensions

| Dimension | What it checks |
| --- | --- |
| Source-chain integrity | Whether the action carries required provenance references |
| Budget governance | Whether the action is within delegated runtime authority |
| Plan preflight | Whether a multi-step plan stays within execution boundaries |
| Embodied consistency | Whether digital action evidence matches contextual or physical evidence |

The bundled engines are intentionally lightweight. Production deployments
should use durable storage, authenticated policy management, operational
monitoring, and stronger organization-specific decision logic.

## LangChain Adapter

```python
from sayfos.adapters.langchain import SayfosLangChainInterceptor, BlockedActionError

interceptor = SayfosLangChainInterceptor()

@interceptor.guard
@tool
def transfer_funds(amount: float, to: str) -> str:
    return f"Transferred {amount} to {to}"

try:
    transfer_funds(100.0, "acct_evil")
except BlockedActionError as e:
    print(f"Blocked: {e.token.reason_code}")
```

## CLI

```bash
sayfos verify --action '{"action_type":"payment","parameters":{"amount":100}}'
sayfos budget create --owner agent-1 --quotas '{"amount_cny":5000}'
sayfos plan preflight --plan '{"steps":[]}' --budget-id <budget-id>
```

## Open Source Boundary

This repository provides public interfaces, reference objects, lightweight
verification engines, examples, and adapters under Apache 2.0.

Enterprise gateway capabilities, managed policy engines, certification
services, production control planes, and commercial support are separate
offerings and are not provided by this community SDK.

## Notices

See LICENSE for the Apache 2.0 license.

See PATENT_NOTICE.md and TRADEMARK.md for additional patent and trademark
notices related to this project.
