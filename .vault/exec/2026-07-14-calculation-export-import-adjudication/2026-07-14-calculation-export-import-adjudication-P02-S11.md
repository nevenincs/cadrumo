---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S11'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---




# Adjudicate Modelo 347 export by registered authority window and gate uncatalogued 2008-to-2010 layouts

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/347/`
- `.vault/reference/`

## Description

Confirm that the current `2008-y-siguientes` registry revision in
`src/cadrumo/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/revision.toml`
uses `valid_from = 2008-10-23`. Confirm that the two registered PDF record
designs in `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml`
are `aeat-dr-347-2011` (`2011-12-13` through `2024-12-31`) and
`aeat-dr-347-2025` (`2025-01-01`, open end). Record the resulting
uncatalogued registry span before `2011-12-13` as an authority-registration
gap. The official corpus already bundles separate designs for exercises
2008-2009 and exercise 2010, but neither artefact has reviewed applicability
metadata in the legal-source registry. Preserve those windows separately;
do not infer a single layout from the later registered designs.

Inspect the accepted ADR, research, reference register, and plan. The legacy
work explicitly deferred record bindings until the official PDF designs could
be transcribed; that deferral is a conditional pointer, not an accepted
current-scope decision. No accepted decision or explicit current product
goal confirms Modelo 347 machine-file generation as required today.

Inspect the Modelo 347 registry and the generic export engine. The revision
has no `export_layouts` data across its full span. The shared
`resolve_export_layout` and `export_draft` paths remain canonical and fail
closed. No real Modelo 347 golden outbound payload or mutation-sensitive
export/parse round trip exists.

## Outcome

### `modelo-347-outbound-2025-open` | `mandate-gated`

- **Candidate:** Modelo 347 outbound fichero generation for annual filings
  from `2025-01-01` with an open end under revision `2008-y-siguientes`.
- **Mandate:** `conditional`. The legacy deferral names a future transcription
  task, not a proven current requirement; no accepted decision or explicit
  product goal exists.
- **Exact authority window:** `aeat-dr-347-2025` is a reviewed AEAT PDF record
  design registered from `2025-01-01` with an open end and covers this
  candidate window exactly.
- **Canonical implementation state:** `gap` only in optional layout data; the
  canonical generic resolver, renderer, and parser are delivered and refuse
  the absent layout.
- **Real evidence or specimen:** `missing`; no real Modelo 347 golden
  outbound payload or mutation-sensitive round trip exists for this window.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm an explicit current product decision for Modelo
  347 outbound machine-file generation before authoring any registry data.

### `modelo-347-outbound-2011-2024` | `mandate-gated`

- **Candidate:** Modelo 347 outbound fichero generation for annual filings
  from `2011-12-13` through `2024-12-31` under revision `2008-y-siguientes`.
- **Mandate:** `conditional`, for the same reason as the 2025-open window.
- **Exact authority window:** `aeat-dr-347-2011` is a reviewed AEAT PDF
  record design registered from `2011-12-13` through `2024-12-31` and
  covers this candidate window exactly.
- **Canonical implementation state:** `gap` only in optional layout data,
  identical boundary as above.
- **Real evidence or specimen:** `missing`; no real golden payload exists.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** same as the 2025-open window; the two windows require one
  shared product decision, then separate registry layout data because the
  record designs differ.

### `modelo-347-outbound-2008-2009` | `mandate-gated`

- **Candidate:** Modelo 347 outbound fichero generation for exercises 2008
  and 2009 under revision `2008-y-siguientes`.
- **Mandate:** `conditional`, identical reasoning; not independently proven
  for this span either. Taxonomy precedence selects `mandate-gated` ahead of
  any authority finding.
- **Exact authority window:** `missing` from the registry. The official
  corpus bundles `02-347-ejercicio-2008-y-2009-30-kb-pdf.pdf`, but its exact
  applicability has not been reviewed and registered as legal authority.
- **Canonical implementation state:** `gap` only in optional layout data.
- **Real evidence or specimen:** `missing`.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`,
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm the product decision named above; if confirmed,
  review the bundled 2008-2009 design's exact applicability and register it
  before any layout transcription.

### `modelo-347-outbound-2010` | `mandate-gated`

- **Candidate:** Modelo 347 outbound fichero generation for exercise 2010
  under revision `2008-y-siguientes`.
- **Mandate:** `conditional`, identical reasoning; not independently proven.
- **Exact authority window:** `missing` from the registry. The official
  corpus bundles `03-347-orden-eha-3062-2010-ejercicio-2010-181-kb-pdf.pdf`,
  but its exact applicability has not been reviewed and registered as legal
  authority.
- **Canonical implementation state:** `gap` only in optional layout data.
- **Real evidence or specimen:** `missing`.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`,
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm the product decision named above; if confirmed,
  review the bundled 2010 design's exact applicability and register it before
  any layout transcription.

## Notes

- Independent Terra high review corrected the original combined
  2008-to-2011 authority-gap row: the corpus already contains distinct
  2008-2009 and 2010 designs, although neither is registered authority.
- Grounding used the accepted adjudication contract, exact Modelo 347
  registry/legal files, the separately bundled 2008-2009 and 2010 official
  designs, generic exporter boundaries, and the existing reference register
  entry for Modelo 347.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
