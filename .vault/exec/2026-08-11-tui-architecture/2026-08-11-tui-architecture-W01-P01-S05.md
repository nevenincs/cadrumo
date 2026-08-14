---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d32df5a0520538698e2e7b072a6313db24afe64736789e88409c0f8cd65561cf'
step_id: 'S05'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# Prove the generated migration manifest matches direct source discovery and admits no new identity

## Scope

- `src/cadrumo/tests/test_tui_migration_manifest.py`
- `dev/quality/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_scan.py`

## Description

- Ground the proof in the canonical import-hygiene scanner, S01 manifest record and audit, and the accepted exact-census decision through semantic RAG and full-file reads.
- Compare the production manifest with independently observed real-tree module and literal-export multiplicity without reusing private discovery helpers or mirroring scanner suppression logic.
- Make qualified-reference discovery occurrence-exact, including a string reference on the same physical line as an import; recursively discover nested production legacy modules; and bind the accepted digest to row multiplicity and full disposition.
- Exercise each reviewed escape with a real temporary package mutation: same-line import plus reference, nested module insertion, and duplicate semantic rows.

## Outcome

The canonical scanner now preserves exact qualified-reference occurrences, recursively discovers nested legacy production modules while excluding the legacy test subtree, and hashes the ordered row collection rather than a deduplicating set. The S05 acceptance gate independently proves real-tree module/export multiplicity and plants each reviewed escape against the production generator.

The final live census contains exactly 515 rows: 16 modules, 129 literal exports, 351 imports, and 19 qualified references. Its accepted full-disposition digest is `4eda54f61f2d91912366af74bc8684732afce84ed2fb4e45c11c19ff28ee549f`. During post-pin review, an apparent 520-row census was adjudicated as test self-contamination: five reference rows came from literal legacy-package strings inside this acceptance test itself (two occurrences at the same-line fixture, one at the baseline duplicate fixture, and two at the duplicate mutation). Constructing those planted source strings from the canonical package constant removed all five self-rows; the S05 test now contributes zero rows to the census it proves.

## Notes

Canonical-home decision: `dev.quality.import_hygiene_scan` remains the sole manifest, discovery, disposition, and digest authority. S05 adds an independent acceptance consumer under `src/cadrumo/tests`; no second scanner, baseline, allowlist, compatibility bridge, fake, mock, patch, monkeypatch, skip, or xfail was introduced.

Review remediation evidence:

- Same-line import and qualified-reference occurrences are collected independently rather than suppressed by physical line.
- Nested production legacy modules are recursively discovered and fail closed when undispositioned.
- Exact row multiplicity participates in the accepted digest; a planted duplicate edge is refused.
- The acceptance test uses direct filesystem and standard-library AST observations for module/export facts and does not reuse private discovery helpers.
- The exact census assertion is grounded in the enumerated final kind counts, and fixture strings no longer introduce their own census identities.

Focused verification:

- Initial remediation run: exact focused pytest command reported 6 failed and 6 passed in 336.13 seconds; every failure was the same stale accepted-census pin.
- First post-pin run: the exact focused pytest command reported 11 passed and 1 failed in 315.73 seconds; the only failure was the stale `515` assertion against the self-contaminated 520-row census.
- Intermediate run after removing the stale count assertion: the exact focused pytest command reported 12 passed in 281.82 seconds. Subsequent semantic adjudication proved the five-row increase came exclusively from S05 fixture literals, so this was not accepted as the final proof.
- Final command: `uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_tui_migration_manifest.py dev/tests/test_import_hygiene_scan.py::test_live_tui_migration_manifest_covers_declarations_exports_consumers_and_references dev/tests/test_import_hygiene_scan.py::test_tui_migration_manifest_json_is_deterministic_and_complete dev/tests/test_import_hygiene_scan.py::test_tui_migration_manifest_refuses_a_new_undispositioned_legacy_module dev/tests/test_import_hygiene_scan.py::test_tui_migration_manifest_refuses_an_unreadable_consumer dev/tests/test_import_hygiene_scan.py::test_tui_migration_manifest_refuses_a_new_symbol_or_consumer_identity dev/tests/test_import_hygiene_scan.py::test_tui_migration_manifest_refuses_disposition_drift` - 12 passed in 237.69 seconds.
- Final command: `uv run --no-sync ruff check dev/quality/import_hygiene_scan.py dev/tests/test_import_hygiene_scan.py src/cadrumo/tests/test_tui_migration_manifest.py` - all checks passed.

Standing verification status: the exact S05 focused pytest and Ruff gates are green. The Step remains open and uncommitted pending independent final review.

Mechanical closeout verification:

- `uvx vaultspec-core vault check all` - exit 1 in 23.2 seconds with 10 errors and 1,313 warnings. All errors are unrelated to S05: eight missing-frontmatter errors and two invalid-UTF-8 errors belong exclusively to `2026-08-07-canonical-identifiers-W08-P13-S56.md` and `2026-08-07-canonical-identifiers-W08-P13-S57.md`. The warnings comprise one Markdown-hygiene warning, five feature warnings, 54 execution-mapping warnings, 1,221 body-section warnings, 29 schema warnings, and three modified-stamp warnings. S05's structure, links, mapping, and attested body introduced no reported violation.
