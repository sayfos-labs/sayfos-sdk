# Contributing to Sayfos SDK

Thank you for your interest in contributing to Sayfos SDK.

Sayfos SDK is the public community reference implementation for agent runtime
control. Contributions are welcome when they make the SDK easier to use,
easier to integrate, and safer for real automated execution workflows.

## Why Contribute?

When your pull request is accepted, your work becomes part of the Apache-2.0
licensed SDK. That means you and everyone else can continue to use, modify,
fork, and build products or services with the licensed SDK code without
registration, usage thresholds, revenue caps, or expiration.

The Apache-2.0 patent grant applies to the licensed SDK code and accepted
contributions. You do not need a separate patent license to use Sayfos SDK as
a dependency in your own projects.

This covers integration and use of the SDK code. It does not cover independent
implementations of patented methods outside this SDK. See PATENT_NOTICE.md for
details.

## Contribution License

By submitting a contribution to this repository, you agree that your
contribution is submitted under the Apache License, Version 2.0, unless you
clearly state otherwise in writing before the contribution is accepted.

You also confirm that you have the right to submit the contribution under the
project license.

## What We Welcome

Good contributions include:

- Bug fixes with tests or clear reproduction notes.
- Documentation improvements that make the SDK easier to adopt.
- Small, focused examples showing real agent runtime-control scenarios.
- Lightweight reference engines and adapters that fit the public SDK boundary.
- Compatibility fixes for supported Python versions and frameworks.

Large changes should start as an issue or discussion before a pull request.

## Pull Request Guidelines

Before opening a pull request:

1. Keep the change focused and easy to review.
2. Add or update tests when behavior changes.
3. Keep public-facing files in English.
4. Run the test suite when practical:

```bash
python -m pytest tests/ -q
```

See TRADEMARK.md and PATENT_NOTICE.md for additional notices.
