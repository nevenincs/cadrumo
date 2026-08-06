---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:9bd6064548353f7ab282880c130c5ffee62c4c278ec1583c401d19ce961ff26d'
step_id: 'S09'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Record that Modelo 309 has no legacy outbound mandate and prevent source availability from manufacturing one

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/309/`
- `.vault/reference/`

## Description

Record the absence of any Modelo 309 outbound product mandate separately from
the availability of later record-design authority.

Confirm that the current `2004-y-siguientes` registry revision in
`src/cadrumo/_data/registry/aeat/modelos/309/revisions/2004-y-siguientes/revision.toml`
uses filing year 2004 and following with the `AD-HOC` period. Confirm that the
reviewed `aeat-dr-309-2023` XLS record design in
`src/cadrumo/_data/registry/aeat/legal/iva.toml` applies from `2023-01-01` with
an open end. Keep 2004-2022 outside that machine-file authority window.

Inspect the accepted ADR, research, reference register, and plan. None contains
an accepted decision, explicit current product goal, or legacy export-layout
task for Modelo 309. Registry calculation coverage, filing/extraction links,
workbook parity metadata, and an available record design describe existing
surfaces and evidence; they do not create outbound scope.

Inspect the Modelo 309 registry and generic export engine. The revision has no
`export_layouts` data. The shared `resolve_export_layout` and `export_draft`
paths remain canonical and fail closed when no layout is exposed. Direct Modelo
309 tests validate the committed definition, AD-HOC revision/snapshot,
calculation bindings, and parity linkage. The real mutation-sensitive
fichero-BOE suite covers Modelos 130, 303, and 390 only; no real Modelo 309
golden outbound payload exists.

## Outcome

### `modelo-309-outbound-2023-open` | `not-mandated`

- **Candidate:** Modelo 309 outbound fichero generation for AD-HOC filings from
  `2023-01-01` with an open end under revision `2004-y-siguientes`.
- **Mandate:** `absent`. No accepted decision, explicit current product goal,
  or legacy export-layout task requires local Modelo 309 fichero generation.
  The registered record design, filing link, and parity reference are not a
  mandate.
- **Exact authority window:** `aeat-dr-309-2023` is a reviewed AEAT XLS record
  design registered from `2023-01-01` with an open end and covers this candidate
  window. Authority proves format applicability only, not product scope.
- **Canonical implementation state:** `gap` only in optional Modelo 309 layout
  data: no export layout is registered. The canonical generic resolver,
  renderer, and parser are delivered and refuse the absent layout. Because no
  required outbound capability exists, optional data absence does not satisfy
  the gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed 2023 record-design XLS
  is available as authority, but no real Modelo 309 golden outbound payload or
  mutation-sensitive export/parse round trip exists. This missing evidence does
  not revive a non-mandated candidate.
- **Retirement:** `false`; the candidate is not retired, but it has no mandate.
- **Evidence block:** `true`; a real Modelo 309 golden outbound payload is
  unavailable. Taxonomy precedence still selects `not-mandated` before any
  evidence-gated state.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `not-mandated`.
- **Next action:** `none`. Create no Modelo 309 export layout, renderer, parser,
  golden test, registry split, or successor implementation work unless a future
  accepted decision or explicit product goal establishes an outbound mandate.

### `modelo-309-outbound-2004-2022` | `not-mandated`

- **Candidate:** Modelo 309 outbound fichero generation for AD-HOC filing years
  2004-2022 under revision `2004-y-siguientes`, from `2004-01-01` through
  `2022-12-31`.
- **Mandate:** `absent`. No accepted or legacy outbound requirement exists for
  this historical window. Registry coverage, legal form authority, filing
  linkage, and the later 2023 record design cannot manufacture one.
- **Exact authority window:** `missing`. The registered
  `aeat-dr-309-2023` record design starts on `2023-01-01` and cannot support
  2004-2022. `boe-modelo-309-2003-form` grounds the form and obligation, not an
  exact historical machine-file layout.
- **Canonical implementation state:** `gap` only in optional historical layout
  data: no export layout is registered. The delivered generic resolver,
  renderer, and parser fail closed. With no required outbound capability,
  optional registry absence is not a canonical gap for admission.
- **Real evidence or specimen:** `missing`. There is no exact-window official
  record design and no real Modelo 309 golden outbound payload for 2004-2022.
  The 2023 XLS and other-model round trips cannot be extrapolated backward.
- **Retirement:** `false`; the candidate is not retired, but it has no mandate.
- **Evidence block:** `true`; exact-window golden outbound evidence is
  unavailable. The earlier `not-mandated` taxonomy rule remains controlling.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `not-mandated`.
- **Next action:** `none`. Do not seek historical layout authority for
  implementation, extrapolate the 2023 design, author registry data or tests,
  or create successor work unless a future accepted mandate changes scope.

## Notes

- A concurrent coordinator committed this record together with P03.S22 and
  closed both plan rows before independent review completed. The rows were
  reopened through the canonical CLI; this record is reclosed only after the
  reviewer accepted its substantive outcome.
- Grounding used the accepted adjudication contract, exact Modelo 309
  registry/legal files, generic exporter boundaries, and direct test/fixture
  inventory. The bounded `vaultspec-rag` query returned unrelated export
  documentation; no semantic result was treated as mandate or authority.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
