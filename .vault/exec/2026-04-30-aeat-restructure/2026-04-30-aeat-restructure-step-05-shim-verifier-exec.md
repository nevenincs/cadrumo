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

# 2026-04-30-aeat-restructure step-05 public-surface verification (superseded)

## status

SUPERSEDED. The planned shim-verification subroutine (`scripts/verify_shims.py`)
was authored and run once during Step 5 tooling prep, but the approach it was
designed to gate — a backward-compat re-export layer at old import paths — was
NOT adopted. The project uses a hard-cutover migration model: every rename or
relocation is accompanied by a same-change-set update of every caller, so no
old-path shim is ever introduced and no ongoing shim-verification is needed.
`scripts/verify_shims.py` was subsequently deleted before the Step 7 keystone PR.

This record is retained for historical traceability of the `restrict_file_permissions`
gap-fix finding (see below), which IS permanent and was correctly applied regardless
of the migration model.

## what was planned (not adopted)

A `scripts/verify_shims.py` script declaring a PUBLIC_SURFACE_CONTRACT (4 module
entries; approximately 50 symbols total) was planned as a Step 8 acceptance-gate
precondition for classifying the semver bump (minor vs major). It would have:

- imported each declared module path in a clean Python subprocess
- emitted a structured JSON report
- exited 0 if all symbols were reachable, 1 otherwise

This was superseded by the hard-cutover model, which makes per-symbol reachability
at old paths a non-requirement.

## audit-grounded gap-fix (permanent, adopted)

During the single run of `scripts/verify_shims.py`, a real public-surface gap was
surfaced: `restrict_file_permissions` was NOT actually exposed on
`aeat.adapters.outbound.aeat.auth`. The function existed at
`aeat.adapters.outbound.aeat.auth._file_permissions.restrict_file_permissions`
and was imported only via the relative path internally; no entry on
`aeat.adapters.outbound.aeat.auth.__init__.py` `__all__` + import block.

Fix applied:

- Added `from ._file_permissions import restrict_file_permissions` to
  `aeat.adapters.outbound.aeat.auth.__init__.py`.
- Added `"restrict_file_permissions"` to the `__all__` list (alphabetical
  position between `preload_into_browser_context` and `select_provider`).

This fix is valid under both the original shim model and the adopted hard-cutover
model: the symbol is correctly exposed at its canonical path.

## findings disposition

- **FIX (applied, permanent)**: missing `restrict_file_permissions` export at
  `aeat.adapters.outbound.aeat.auth`.
- **FILE deferred**: `bind_error_code` was originally listed in the ADR
  public-surface table for the rendering-pipeline cluster but is currently an
  internal helper used only by `AeatError.__init_subclass__`. Not included in
  any public-surface contract (no external consumers). If a future consumer
  surfaces a need, add to `aeat.core.errors.__init__.__all__`.
