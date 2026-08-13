---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d819ed0e863e08c34c647ed3bc53d8a9819c8edf299ea12572bacac59803f522'
step_id: 'S01'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Generate the exact legacy TUI migration manifest with module, symbol, consumer, owner lane, replacement, and deletion proof

## Scope

- `dev/quality/import_hygiene_scan.py`

## Description

- Extend the canonical `dev.quality.import_hygiene_scan` authority with a fail-closed legacy-TUI migration census.
- Derive module declarations, literal exports, static and type-only imports, local imports, development-tool imports, and qualified Python references from the live AST graph.
- Join every row to its owner lane, canonical replacement or installed boundary, exact locator, consumer class, legacy state, and source-file deletion proof.
- Emit the stable manifest through the scanner's full JSON output and the dedicated `--tui-migration-json` route.
- Correct the plan scope from the retired pre-relocation path through the sanctioned Step edit verb.
- Add direct live-tree, determinism, unreadable-consumer, new-module, new-symbol, new-consumer, and disposition-drift failure proofs.

## Outcome

The live scan produces 515 deterministic rows: 16 module declarations, 129 exports, 351 import edges, and 19 qualified non-import references. Ownership resolves to 409 interface rows, 63 operation rows, 14 Modelo rows, and 10 integration rows. The accepted semantic digest `af0f314fcc15fa1b677c29ba372fe805fb2bd12a7964a88e6186a6b5dd3176fd` binds every row's kind, module, symbol, consumer, consumer class, owner lane, replacement, deletion proof, and state. New or removed identities, consumer reclassification, and disposition drift fail closed; line locators alone remain volatile.

Exact bounded verification completed successfully:

- `uv run --no-sync ruff format dev/quality/import_hygiene_scan.py dev/tests/test_import_hygiene_scan.py` - one file reformatted and one unchanged.
- `uv run --no-sync ruff check dev/quality/import_hygiene_scan.py dev/tests/test_import_hygiene_scan.py` - all checks passed.
- `uv run --no-sync ruff format --check dev/quality/import_hygiene_scan.py dev/tests/test_import_hygiene_scan.py` - both files already formatted.
- `uv run --no-sync pytest -q dev/tests/test_import_hygiene_scan.py -k "tui_migration_manifest"` - eight passed in 281.40 seconds.
- `uvx vaultspec-core vault check all` - exited zero in 32.6 seconds with all structural, frontmatter, annotation, Markdown, link, placeholder, orphan, feature-rename, reference, ADR-status, rename-integrity, and encoding checks clean; it reported 1,294 warnings from the shared global vault.

## Notes

The plan originally named `dev/import_hygiene_scan.py`, but commit `ccebda4141` relocated that scanner to its canonical quality package. No compatibility module or duplicate implementation was created. The plan scope was updated with `vault plan step edit`, without canonicalisation.

The broader scanner test module has one pre-existing stale-path failure: `test_find_shim_modules_still_flags_a_non_main_pure_reexport_module` expects the removed `src/cadrumo/domain/transactions/_ids.py`. This Step did not alter or suppress that unrelated test.

The global vault warnings are not S01 failures. They include seven stale/missing feature-association warnings, 53 historical exec-mapping warnings, 29 plans without research references, the shared corpus of historical audit body-section warnings, and one stale fingerprint on this Step's independent review audit before final re-attestation. The S01 plan/exec mapping itself passed, and the TUI architecture feature's only reported association issue was its stale feature index (`related` contained three links while five feature documents existed).
