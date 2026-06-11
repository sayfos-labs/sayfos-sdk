# Governance

Sayfos SDK is maintained as the official upstream community reference
implementation of the public Sayfos SDK interfaces.

## Maintainers

Maintainers are responsible for:

- Reviewing and merging pull requests.
- Protecting the public SDK boundary.
- Preserving API clarity and backwards compatibility where practical.
- Keeping security-sensitive behavior understandable and testable.
- Deciding whether a change belongs in the community SDK or in a separate
  commercial, managed, or enterprise offering.

Community contributions are welcome, but contribution does not automatically
grant maintainer status, project administration rights, trademark rights,
certification rights, commercial licensing authority, or authority to represent
the project.

## Decision Process

Routine documentation, example, adapter, and bug-fix changes may be accepted
by maintainer review.

Changes to the following areas require explicit maintainer approval:

- Core semantic objects and public APIs.
- Runtime adjudication behavior.
- Source-chain, budget, preflight, or embodied-consistency engines.
- License, patent, trademark, contribution, governance, or security notices.
- Claims about official compatibility, certification, gateway status, or
  enterprise services.

Maintainers may request design notes, tests, threat-model discussion, or a
smaller change set before accepting a pull request.

## Project Boundary

This repository contains the community SDK: public interfaces, reference
objects, lightweight engines, examples, and adapters.

The following are outside the community SDK unless explicitly added by
maintainers:

- Enterprise gateways.
- Managed policy engines.
- Production control planes.
- Certification services and test suites.
- Commercial support offerings.
- Private deployment services.

## Trademarks and Official Status

The Sayfos name, logos, certification marks, and official service names are
not granted by contribution, fork, pull request, issue participation, or use of
the Apache 2.0 license.

Forks and derivative projects must not imply that they are the official Sayfos
SDK, Sayfos Enterprise, a certified Sayfos gateway, or an authorized Sayfos
service unless separately approved in writing.

See TRADEMARK.md for details.
