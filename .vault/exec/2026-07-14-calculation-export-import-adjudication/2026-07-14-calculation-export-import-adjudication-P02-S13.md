---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S13'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---




# Record that Modelo 360 has no legacy outbound mandate and preserve its layout authority as evidence only

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/360/`
- `.vault/reference/`

## Description

Confirm that the current `2010-y-siguientes` registry revision in
`src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/revision.toml`
uses `valid_from = 2010-04-01`. Confirm that the reviewed `aeat-dr-360-2010`
PDF record design applies from `2010-04-01`, aligned with the revision start.

Inspect the accepted ADR, research, reference register, and plan. None
contains an accepted decision, explicit current product goal, or legacy
export-layout task for Modelo 360. A record design being registered proves
format applicability only; it does not manufacture outbound product scope.

Inspect the Modelo 360 registry and the generic export engine. The revision
has no `export_layouts` data. The shared `resolve_export_layout` and
`export_draft` paths remain canonical and fail closed. No real Modelo 360
golden outbound payload or mutation-sensitive export/parse round trip exists.

## Outcome

### `modelo-360-outbound-2010-open` | `not-mandated`

- **Candidate:** Modelo 360 outbound fichero generation from `2010-04-01`
  with an open end under revision `2010-y-siguientes`.
- **Mandate:** `absent`. No accepted decision, explicit current product goal,
  or legacy export-layout task requires local Modelo 360 fichero generation.
  A feasible bundled record design is not a mandate.
- **Exact authority window:** `aeat-dr-360-2010` is a reviewed AEAT PDF
  record design registered from `2010-04-01`, aligned with the revision, and
  covers this candidate window. Authority proves format applicability only.
- **Canonical implementation state:** `gap` only in optional Modelo 360
  layout data: no export layout is registered. The canonical generic
  resolver, renderer, and parser are delivered and refuse the absent layout.
  Because no required outbound capability exists, optional data absence does
  not satisfy the gate's canonical-gap condition.
- **Real evidence or specimen:** `missing`. The reviewed record-design PDF is
  available as authority, but no real Modelo 360 golden outbound payload or
  mutation-sensitive round trip exists.
- **Retirement:** `false`; the candidate is not retired, but it has no
  mandate.
- **Evidence block:** `true`; a real Modelo 360 golden outbound payload is
  unavailable. Taxonomy precedence still selects `not-mandated` before any
  evidence-gated state.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`,
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `not-mandated`.
- **Next action:** `none`. Create no Modelo 360 export layout, renderer,
  parser, golden test, or successor implementation work unless a future
  accepted decision or explicit product goal establishes an outbound
  mandate. Preserve `aeat-dr-360-2010` as registered layout-authority
  evidence; do not remove it.

## Notes

- Grounding used the accepted adjudication contract, exact Modelo 360
  registry/legal files, generic exporter boundaries, and the existing
  reference register entry for Modelo 360 (which already records the
  companion declaration-PDF extraction candidate as evidence-gated under
  `P03.S22`).
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
