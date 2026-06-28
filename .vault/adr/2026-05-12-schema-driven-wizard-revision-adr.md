---
tags:
  - '#adr'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - '[[2026-05-12-schema-driven-wizard-revision-plan]]'
  - '[[2026-05-12-schema-driven-wizard-adr]]'
  - '[[2026-05-12-schema-driven-wizard-reference]]'
  - '[[2026-05-12-schema-driven-wizard-research]]'
  - '[[2026-06-04-schema-driven-wizard-revision-research]]'
---

# `schema-driven-wizard-revision` adr

## Context

The first schema-driven wizard slice landed the core architecture but left
review-confirmed debt in descriptor-driven flag derivation, locale
coverage, deleted-surface cleanup, and downstream test surfaces. The
revision slice exists to close that debt without redesigning the wizard.

## Decision

- Keep the original wizard ADR authoritative and use the revision slice to
  finish the accepted contract.
- Treat descriptor-driven CLI generation, locale completeness, and stale
  surface removal as required closure items.
- Encode each reviewer finding as an ordered execution step with explicit
  acceptance gates.

## Consequences

- The revision pass strengthens confidence in the wizard architecture
  without splintering the decision history.
- Review findings become first-class tracked work instead of informal TODOs.
- Downstream CLI and test regressions are resolved under the same wizard
  architecture that introduced them.
