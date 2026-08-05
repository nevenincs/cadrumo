---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:06fc3f84536769997d0054f2264ea933b817654bc90020ec7c532e994824d9bc'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
---
## Scope

Reviewed the SOL-authorized projection of the exact-year casilla/layout comparator into the finite annual conformance report. The review covers the typed coordinate contract, authority-selected snapshot wiring, JSON/text projections, degraded-read behavior, and the distinction between measured XML-dictionary identity and unsupported printed-form/XSD parity.

## Findings

### s02-d2025-schema-projection | medium | The exact comparator is now visible on the standard finite report surface

The finite annual matrix remains one exact coordinate: Modelo 100, filing year 2025, period `0A`, law-selected revision `2025`. The manager resolves one validated snapshot, passes its authority source root to `compare_annual_casilla_population`, and stores the typed result on `ConformanceCoordinate`. The coordinate validator rejects any nested comparison whose modelo, filing year, period, or revision differs from the enclosing coordinate. JSON exposes the nested comparison, computed missing/extra identity sets, per-layout divergence, and total divergence; text emits coordinate and `annual_schema_layout` rows.

The live D2025 XML-dictionary measurement is 2,238 non-internal registry casillas versus 2,205 dictionary casillas: 33 missing registry identities and zero extra dictionary identities. This is a measured identity divergence, not a behavioral parity score.

### evidence-boundary | low | Unsupported evidence remains explicit

D2025 remains classified `not_yet_measured` and `provisional=true`. Printed-form membership and XSD-only/unmapped attribute parity remain `unsupported`; a comparator without a resolvable source remains `unmeasured`. No dictionary identity is promoted into printed-form, complete-attribute, behavioral, legal, or oracle parity.

### finite-denominator-boundary | low | The annual denominator remains deliberately narrow

The projection covers only coordinates already enumerated by the finite matrix. M100 2020â€“2024 comparator results remain bounded API/test evidence and were not added to the annual denominator. No newest/largest revision, portfolio revision count, or count equalization was introduced.

### verification-boundary | low | Independent reviewer did not return

The delegated `vaultspec-code-reviewer` was invoked with the mandatory RAG-grounded scope but timed out before returning a verdict. The supervisor review therefore records no independent reviewer sign-off. The implementation evidence below is retained as the bounded local verification result.

## Recommendations

- Keep the D2025 coordinate provisional until official layout and independent behavioral/oracle evidence closes the remaining parity domains.
- Preserve `unsupported` and `unmeasured` as distinct states; do not infer printed-form or XSD parity from dictionary identity.
- Treat M100 2025 casillas `0150`, `0613`, and `1481` as manual/open under their existing SOL decisions; no formula, binding, profile, selector, relation, or aggregation change is authorized by this review.
- Revisit the shared locale ratchet separately; do not weaken its baseline to close this projection.

## Verification

- `uv run --no-sync pytest -q -n 0 dev/tests/test_registry_conformance_cli.py -k 'report_json_keeps_the_finite_annual_matrix or annual_matrix_revision_is_read_from_the_validated_authority or report_text_projects_schema_layout or annual_coordinate_rejects_mismatched_schema_comparison or degraded_report_does_not_claim_validated_annual_coordinates or annual_matrix_rejects_an_incomplete_classification_census or annual_matrix_rejects_a_census_count_that_does_not_match_coordinates or annual_matrix_rejects_duplicate_exact_coordinates'` â€” 8 passed.
- The broader report/matrix selector passed 12 tests and retained one unrelated locale-ratchet failure; the full legacy CLI file remains bounded by pre-existing `localization_key` peer-schema failures and the known locale baseline boundary.
- `uv run --no-sync basedpyright src/cadrumo/application/registry/__init__.py dev/registry/conformance/manager.py` â€” 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync ruff check` and `ruff format --check` on the three authorized files â€” clean.
- Real CLI JSON report â€” D2025 identity measured, 2,238 registry, 2,205 dictionary, 33 divergence, zero extra; classification remains `not_yet_measured` and provisional.
- Real CLI text report â€” coordinate and layout rows present with measured and unsupported statuses; the real no-source comparator test preserves `unmeasured` separately.
- `uv run --no-sync vaultspec-core vault check all --feature modelo-parity-rollup --json` â€” all diagnostics empty.
- `python -m dev.registry.conformance audit --check` remains intentionally non-green only at the known shared locale ratchet boundary: audited locale leaves 47,322 versus baseline 47,376 and translated labels 25,677 versus 25,767; no baseline weakening was made.
