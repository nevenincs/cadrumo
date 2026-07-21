---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Adjudicate Modelo 308 export only for the 2019-and-following authority window and gate earlier revisions

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/308/`
- `.vault/reference/`

## Description

Adjudicate Modelo 308 outbound generation as separate 2009-2018 and
2019-and-following authority windows rather than extending a later record design
across the full registry revision.

Confirm that the current `2009-y-siguientes` revision in
`src/cadrumo/_data/registry/aeat/modelos/308/revisions/2009-y-siguientes/revision.toml`
starts on `2009-01-01` and uses the `AD-HOC` period. Confirm that the reviewed
`aeat-dr-308-2019` XLS record design in
`src/cadrumo/_data/registry/aeat/legal/iva.toml` applies from `2019-01-01` with
an open end. The `boe-modelo-308-2008-form` authority grounds the form and
obligation but is not a machine-file record design for 2009-2018.

Inspect the Modelo 308 registry and generic export path. The revision has a
filing application link and a record-design parity reference but no
`export_layouts` data. The shared `resolve_export_layout` and `export_draft`
paths remain the canonical resolver/renderer and fail closed when no layout is
exposed; no Modelo-specific exporter is missing.

Inspect direct tests and evidence inventory. Modelo 308 registry tests validate
the committed definition, 2009 revision start, recent snapshots, source
projection, AD-HOC schedule, and filing/parity linkage. The real
mutation-sensitive fichero-BOE round-trip suite covers Modelos 130, 303, and
390 only. No real Modelo 308 golden outbound payload exists for either window.

## Outcome

### `modelo-308-outbound-2019-open` | `mandate-gated`

- **Candidate:** Modelo 308 outbound fichero generation for AD-HOC filings from
  `2019-01-01` with an open end under revision `2009-y-siguientes`.
- **Mandate:** `conditional`. The legacy goal asks for deeper export/file layout
  support only where required, but no accepted decision or explicit current
  product goal requires local Modelo 308 fichero generation. Filing linkage,
  parity metadata, and source availability do not establish that mandate.
- **Exact authority window:** `aeat-dr-308-2019` is a reviewed AEAT XLS record
  design registered from `2019-01-01` with an open end and covers this candidate
  window. The revision's 2009 start does not broaden the source.
- **Canonical implementation state:** `gap` only in optional Modelo 308 layout
  data: no export layout is registered. The canonical generic resolver,
  renderer, and parser are delivered and refuse the absent layout. Because the
  required capability is unproven, optional data absence does not satisfy the
  gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed 2019 record-design XLS
  is available as authority, but there is no real Modelo 308 golden outbound
  payload or mutation-sensitive export/parse round trip. The generic real
  round-trip suite does not include Modelo 308.
- **Retirement:** `false`; no accepted retirement or supersession applies.
- **Evidence block:** `true`; the missing artefact is a real Modelo 308 golden
  payload derived from the 2019-and-following design and round-tripped through
  the canonical exporter/parser with mutation detection.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 308 fichero generation for 2019 and following. Until then,
  create no layout, renderer, parser, test, registry split, or successor
  implementation step.

### `modelo-308-outbound-2009-2018` | `mandate-gated`

- **Candidate:** Modelo 308 outbound fichero generation for AD-HOC filings from
  `2009-01-01` through `2018-12-31` under revision
  `2009-y-siguientes`.
- **Mandate:** `conditional`. The same legacy goal is conditional on a product
  need that has not been established for this historical window. Registry
  coverage, a filing link, and later source availability are not a mandate.
- **Exact authority window:** `missing`. The registered
  `aeat-dr-308-2019` record design starts on `2019-01-01` and cannot support
  2009-2018. `boe-modelo-308-2008-form` grounds the form and legal obligation,
  not an exact machine-file layout for this outbound candidate.
- **Canonical implementation state:** `gap` only in optional historical layout
  data: no export layout is registered. The delivered generic resolver,
  renderer, and parser fail closed. With no proven required capability or
  exact-window record-design authority, this is not an admitted canonical gap.
- **Real evidence or specimen:** `missing`. There is no exact-window official
  record design and no real Modelo 308 golden outbound payload for 2009-2018.
  The 2019 XLS and other-model round trips cannot be extrapolated backward.
- **Retirement:** `false`; this is an authority-limited historical window, not a
  retired surface.
- **Evidence block:** `true`; a real golden payload grounded in an exact
  2009-2018 official record design is unavailable.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 308 fichero generation for 2009-2018. Until then, do not seek
  historical layout authority for implementation, extrapolate the 2019 design,
  author registry data or tests, or create successor implementation work.

## Notes

- Grounding used the accepted adjudication contract, exact Modelo 308
  registry/legal files, generic exporter boundaries, and direct test/fixture
  inventory. The bounded `vaultspec-rag` result identified only generic export
  internals and the dormant Modelo 308 matrix classification; exact source
  inspection supplied the authority and window findings.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
