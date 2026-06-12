# Contributing to Sayfos SDK

Thank you for your interest in contributing to Sayfos SDK.

Sayfos SDK is the public community reference implementation for agent runtime
control. Contributions are welcome when they improve the SDK, examples,
documentation, adapters, or tests while preserving the project's security
focus and public API clarity.

## Contribution License

By submitting a contribution to this repository, you agree that your
contribution is submitted under the Apache License, Version 2.0, unless you
clearly state otherwise in writing before the contribution is accepted.

You also confirm that you have the right to submit the contribution. Do not
submit code, documentation, model outputs, datasets, proprietary snippets, or
third-party materials unless you have the legal right to contribute them under
the project license.

## Developer Certificate of Origin

This project uses the Developer Certificate of Origin (DCO) as a lightweight
contribution certification process.

Each commit should include a Signed-off-by line:

```bash
git commit -s -m "Describe your change"
```

The sign-off means that you certify the statements in DCO.md for that
contribution.

## What We Accept

Good contributions include:

- Bug fixes with tests or clear reproduction notes.
- Documentation improvements that make the SDK easier to adopt.
- Small, focused examples showing real agent runtime-control scenarios.
- Lightweight reference engines and adapters that fit the public SDK boundary.
- Compatibility fixes for supported Python versions and frameworks.

Large changes should start as an issue or discussion before a pull request.

## What We Do Not Accept

Please do not submit:

- Code copied from another project without compatible licensing.
- Confidential, proprietary, or employer-owned code without authorization.
- Generated code or model output that you cannot license to this project.
- Changes that imply Sayfos certification, enterprise support, or official
  gateway status.
- Heavy enterprise gateway, managed policy engine, control-plane, or
  certification-service code unless a maintainer explicitly asks for it.

## Public SDK Boundary

This repository contains public interfaces, reference objects, lightweight
verification engines, examples, and adapters.

Contributing to this community SDK does not grant rights to use Sayfos
trademarks, certification marks, enterprise gateways, managed services,
commercial offerings, private roadmaps, or non-public implementations.

See TRADEMARK.md and PATENT_NOTICE.md for additional notices.

## Contributor Patent License Grant

Every contributor whose pull request is merged into this repository
automatically receives a **free, royalty-free, non-transferable patent
license** from the Sayfos patent holders.  This license permits the
contributor to integrate Sayfos SDK into their own products and services
without paying patent royalties, subject to the limitations below.

The intent is simple: *You help build the SDK, you can use it in your
product — for free.*

### License Scope

The license covers **integration and use of Sayfos SDK as a dependency**
inside the contributor's own product.  It does **not** grant a separate
right to extract the SDK's protocol semantics and re-implement a competing
runtime-control product outside the Sayfos SDK codebase.

### License Limitations

The free patent license granted to contributors **automatically terminates**
when any of the following thresholds is met by the contributor's product
that integrates Sayfos SDK:

| Threshold | Applies to |
|-----------|-----------|
| Annual active end-users ≥ **50,000** | Consumer-facing products (B2C apps, mobile apps) |
| Annual contract customers ≥ **20** enterprise entities | Business-facing products (SaaS, middleware, gateways) |
| Annual revenue related to the integrating product ≥ **¥2,000,000 CNY** | Any product (fallback) |

If a contributor's product exceeds any of the above thresholds, the
contributor must contact the Sayfos rights holders within 30 days to agree
on commercially reasonable patent license terms.  The thresholds are
intentionally set high enough to let individual developers and small teams
grow without worrying about royalties, while ensuring that large-scale
commercial deployments contribute back to the ecosystem.

### Non-Transferability

This license is granted to the contributor in person (or the single
corporate entity they represent).  It may not be transferred, sublicensed,
or assigned.  If the contributor's product line is acquired, the acquirer
must negotiate its own license with the Sayfos rights holders.

## Pull Request Guidelines

Before opening a pull request:

1. Keep the change focused and easy to review.
2. Add or update tests when behavior changes.
3. Keep public-facing files in English.
4. Avoid internal planning terms, unpublished roadmap names, or private
   business materials.
5. Run the test suite when practical:

```bash
python -m pytest tests/ -q
```

Maintainers may edit, squash, rebase, or decline contributions to protect the
project's security model, API clarity, legal boundary, and long-term direction.
