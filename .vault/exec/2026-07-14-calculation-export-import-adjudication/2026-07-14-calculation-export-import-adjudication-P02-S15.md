---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S15'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Adjudicate Modelo 840 registry field and binding work only if machine-file generation is a confirmed product mandate

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/840/`
- `.vault/reference/`

## Description

Confirm that the current `2003-y-siguientes` registry revision in
`src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/revision.toml`
uses `valid_from = 2003-09-19`. Confirm that the reviewed `aeat-dr-840` PDF
record design in `src/cadrumo/_data/registry/aeat/legal/iae.toml` applies
from the same `2003-09-19` date, aligned with the revision start.

Inspect the accepted ADR, research, reference register, and plan. Legacy
wording explicitly identifies missing layout-binding rows for Modelo 840, but
naming a known gap in optional registry data is not an accepted decision or
explicit current product goal to build machine-file generation.

Inspect the Modelo 840 registry and the generic export engine. The revision
has no `export_layouts` data and no layout-binding rows. The shared
`resolve_export_layout` and `export_draft` paths remain canonical and fail
closed when no layout is exposed. No real Modelo 840 golden outbound payload
or mutation-sensitive export/parse round trip exists.

## Outcome

### `modelo-840-outbound-2003-open` | `mandate-gated`

- **Candidate:** Modelo 840 outbound fichero generation from `2003-09-19`
  with an open end under revision `2003-y-siguientes`.
- **Mandate:** `conditional`. Legacy wording explicitly names the missing
  layout-binding rows as a known gap, which is closer to an intent signal
  than silence, but no accepted decision or explicit current product goal
  establishes machine-file generation as required today.
- **Exact authority window:** `aeat-dr-840` is a reviewed AEAT PDF record
  design registered from `2003-09-19`, aligned exactly with the revision
  start, and covers this candidate window with an open end.
- **Canonical implementation state:** `gap` only in optional Modelo 840
  layout and binding data: no export layout or layout-binding rows are
  registered. The canonical generic resolver, renderer, and parser are
  delivered and refuse the absent layout.
- **Real evidence or specimen:** `missing`. The reviewed record-design PDF is
  available as authority, but no real Modelo 840 golden outbound payload or
  mutation-sensitive round trip exists.
- **Retirement:** `false`.
- **Evidence block:** `true`; taxonomy precedence selects `mandate-gated`
  before any evidence-gated state because the mandate remains conditional,
  not proven.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm machine-file generation as an explicit current
  product mandate for Modelo 840 before transcribing any registry field or
  layout-binding row, authoring a layout, or building a golden test.

## Notes

- Grounding used the accepted adjudication contract, exact Modelo 840
  registry/legal files, generic exporter boundaries, and the existing
  reference register entry for Modelo 840.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
