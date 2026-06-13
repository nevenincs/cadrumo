---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-05-import-linter-contract-exec]]"
---

# 2026-04-30-aeat-restructure step-05 shim-verification subroutine

## status

Step 5 PR 2 of N. Lands the shim-verification subroutine that the Step 8 acceptance gate uses to deterministically classify the semver bump (minor vs major). Per ADR Shim-verification gate.

Historical execution note: this step documents a pre-hard-cutover
tooling path. The delivered rollout removed root compatibility modules
and did not retain a shim layer; `scripts/verify_shims.py` was later
removed as part of the hard-cutover continuation.

## scope

- New script `scripts/verify_shims.py` declaring the public-surface SHIM_CONTRACT (4 module entries; ~50 symbols total).
- Subprocess-isolated import per shim with structured JSON report.
- Exit 0 on all-shims-OK; exit 1 on any broken shim.

## audit-grounded fix discovered during PR

The shim verifier surfaced a real public-surface gap pre-Step-7: `restrict_file_permissions` (per ADR public-surface table) was NOT actually exposed on `aeat.adapters.outbound.aeat.auth`. The function existed at `aeat.adapters.outbound.aeat.auth._file_permissions.restrict_file_permissions` and was imported only via the relative path internally; no entry on `aeat.adapters.outbound.aeat.auth.__init__.py` __all__ + import block.

Fix applied in this PR:
- Add `from ._file_permissions import restrict_file_permissions` to `aeat.adapters.outbound.aeat.auth.__init__.py`.
- Add `"restrict_file_permissions"` to the `__all__` list (alphabetical position between `preload_into_browser_context` and `select_provider`).

This made the ADR's public-surface promise concrete in the pre-cutover
plan. It is not an active compatibility contract after the delivered
hard cutover.

## SHIM_CONTRACT entries

| Module | Symbols verified | Rationale |
|---|---|---|
| `aeat.core.errors` | 28 (registry + rendering + 11 domain-specific exceptions) | Per ADR Public surface — preserved via shim from `aeat.core.errors` + 3 domain destinations. |
| `aeat.adapters.outbound.aeat.auth` | 11 (AEAT auth + access-gate + restrict_file_permissions) | Per ADR Public surface — preserved via shim from `aeat.adapters.outbound.aeat.auth` + `aeat.application.auth` + `aeat.core.access_gate` + `aeat.core.file_permissions`. |
| `aeat.adapters.outbound.aeat.export` | 1 (`LiveSubmitForbiddenError`) | Per ADR Constraints — relocates to `aeat.core.access_gate._errors`; old path keeps shim. |
| `aeat.domain.formulas` | 8 (Engine + period + ruleset + ledger + registry) | Public surface for the per-modelo formula engine; stable across the move. |

## verification

- `uv run --no-sync python scripts/verify_shims.py` → all 4 entries `ok`; exit 0.

## findings (FIX / FILE / STRIKE)

- **FIX (in this PR)**: missing `restrict_file_permissions` export at `aeat.adapters.outbound.aeat.auth`.
- **FILE deferred**: `bind_error_code` was originally listed in the ADR public-surface table for the rendering-pipeline cluster but is currently an internal helper used only by `AeatError.__init_subclass__`. Audit decision: NOT included in SHIM_CONTRACT (no external consumers) — but the inclusion in the ADR table reflects original intent. If a future consumer surfaces a need for `bind_error_code` on the public surface, add to both `aeat.core.errors.__init__.__all__` AND the SHIM_CONTRACT in this script.

## next step

Step 5 PR 3 — mechanical rebase script (`scripts/rebase_imports.py`) + test fixture covering relative imports / TYPE_CHECKING blocks / star imports / dynamic `importlib.import_module` calls. Forward + reverse rewrite maps for post-Step-9 rollback symmetry.
