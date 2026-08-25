---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0f6bf305cf7223ef43d9ec2510d0a625381201905a895b50c705797598996ec3'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# `registry-temporal-coverage` audit: `s13 full span matrix`

## Scope

Independent review of `W02.P06.S13` at `915a66a5bc` and corrective provenance `7bbbd2c777`, against the temporal-coverage plan, its governing ADRs, the S13 and S24 execution records, and the current implementation. Vaultspec-RAG located the plan, ADR and execution epicentre. The shared code index remained in a continuous refresh and the explicit local fallback reported a published-but-empty index, so it was not used to establish any absence claim. Whole-file reads of `src/cadrumo/domain/calculations/registry/_coverage.py`, `src/cadrumo/domain/calculations/registry/_temporal.py`, `src/cadrumo/application/registry/_temporal_coverage.py`, and `src/cadrumo/application/registry/_filing_export_coverage.py`, plus targeted `rg`, supplied the code evidence.

Verdict: S13 passes. The derived selector expansion uses the registry-supported filing-year horizon and produces one canonical `(modelo, revision, filing_year, period)` row per declared coordinate. The model-law audit reselects through the authority for every cell, sub-filing grades remain inspection-only, construct evidence probes every coordinate, and conformance aggregates complete cell sets without retaining an arbitrary later or representative cell. Targeted `rg` found no executable `_representative_year` or representative-coordinate consumer; the remaining matches are explanatory text only. The real bundled temporal property suite passed 39 tests.

The derived authority denominator is 2,220 cells across 102 revisions, computed from the supported-year horizon and selector coordinates without a hard-coded cardinality assertion. This is non-vacuous: the suite proves a real long-span open revision expands through every later supported year and that a deliberately removed later lookup cell is retained as a refusal.

## Findings

### m353-stale-filing-expectation | low | The integration test expects a refusal no longer produced by the canonical full-span consumer

`test_modelo_353_layout_gap_is_selected_by_its_own_law_coordinate_and_cannot_be_masked_by_2026` fails with `StopIteration` because it searches for an M353 `filing-layout` refusal. The isolated integration run produced two passes and this one failure. This is not an S13 regression: the full-span filing-export consumer iterates both revisions' declared coordinates, each coordinate passes the layout-evidence branch, and both reach the existing `production-emission-proof` refusal instead. The stale test predates S13; its coordinate assertions were later converted to the shared full-span derivation. The failure therefore concerns the expected evidence stage, not a representative coordinate, a lost later cell, or incorrect law selection.

## Recommendations

- Update the M353 integration expectation under the filing-export proof owner to assert the present `production-emission-proof` refusal, preserving the law-coordinate and no-mask assertions. Keep this correction separate from S13 unless that owner elects to absorb it.
- Treat the code-index refresh as an operational discovery limitation: do not infer absence from its empty fallback result. Restore index health before relying on semantic code search for future coverage audits.
