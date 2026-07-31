---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:8ea27ebd9f84ffe7fdd8937a63dcd09b352c38bfbab490915abdf79e31fc70fb'
step_id: 'S06'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Reconcile Modelo 190 2024 and 2025 design windows before deciding any outbound mandate

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/190/`
- `.vault/reference/`

## Description

Reconcile Modelo 190 outbound generation as separate 2024 and 2025-and-following
authority windows while preserving the single `2024-y-siguientes` calculation
revision.

Confirm that the current revision in
`src/cadrumo/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes/revision.toml`
starts on `2024-01-01` and covers annual period `0A`. Confirm that the reviewed
`aeat-dr-190-2025` record design in
`src/cadrumo/_data/registry/aeat/legal/irpf.toml` applies from `2025-01-01`.
The official corpus manifest also bundles and hashes the distinct 2024 PDF
updated by Orden HAC/1432/2024, but no 2024 source identifier is registered in
the legal catalogue or revision source references.

Retain the accepted declaration-extraction ADR's structural finding: its
task-32 audit compared the 2024 and 2025 EDI specifications and found the Tipo 1
and Tipo 2 layouts identical, with no field additions, removals, or
renumbering. That finding supports one registry revision; it does not turn the
registered 2025 source into 2024 authority or eliminate the need to catalogue
the bundled 2024 source before any exact-window implementation claim.

Inspect the Modelo 190 registry, generic export engine, and real-behaviour
tests. The revision has filing linkage and parity metadata but no
`export_layouts` data. The canonical `resolve_export_layout` and `export_draft`
paths remain generic and fail closed when no layout is exposed. Modelo 190
registry tests validate source-tier separation and the current snapshot, while
the real mutation-sensitive fichero-BOE round-trip suite covers Modelos 130,
303, and 390 only. No real Modelo 190 golden outbound payload exists.

## Outcome

### `modelo-190-outbound-2025-open` | `mandate-gated`

- **Candidate:** Modelo 190 outbound fichero generation for annual filing year
  2025 and following under revision `2024-y-siguientes`, from `2025-01-01`
  with an open end.
- **Mandate:** `unproven`. Legacy discovery and generic export-routing wording
  identify a possible outbound surface, but no accepted decision or explicit
  current product goal requires local Modelo 190 fichero generation. Filing
  linkage and source availability are not a mandate.
- **Exact authority window:** `aeat-dr-190-2025` is a reviewed AEAT PDF record
  design registered from `2025-01-01` with an open end and covers this window.
  The revision's earlier 2024 start does not broaden that source.
- **Canonical implementation state:** `gap` only in optional Modelo 190 layout
  data: no export layout is registered. The canonical generic resolver,
  renderer, and parser are delivered and refuse the absent layout. Because the
  required product capability is unproven, optional data absence does not
  satisfy the gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed 2025 record-design PDF
  is available as authority, but there is no real Modelo 190 golden outbound
  payload or mutation-sensitive export/parse round trip. The generic real
  round-trip suite does not include Modelo 190.
- **Retirement:** `false`; no accepted retirement or supersession applies.
- **Evidence block:** `true`; the missing artefact is a real Modelo 190 golden
  payload derived from the 2025 design and round-tripped through the canonical
  exporter/parser with mutation detection.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 190 fichero generation for 2025 and following. Until then,
  create no layout, renderer, parser, test, or successor implementation step.

### `modelo-190-outbound-2024` | `mandate-gated`

- **Candidate:** Modelo 190 outbound fichero generation for annual filing year
  2024 under revision `2024-y-siguientes`, from `2024-01-01` through
  `2024-12-31`.
- **Mandate:** `unproven`. The same legacy discovery and routing wording does
  not establish a current product requirement for this window. A bundled
  source, filing link, or accepted structural comparison cannot create one.
- **Exact authority window:** `missing from the registered authority
  catalogue`. The official corpus manifest bundles and hashes
  `DISENOS_LOGICOS_190-2024.pdf`, updated by Orden HAC/1432/2024, but the
  revision and legal catalogue register only `aeat-dr-190-2025` from
  `2025-01-01`. The accepted ADR's finding that the 2024 and 2025 Tipo 1/Tipo 2
  structures are identical supports one revision but does not register the
  2024 source or authorize backward projection.
- **Canonical implementation state:** `gap` only in optional Modelo 190 layout
  data: no export layout is registered. The delivered generic resolver,
  renderer, and parser fail closed. With no proven required capability or
  registered exact-window authority, this is not an admitted canonical gap.
- **Real evidence or specimen:** `missing`. There is no real 2024 Modelo 190
  golden outbound payload or mutation-sensitive export/parse round trip. The
  filed 2024 declaration-PDF specimen used by extraction is a different
  evidence surface and cannot serve as an outbound golden fichero.
- **Retirement:** `false`; 2024 remains an authority-reconciliation window, not
  a retired surface.
- **Evidence block:** `true`; the missing outbound artefact is a real 2024
  golden fichero grounded in the exact 2024 record design.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 190 fichero generation for 2024. Until then, do not catalogue a
  source for implementation, extrapolate the 2025 source, author a layout or
  golden test, or create successor implementation work.

## Notes

- Grounding used the accepted adjudication and declaration-extraction ADRs,
  shared evidence contract, exact Modelo 190 registry/source/corpus files,
  generic exporter boundaries, and direct test/fixture inventory. The initial
  bounded `vaultspec-rag` query returned unrelated export documentation, so no
  semantic hit was treated as evidence; exact source inspection supplied every
  adjudication claim.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
