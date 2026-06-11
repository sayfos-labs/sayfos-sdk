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
