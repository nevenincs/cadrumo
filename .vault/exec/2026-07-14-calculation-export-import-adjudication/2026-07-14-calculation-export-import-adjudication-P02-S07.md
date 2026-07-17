---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Reconcile Modelo 193 2024 and 2025 design windows before deciding any outbound mandate

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/193/`
- `.vault/reference/`

## Description

Reconcile Modelo 193 outbound generation as separate 2024 and 2025-and-following
authority windows while distinguishing required authority separation from an
unproven registry-schema split.

Confirm that the current registry revision in
`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2024-y-siguientes/revision.toml`
starts on `2024-01-01` for annual period `0A`. Confirm that the reviewed
`aeat-dr-193-2025` record design in
`src/cadrumo/_data/registry/aeat/legal/irpf.toml` applies from `2025-01-01`.
The official corpus manifest separately bundles and hashes a 2024 design
updated by Orden HAC/1504/2024 and an additional Orden HAC/56/2024 design for
2024 and following, but neither is registered as a 2024 record-design source in
the legal catalogue or revision source references.

Find no accepted comparison establishing that the 2024 and 2025 Tipo 1/Tipo 2
EDI structures are identical. The accepted declaration-extraction material
validates a synthetic 2024 declaration-PDF profile and the M123-to-M193
calculation relation; those are different surfaces and do not prove outbound
record-layout parity. Keep the authority windows separate now. Require an exact
2024-versus-2025 structure comparison before deciding whether the existing
revision may safely remain shared or must split at `2025-01-01`.

Inspect the Modelo 193 registry, generic exporter, and real-behaviour tests.
The revision has filing linkage and parity metadata but no `export_layouts`
data. The canonical `resolve_export_layout` and `export_draft` paths are generic
and fail closed when no layout is exposed. Modelo 193 registry tests validate
source-tier separation and snapshot behaviour, while the real
mutation-sensitive fichero-BOE suite covers Modelos 130, 303, and 390 only. No
real Modelo 193 golden outbound payload exists.

## Outcome

### `modelo-193-outbound-2025-open` | `mandate-gated`

- **Candidate:** Modelo 193 outbound fichero generation for annual filing year
  2025 and following, from `2025-01-01` with an open end.
- **Mandate:** `unproven`. Legacy discovery and generic export-routing wording
  identify a possible outbound surface, but no accepted decision or explicit
  current product goal requires local Modelo 193 fichero generation. Source
  availability, filing linkage, and parity metadata do not create a mandate.
- **Exact authority window:** `aeat-dr-193-2025` is a reviewed AEAT PDF record
  design registered from `2025-01-01` with an open end and covers this candidate
  window. The shared revision's 2024 start does not broaden that source.
- **Canonical implementation state:** `gap` only in optional Modelo 193 layout
  data: no export layout is registered. The canonical generic resolver,
  renderer, and parser are delivered and refuse the absent layout. Because the
  required capability is unproven, optional data absence does not satisfy the
  gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed 2025 record-design PDF
  is available as authority, but there is no real Modelo 193 golden outbound
  payload or mutation-sensitive export/parse round trip. The generic real
  round-trip suite does not include Modelo 193.
- **Retirement:** `false`; no accepted retirement or supersession applies.
- **Evidence block:** `true`; the missing artefact is a real Modelo 193 golden
  payload derived from the 2025 design and round-tripped through the canonical
  exporter/parser with mutation detection.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 193 fichero generation for 2025 and following. Until then,
  create no layout, renderer, parser, test, registry split, or successor
  implementation step.

### `modelo-193-outbound-2024` | `mandate-gated`

- **Candidate:** Modelo 193 outbound fichero generation for annual filing year
  2024, from `2024-01-01` through `2024-12-31`.
- **Mandate:** `unproven`. The same legacy discovery and routing wording does
  not establish a current product requirement for 2024. Bundled official
  artefacts and a declaration-extraction profile are evidence surfaces, not an
  outbound mandate.
- **Exact authority window:** `missing from the registered record-design
  catalogue`. The official corpus bundles and hashes the 2024 PDFs updated by
  Orden HAC/1504/2024 and Orden HAC/56/2024, but the legal catalogue and
  revision register only `aeat-dr-193-2025` from `2025-01-01`. No accepted
  structural comparison proves those 2024 layouts identical to the 2025
  design. Authority-window separation is therefore required; whether the
  registry schema itself must split remains pending exact comparison.
- **Canonical implementation state:** `gap` only in optional Modelo 193 layout
  data: no export layout is registered. The delivered generic resolver,
  renderer, and parser fail closed. With no proven required capability or
  registered exact-window layout authority, this is not an admitted canonical
  gap.
- **Real evidence or specimen:** `missing`. There is no real 2024 Modelo 193
  golden outbound payload or mutation-sensitive export/parse round trip. The
  synthetic 2024 declaration-PDF fixture verifies inbound extraction and cannot
  serve as an outbound golden fichero.
- **Retirement:** `false`; 2024 is temporally unreconciled, not retired.
- **Evidence block:** `true`; the missing outbound artefact is a real 2024
  golden fichero grounded in whichever exact 2024 record design applies after
  reconciliation.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision that explicitly requires
  local Modelo 193 fichero generation for 2024. Until then, do not catalogue a
  source for implementation, infer 2024/2025 structural identity, split or
  preserve the registry revision for export, author a layout/golden test, or
  create successor implementation work.

## Notes

- Grounding used the accepted adjudication contract, exact Modelo 193
  registry/legal/corpus files, generic exporter boundaries, and direct
  test/fixture inventory. The bounded `vaultspec-rag` hit was an inbound
  synthetic extraction test; it was treated only as a pointer and not as
  outbound authority or golden evidence.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
