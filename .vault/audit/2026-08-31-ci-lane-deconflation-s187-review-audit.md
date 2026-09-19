---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7d2d3666691accc77fa38dbe5548632106eaf5336bc81a47e1991c4603cefd42'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `Review P05 S187 invoice row materialization`

## Scope

Independent review of immutable P05.S187 commit `fa87bac54a`, its execution record and plan change, M347/M349 row-materialisation ownership and cycle boundary, direct test repoint, focused test evidence, size/baseline/policy scope, and plan isolation from current peer worktree state.

## Findings

### private-core-import | high | The parity test gains an unrelated cross-package private import

`src/cadrumo/domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py` changes its local `bundled_path` import from `.....core.resources` to `.....core.resources._boundary`. `_boundary.py` is an underscore-private core module; importing it from the domain registry test violates the canonical direct-public-import boundary. This is not needed for the intended M349 materialisation-contract repoint, which is the test's direct import of `Modelo349OperadorTotalsParity` and `compute_modelo_349_operador_totals_parity` from `_invoice_row_materialization.py`. The extra resource import hunk is introduced by this immutable commit and should not be attributed to the extraction.

The intended extraction is otherwise sound: the 577-line private sibling owns the M347/M349 materialisation family; `invoice_bindings.py` is its sole production consumer and injects `_m347_row_family_threshold_filter`. The sibling restricts `InvoiceObservation` to `TYPE_CHECKING` and imports the resolver locally only at parity computation time, avoiding an initialization cycle and facade. Direct import smoke passed; ruff and formatting passed; focused collection found 49 and the focused run completed cleanly. The original contracts from 1439 to 894 lines, below the 1250 cap, with sibling size 577 and no baseline or policy change. The immutable plan diff changes only `body_hash` and S187; current P02 plan changes are peer worktree residue.

## Recommendations

Repair `private-core-import` in a scoped S187 correction: remove the unintended `_boundary` import change from the parity test (restore the parent import while the resource public-surface migration is owned separately). Do not introduce a forwarding facade to preserve the private path. Re-run the six-file 49-test command and the existing lint/format checks.
