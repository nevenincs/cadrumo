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

Re-review found `src/aeat/_data/registry/aeat/modelos/145/manifest.toml` and the expected `revision.toml`, `application_links`, `casillas`, and `workbook_parity_refs` fragments restored, with no `export_layouts` fragment. Focused verification with `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short` passed 22 tests, `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed, and a direct authority/support-matrix probe reported 14 casillas, parity `modelo-145-dr-v20`, zero export layouts, and `has_fixed_width_export=False`. The prior high finding is therefore resolved.

## Recommendations

- Keep `export_layouts` empty until a complete DR145 fixed-width value-field layout is grounded and verified, so `build_support_matrix` does not advertise fixed-width export support prematurely.
- Leave `P03.S13` open for the future complete export-layout implementation.
