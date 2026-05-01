---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-05-import-linter-contract-exec]]"
---

# 2026-04-30-aeat-restructure step-05 legacy verification subroutine

## status

Step 5 PR 2 of N. Historical shim-verification work, superseded by the delivered hard-cutover. The accepted state verifies canonical public paths directly and treats deleted public root modules as the deterministic major-version trigger.

## scope

- Historical script `scripts/verify_shims.py` declared the public-surface contract (4 module entries; ~50 symbols total).
- The script was deleted after the hard-cutover decision; `tests/import_contract/test_adr_layout_import_smoke.py` is the delivered verification surface.
- Exit status is no longer part of the accepted gate because no compatibility layer is retained.

## audit-grounded fix discovered during PR

The historical verifier surfaced a real public-surface gap pre-Step-7: `restrict_file_permissions` (per ADR public-surface table) was NOT actually exposed on `aeat.adapters.outbound.aeat.auth`. The function existed at `aeat.adapters.outbound.aeat.auth._file_permissions.restrict_file_permissions` and was imported only via the relative path internally; no entry on `aeat.adapters.outbound.aeat.auth.__init__.py` __all__ + import block.

Fix applied in this PR:
- Add `from ._file_permissions import restrict_file_permissions` to `aeat.adapters.outbound.aeat.auth.__init__.py`.
- Add `"restrict_file_permissions"` to the `__all__` list (alphabetical position between `preload_into_browser_context` and `select_provider`).

This made the ADR's public-surface promise concrete pre-Step-7. The delivered hard-cutover later moved the stable contract to canonical paths rather than promising OLD-path reachability.

## historical public-surface entries

| Module | Symbols verified | Rationale |
|---|---|---|
| `aeat.core.errors` | 28 (registry + rendering + 11 domain-specific exceptions) | Per ADR Public surface — canonical errors stay in `aeat.core.errors`; moved domain-specific exceptions use canonical destinations. |
| `aeat.adapters.outbound.aeat.auth` | 11 (AEAT auth + access-gate + restrict_file_permissions) | Per ADR Public surface — split across canonical auth, application auth, access-gate, and file-permission destinations. |
| `aeat.adapters.outbound.aeat.export` | 1 (`LiveSubmitForbiddenError`) | Per ADR Constraints — relocated to `aeat.core.access_gate._errors`; old-path compatibility is not retained. |
| `aeat.domain.formulas` | 8 (Engine + period + ruleset + ledger + registry) | Public surface for the per-modelo formula engine; stable across the move. |

## verification

- Historical: `uv run --no-sync python scripts/verify_shims.py` → all 4 entries `ok`; exit 0.
- Delivered: script removed; import-contract tests verify canonical public surfaces and deleted root-module absence.

## findings (FIX / FILE / STRIKE)

- **FIX (in this PR)**: missing `restrict_file_permissions` export at `aeat.adapters.outbound.aeat.auth`.
- **FILE deferred**: `bind_error_code` was originally listed in the ADR public-surface table for the rendering-pipeline cluster but is currently an internal helper used only by `AeatError.__init_subclass__`. Audit decision: not included in the historical verification contract (no external consumers). If a future consumer surfaces a need for `bind_error_code` on the public surface, add it to `aeat.core.errors.__init__.__all__` and the import-contract tests.

## next step

Step 5 PR 3 — mechanical rebase script (`scripts/rebase_imports.py`) + test fixture covering relative imports / TYPE_CHECKING blocks / star imports / dynamic `importlib.import_module` calls. Forward + reverse rewrite maps for post-Step-9 rollback symmetry.
