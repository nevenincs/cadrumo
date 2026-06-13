---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S09'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Re-run formerly-red gates + bounds test fix

## Scope

- `src/aeat/domain/calculations/registry/test_record_design.py`

## Description

Re-ran `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q --tb=line --no-header -p no:logging`. The bin-aplicada-maxima-specific `RegistryValidationError` ("casilla 'DP200014:bin-aplicada-maxima' declared under segmento 'DP200014' but Diseño does not carry it") is gone — the schema field + gate exemption + TOML flip have closed that gap as the ADR designed.

The `test_calculation_closure_bounds_the_full_diseno_coverage` test was further amended to subtract `internal_only_identities` from the closure before asserting it is a subset of the full-Diseño coverage, then assert on `exported_closure <= coverage`. The contract the test now expresses is the ADR's narrowed claim: every *exported* closure casilla must appear in the Diseño; an internal_only ceiling is intentionally exempt. A stable, sort-key-safe error formatter replaced the unsafe `sorted(tuple-with-None)` rendering that had been a TypeError-on-failure trap.

## Outcome

Verified via direct run:

- `test_internal_only_casilla.py` — 3 tests, all green.
- `test_record_design.py` — the bin-aplicada-maxima error is gone; the manifest derivation now enumerates `(DP200014, DP200014:bin-aplicada-maxima)` as a derived identity post-exemption.
- Remaining reds in `test_record_design.py` (3) are concurrent-campaign drift unrelated to this ADR's scope:
  1. `test_registered_record_design_sources_are_discovered_and_parseable` fails because a `record_design` catalogue source now carries a `.html` corpus_path; `_extract_record_design_cached` only supports `.pdf` / `.xls` / `.xlsx`. Out of scope; predates this work.
  2. `test_calculation_completeness_manifests_match_their_calculation_surface` fails because M100's manifest drifted from its closure — `(None, '1388')`, `(None, '1391')` exist in the closure but not in the manifest. M100 issue, unrelated to M200 internal_only.
  3. `test_calculation_closure_bounds_the_full_diseno_coverage` still fails after the internal_only exemption because 8 OTHER M200 closure tokens (`00501`, `00670`, `00671`, `01032`, `01494`, `01495`, `01498`, `01499`) resolve to `(None, number)` in the closure — their TOML declares no segmento despite M200 being multi-segment, so the closure-identity carries no segmento and the Diseño coverage (which is keyed `(sheet_name, number)`) cannot match them. These were masked previously because the bin-aplicada-maxima error fired before the bounds check could expose them. Pre-existing concurrent-campaign drift.

The ADR scope (bin-aplicada-maxima ceiling and the schema + gate discipline that defends it) is delivered. The three pre-existing reds and the 8 pre-existing `(None, number)` M200 closure mismatches belong to separate campaigns and are documented here for follow-up.
