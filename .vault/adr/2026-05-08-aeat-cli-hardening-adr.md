---
tags:
  - '#adr'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-04-24-aeat-cli-wireframe-research]]'
  - '[[2026-05-02-aeat-cli-redesign-research]]'
  - '[[2026-05-12-cli-design-research]]'
  - '[[2026-06-04-aeat-cli-hardening-research]]'
---

# `aeat-cli-hardening` adr

## Context

The live `aeat` surface exposes command-shape drift, duplicated policy,
and missing backend APIs around configuration, output, and workflow
ownership. The hardening plan turns that audit inventory into a
backend-first rollout that preserves a thin CLI boundary.

## Decision

- Keep the CLI layer limited to argument parsing, dispatch, formatting,
  and exit behavior.
- Bring missing backend services into scope whenever the current CLI
  surface reimplements or shadows core behavior.
- Gate every user-facing command change behind live verification and
  meaningful, non-tautological tests.

## Consequences

- The CLI becomes easier to reason about because policy migrates to
  centralized backend code.
- Hardening work can legitimately include backend implementation, not
  just entrypoint edits.
- Future CLI slices inherit stricter verification and ownership rules.
