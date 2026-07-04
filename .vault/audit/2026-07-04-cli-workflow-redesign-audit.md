---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# `cli-workflow-redesign` audit: `Modelo 145 registry foundation review`

## Scope

Review the Modelo 145 registry foundation repair for registry-load correctness,
non-filing scope, and export-support honesty.

## Findings

### modelo-145-registry-foundation-missing | high | Registry foundation files are absent while the new tests require Modelo 145 to load

The current worktree no longer contains `src/aeat/_data/registry/aeat/modelos/145/manifest.toml` or the revision fragments listed for the Modelo 145 registry foundation, while `src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` still calls `bundled_authority().modelo("145")` at lines 21, 42, and 70. Focused verification with `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py -q` fails all three tests with `RegistrySnapshotError: modelo '145' is not present in the calculation registry`, so the patch does not currently fix the registry-load blocker.

### modelo-145-registry-foundation-restored | low | Previous missing-registry blocker is resolved in the repaired state

Re-review found `src/aeat/_data/registry/aeat/modelos/145/manifest.toml` and the expected `revision.toml`, `application_links`, `casillas`, and `workbook_parity_refs` fragments restored. At that intermediate point, before the later `P03.S13` retry, focused verification with `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short` passed 22 tests, `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed, and a direct authority/support-matrix probe reported 50 casillas with DR145 record-design parity. The prior high finding is therefore resolved.

### modelo-145-dangling-export-refs-transient | low | Transient no-export repair was superseded by the completed layout

A later follow-up caught a transient fixed-width layout attempt that left Modelo 145 casillas pointing at export fields after the layout was removed. That no-export repair was useful while the layout was absent, but it is now superseded by the completed `P03.S13` retry below: the current registry keeps the DR145 export layout and matching casilla `export_refs`.

### modelo-145-fixed-width-layout-registered | low | S13 retry completed the DR145 layout without adding filing semantics

A subsequent retry completed `P03.S13` by registering the `modelo-145-dr-v20-fixed-width` export layout, adding the matching 50 casilla `export_refs`, and verifying DR145 v2.0 byte-span coverage from the bundled extractor output. Focused verification with `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py --tb=short` passed 4 tests, `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed, and the four-file registry/support slice passed 23 tests. Modelo 145 still has no filing schedules, deadline windows, live cross references, portal links, or AEAT submission surface.

## Recommendations

- The earlier `export_layouts`-empty recommendation is retired: `P03.S13` is now closed with extractor-grounded DR145 layout metadata.
- Continue with `P04.S16`; backend behavior must preserve the same local payer-communication boundary.
