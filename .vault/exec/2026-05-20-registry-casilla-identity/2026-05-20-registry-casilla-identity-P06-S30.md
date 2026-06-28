---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S30'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P06.S30`

Updated the drift / coverage tests so the full-Diseño extraction is
exercised as an advisory coverage report rather than a load-blocking
gate, per the ADR amendment.

- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`

## Description

The P03 drift block re-derived each checked-in manifest with the
full-Diseño extraction and asserted exact equality against the manifest.
The block is rewritten to the refocused two-concern structure:

- `test_calculation_completeness_manifests_match_their_corpus_diseno` —
  the load-bearing drift re-verification, now re-deriving each
  checked-in calculation-completeness manifest with
  `derive_calculation_completeness_casillas` (the modelo's calculation
  closure intersected with the corpus Diseño) and asserting it still
  equals the manifest. No manifests are authored yet, so the loop
  iterates zero; the discovery-sanity assertion stays load-bearing and
  covers manifests automatically once P05 lands them.
- `test_diseno_coverage_report_inventories_modelo_200_form_data` — the
  full-Diseño extraction (`derive_diseno_coverage_casillas`) is now
  exercised as an advisory coverage inventory: it surfaces every casilla
  AEAT declares on the Modelo 200 form, proves the extraction is
  load-bearing (the Liquidación cuota-chain casillas surface under
  `DP200014`, the multi-segment number-reuse contract holds), and never
  reds the load.
- `test_calculation_closure_bounds_the_full_diseno_coverage` — NEW:
  proves the refocus is real. The Modelo 200 calculation-completeness
  derivation yields a strict, non-empty subset of the full-Diseño
  coverage, because the M200 Diseño is overwhelmingly accounting-
  statement data-entry fields outside the calculation closure. A modelo
  can therefore clear the load-blocking gate without an exhaustive
  full-form backfill — the design intent of the ADR amendment.

A `_modelo_200_record_design_corpus_path` helper was extracted to share
the corpus-path resolution across the coverage and closure tests.

## Tests

`pytest src/aeat/domain/calculations/registry/test_record_design.py
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`
passes — 40 tests, all 26 modelos load valid and the gate stays dormant.
`ruff check` on the touched file passes clean.
