---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S05'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---




# Adjudicate Modelo 184 export only for the 2025-and-following authority window and gate earlier revisions

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/184/`
- `.vault/reference/`

## Description

Adjudicate Modelo 184 outbound generation as two non-overlapping authority
windows rather than treating the registry's `2015-y-siguientes` revision as
proof of one continuous export-layout authority.

Confirm the reviewed `aeat-dr-184-2025` record-design source in
`src/cadrumo/_data/registry/aeat/legal/atribucion-rentas.toml`. Its bundled PDF,
hash, size, and `applies_from = 2025-01-01` establish exact layout authority for
2025 and following only. Contrast that window with the registry revision in
`src/cadrumo/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes/revision.toml`,
whose `valid_from = 2015-10-30` and `year_from = 2015` predate the registered
record design. Do not project the 2025 format backward over filing years
2015-2024.

Inspect the Modelo 184 registry tree and the shared export path. The revision
has filing linkage and a workbook-parity reference but no `export_layouts`
data. `resolve_export_layout` in
`src/cadrumo/domain/calculations/registry/_export.py` remains the canonical
registry layout resolver, and `export_draft` in
`src/cadrumo/application/filing/_export.py` refuses a subview with no export
layout identifiers. No Modelo-specific renderer or alternate schema authority
is missing.

Inspect the real-behaviour evidence. The Modelo 184 registry tests validate the
committed revision, 2015 start, 2025 source projection, snapshots, and filing
linkage. The mutation-sensitive fichero-BOE round-trip suite proves the generic
renderer/parser with real payloads for Modelos 130, 303, and 390, but contains
no Modelo 184 case. The bundled 184 record-design PDF and parity metadata are
authority inputs, not a real golden outbound payload.

## Outcome

### `modelo-184-outbound-2025-open` | `mandate-gated`

- **Candidate:** Modelo 184 outbound fichero generation for filing years 2025
  and following under registry revision `2015-y-siguientes`, from
  `2025-01-01` with an open end.
- **Mandate:** `conditional`. The legacy goal permits export/file generation
  only where official filing support requires it, but no accepted decision or
  explicit current product goal requires local Modelo 184 fichero generation.
  The filing application link and electronic-presentation rules do not by
  themselves establish that product capability.
- **Exact authority window:** `aeat-dr-184-2025` is a reviewed AEAT PDF record
  design registered from `2025-01-01` with an open end. It covers this candidate
  window exactly; the wider registry revision does not enlarge its
  applicability.
- **Canonical implementation state:** `gap` only in optional Modelo 184 layout
  data: no export layout is registered. The canonical resolver and generic
  renderer/parser are delivered and fail closed when a revision exposes no
  layout. Because the required product capability is unproven, that optional
  data absence does not satisfy the gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed record-design PDF is
  available as layout authority, but no real Modelo 184 golden outbound payload
  or mutation-sensitive export/parse round trip exists. The real generic
  round-trip suite covers Modelos 130, 303, and 390, not 184.
- **Retirement:** `false`; no accepted retirement or supersession applies.
- **Evidence block:** `true`; the missing artefact is a real Modelo 184 golden
  outbound payload for the 2025-and-following design, with a
  mutation-sensitive round trip through the canonical exporter/parser.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 184 fichero generation for 2025 and following. Until then,
  create no layout, renderer, parser, test, or successor implementation step.

### `modelo-184-outbound-2015-2024` | `mandate-gated`

- **Candidate:** Modelo 184 outbound fichero generation for filing years
  2015-2024 under registry revision `2015-y-siguientes`, from the revision's
  `2015-10-30` start through `2024-12-31`.
- **Mandate:** `conditional`. The same legacy goal is conditional on a product
  need that has not been established for this historical window. Registry
  coverage, a filing link, and later source availability are not a mandate.
- **Exact authority window:** `missing`. The registered
  `aeat-dr-184-2025` authority starts on `2025-01-01` and cannot support
  2015-2024. The registry revision's earlier start and the 2015 legal form
  authority establish the obligation/form, not an exact historical machine-file
  record design.
- **Canonical implementation state:** `gap` only in optional historical layout
  data: no export layout is registered. The delivered generic resolver and
  renderer/parser fail closed. With neither a proven mandate nor exact-window
  layout authority, optional registry absence is not an admitted canonical gap.
- **Real evidence or specimen:** `missing`. There is no registered exact-window
  record design and no real golden Modelo 184 outbound payload for filing years
  2015-2024. The 2025 PDF and other-model real round trips cannot be
  extrapolated backward.
- **Retirement:** `false`; the historical window is authority-limited, not
  retired.
- **Evidence block:** `true`; a real, official-design-derived golden payload for
  the exact historical layout is unavailable.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 184 fichero generation for the 2015-2024 window. Until then,
  do not seek historical layout authority, extrapolate the 2025 design, or
  create registry, renderer, parser, test, or successor implementation work.

## Notes

- Grounding used the accepted adjudication ADR, plan, shared evidence contract,
  exact Modelo 184 registry/source files, generic exporter boundaries, and
  direct test/fixture inventory. The initial bounded `vaultspec-rag` call
  returned the governing registry-authored export ADR but timed out before the
  code query returned; exact source inspection completed the reconciliation.
- A focused verification command targeted the committed Modelo 184 registry,
  revision-window and source-projection tests plus the real generic exporter
  round-trip test. It exceeded the 30-second execution limit without emitting
  a pytest result, so this record makes no test-pass or test-failure claim.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
