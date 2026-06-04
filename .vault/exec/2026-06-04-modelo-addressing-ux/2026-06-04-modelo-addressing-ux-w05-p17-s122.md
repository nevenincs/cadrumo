---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
step_id: 'S122'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S122` final blast-radius matrix

Step scope: `.vault/exec/2026-06-04-modelo-addressing-ux`.

## Description

- Classify changed modelo addressing surfaces after implementation, docs, locales, and verification.
- Separate common natural-key workflow surfaces from exact-ID advanced compatibility surfaces.
- Record residual risks and blocked verification lanes.

## Outcome

Final blast-radius classification:

- Common natural-key surfaces: `work create`, `work calculate`, `work list`,
  `work status`, `work discard`, `work revisions`, `work revision`,
  `work history`, `work verify`, `work file`, top-level `modelo reconcile`,
  `modelo reconcile-from-justificante`, and `modelo export`.
- Command-specific revision defaults: calculate creates/sets current draft,
  verify selects current draft, file selects current verified, and export prefers
  filed then verified/exportable.
- Exact-ID advanced compatibility: raw `work_unit_id` and
  `calculation_revision_id` arguments remain for direct audit, replay,
  automation, and legacy scripts.
- Internal application services: exact IDs remain authoritative below the CLI
  selector boundary for persistence, filing, export, reconciliation, history,
  taxation comparison, result summaries, and state projection.
- Payloads and machine outputs: structured JSON still exposes authoritative IDs,
  plus short IDs where operator display needs stable breadcrumbs.
- Locales and help: user-facing guidance points standard workflows back to
  natural-key commands while exact-ID parameter help remains for advanced routes.
- Narrative docs: tutorial, getting started, quickstart, Modelo 303/390,
  reconcile, and filing-spine pages use modelo/year/period for the common path.
- Generated CLI reference: regenerated from live command signatures and therefore
  still documents exact-ID arguments where those arguments intentionally remain.

Closure evidence sources:

- `W05.P17.S119`: exact raw-ID leakage audit.
- `W05.P17.S120`: semantic raw-ID leakage audit through `vaultspec-rag`.
- `W05.P17.S121`: source-tree file-discovery blast-radius inventory.
- `W05.P07.S75` through `W05.P07.S78`: focused application, CLI, docs, and
  feature-surface verification gates.

## Notes

Residual verification constraint: `vaultspec-core vault check all --feature
modelo-addressing-ux` still rejects the L3 execution-record filenames required by
the execution skill. The focused plan check, application tests, CLI tests, docs
tests, and scoped ruff gate are recorded separately as passed.
