---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:042fbe0f3e9337dd073ae7f7fc8c4fc708a64eb43de6d48cb7b1c2bd709c2a37'
step_id: 'S90'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Repair mixed-commit drift and restore the binding CADRUMO display contract

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/core/tests/test_product_identity.py`
- `src/cadrumo/tests/test_parity.py`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `S90 execution record`

## Description

- Reopen the identity, runtime, locale, and parity steps invalidated by mixed commit `12d80d1d42`.
- Restore `CADRUMO` as the product display value in the accepted ADR, runtime identity, and contract expectations.
- Preserve `aeat` as the sole human CLI executable and `AEAT` as the Spanish tax authority referent.
- Remove the regressed wordmark-only and title-case prose mandate while retaining the exact machine-identity matrix.
- Verify the source and generated naming rules remain synchronized without editing them.
- Preserve the concurrent open S89 plan row exactly while excluding its locale catalogues and execution record from this repair.

## Outcome

- The binding product display contract is again exactly `CADRUMO`; lowercase machine identifiers, the `CADRUMO_` environment prefix, companion names, and the `AEAT` authority boundary remain intact.
- Steps S05, S86, and S62-S66 are open for fresh evidence. Existing open steps S25 and S67 remain open.
- Step S89 remains open and its pre-existing plan row is cross-committed unchanged because the shared plan is required by S90.
- The correct CADRUMO documentation-template hunk from the mixed commit was left untouched.
- Nine focused identity and parity tests, Ruff lint, the live identity assertion, naming-rule status, and the Vaultspec plan check passed.

## Notes

- The untracked S89 execution record and concurrent locale YAML changes were neither staged nor committed.
- The reopened steps intentionally remain open after S90 closure so later dedicated execution can provide fresh evidence.
- The full parity module passed 31 tests and failed only `test_inter_locale_parity`: concurrent S89 catalogue work leaves two keys absent from English and Spanish relative to Catalan.
- Ruff format check reports pre-existing formatting drift in `test_parity.py`; the same check fails against the committed HEAD version, and this Step intentionally changes only four contract expectations in that file.

## Status note: retired by S87 contextual-casing remediation

The Description and Outcome above are preserved as historical execution
evidence, not active instructions. S87 retires this reopened lane without
re-executing it: directives to remove `Cadrumo` prose or restore an exact
all-caps prose display are superseded by the binding contract of `Cadrumo` in
sentence prose and `CADRUMO` in identity contexts.
