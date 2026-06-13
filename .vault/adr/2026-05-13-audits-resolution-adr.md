---
tags:
  - '#adr'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-audits-resolution-plan]]'
  - '[[2026-05-13-eliminate-shims-audit]]'
  - '[[2026-05-13-schema-driven-wizard-ux-audit]]'
  - '[[2026-05-13-testing-framework-tautology-audit]]'
  - '[[2026-05-12-schema-driven-wizard-research]]'
  - '[[2026-04-17-pytest-only-testing-research]]'
  - '[[2026-06-04-audits-resolution-research]]'
---

# `audits-resolution` adr

## Context

Three 2026-05-13 audits landed together on the same branch and produced a
mixed backlog spanning strictness leaks, localization defects, wizard UX
issues, and test-discipline violations. The resolution slice needs one
record that authorizes grouped execution while keeping each audit origin
visible.

## Decision

- Resolve the audit backlog in grouped passes that preserve audit origin
  in the execution plan.
- Treat no-mocks discipline, locale correctness, and backend-boundary
  integrity as non-negotiable closure gates.
- Use the existing eliminate-shim and schema-driven-wizard decisions as
  upstream architectural anchors for this cleanup pass.

## Consequences

- The branch can clear a cross-audit backlog without losing provenance.
- Execution work remains accountable to the audit clusters that surfaced it.
- Test and UX fixes are evaluated as architecture work, not cosmetic debt.
