---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:161151b0b7900084a35324fc0b105c8c36b986a599df95533eb7854eb9ab33bc'
step_id: 'S07'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Enforce exact-one deadline ownership through canonical select_revision including period-sensitive cutovers

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Resolve every deadline filing coordinate through the canonical `select_revision` authority.
- Reject a deadline nested beneath any revision other than the law-selected owner.
- Accumulate no-owner and ambiguous-owner failures through the registry validator contract.
- Exercise the rule with an isolated same-year, period-sensitive revision cutover.
- Route the ownership invariant through `RegistryValidator` before authority construction.
- Audit semantic redeclarations and retain the existing selector, period, cadence, and resolver authorities.

## Outcome

Deadline rows now carry an exact-one revision-ownership invariant at registry build.
The containing revision is asserted only after selection from the window's canonical
`Period` coordinate, so it cannot influence the selection. Focused ownership,
uniqueness, and temporal tests passed, as did Ruff on every modified Python file.
Independent review found no production defect or duplicate authority; its medium test
coverage finding was closed with a combined missing-owner and ambiguous-owner bite.

## Notes

The bundled corpus is intentionally not asserted green in this step: the duplicate and
non-owner rows inventoried by the campaign remain until the approved corpus-repair
steps. Isolated fixtures prove this invariant independently of those known failures.
Vaultspec RAG confirms this step introduced no selector, parser, cadence classifier, or
filing-window resolver redeclaration. Pre-existing overview matching and deduplication
surfaces remain scheduled for the approved consumer-parity steps.
