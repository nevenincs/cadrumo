---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:b0bee82c7724630a15d8c72a09cecd8ca5ca5008d1eafd165c0b8a1cd910bd04'
step_id: 'S351'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Relocate the modelo cross-period lifecycle seeding out of a package-private test-support module so S333 can reach it, and DECIDE which of two homes it takes, because the cheap-looking one has a dependency chain behind it. The cluster is `seed_clean_cross_period_sources` plus `_seed_clean_cross_period_sources`, `_cross_period_source_groups`, `_source_casilla_values`, `_resolved_revision` and the `_T0` clock, in `application/modelo/tests/_file_flow_support.py`, whose seven consumers all sit inside `application/modelo/tests/`. The conformance matrix lives in `entrypoints/tests/`, so reaching it there is a cross-package PRIVATE import the architecture rule rejects; duplicating the ~80-line seeding is the duplicated-symbol defect the same rule rejects; and dropping the cases needing it narrows the matrix's claim, which S333 forbids. ARM ONE, the canonical home: move it to `src/cadrumo/tests/`, which the evidence says is the shared test-support home -- every cross-package test-support import in the tree resolves there and nothing imports another package's tests directory. THE CATCH, measured not assumed: the cluster calls `create_work_unit`, whose canonical defining module is the PRIVATE `application/modelo/_work_lifecycle.py`. Today `_file_flow_support` reaches it intra-package, which is legal; from `src/cadrumo/tests/` the same call becomes a cross-package private reach, so this arm ADDS a test-only private reach to a baseline that is currently red and must not be touched. Taking it honestly therefore pulls in a SECOND relocation -- promoting `create_work_unit` to a public defining module -- which the architecture rule already independently requires, since roughly ten test modules under `application/aggregation/tests/` and `application/calculations/tests/` reach it cross-package today. ARM TWO, the narrow home: de-privatise in place to a public `application/modelo/tests/cross_period_seeding.py`, keeping the intra-package `create_work_unit` reach legal and adding no debt, at the cost of `entrypoints/tests/` importing another package's tests directory -- which has one precedent in the tree and no other. Pick an arm, record why, and land it as ONE atomic explicit-path commit tagged `relocation:seed_clean_cross_period_sources`, running `pytest --collect-only -q` immediately before and after. `_resolved_revision` has five further uses inside the 706-line origin, so it moves with the cluster and the origin imports it back rather than keeping a second copy

## Scope

- `application/modelo/tests/_file_flow_support.py`
- `the chosen public home`
- `its seven consumers`
- `and whatever create_work_unit's promotion touches if that arm is taken`

## Changes

- `R` `src/cadrumo/application/modelo/_work_lifecycle.py` -> `src/cadrumo/application/modelo/work_lifecycle.py`
- `A` `src/cadrumo/tests/cross_period_seeding.py`
- `M` `src/cadrumo/application/modelo/tests/_file_flow_support.py`
- `M` `src/cadrumo/application/modelo/tests/test_amend_flow.py`
- `M` `src/cadrumo/application/modelo/tests/test_file_flow_calculation.py`
- `M` `src/cadrumo/application/modelo/tests/test_file_flow_events.py`
- `M` `src/cadrumo/application/modelo/tests/test_file_flow_verify.py`
- `M` `src/cadrumo/application/modelo/tests/test_iva_wallet_engine_filing.py`
- `M` `src/cadrumo/application/modelo/tests/test_verify_report_idempotent_collapse.py`
- `M` `docs/api/cadrumo.application.modelo.rst`
- `A` `docs/api/cadrumo.application.modelo.work_lifecycle.rst`
- `D` `docs/api/cadrumo.application.modelo._work_lifecycle.rst`
- `verify:` `pytest --collect-only -q src/cadrumo` -> `28693 before and after, 0 errors`
- `verify:` `pytest -n0 -p no:randomly` on the three heaviest consumers -> `5 failed / 36 passed, identical against clean HEAD`

## Notes

ADJUDICATION, and it CORRECTS AN EARLIER FIGURE OF MINE: the internal-symbol
count is FOUR, not six. An initial single-line regex missed multi-line
`from ... import (` blocks and undercounted cross-package consumers of
`rename_work_unit` and `discard_work_unit` as zero. A multiline AST-grade
pass gives:

SHARED (promote): `create_work_unit` 21, `get_work_unit` 7,
`list_work_units` 5, `discard_work_unit` 3, `rename_work_unit` 2,
`lifecycle_continuation_for_work_list` 2,
`lifecycle_continuation_for_work_history` 1,
`ModeloWorkLifecycleContinuation` 1.

INTERNAL (4, zero cross-package): `require_active_work_unit`,
`require_revision_parent_active`, `ActiveWorkUnitUse`,
`RevisionParentOperation`.

FOR A QUESTION ABOUT IMPORTS, PARSE -- DO NOT MATCH. Import statements span
lines, alias, and nest; every regex answer is a lower bound indistinguishable
from an exact one.

Promoted WHOLE at 8 shared of 12, because the four internal symbols share
five private helpers with the shared ones and a split would leave a public
module importing a private sibling to reach them. Contrast the S358 record:
2 of 57 there warranted a narrow module instead.

Scope also corrected: 122 import sites across 31 cross-package files, not
the "roughly ten test modules" the row estimated.

A pure forwarding wrapper (`seed_clean_cross_period_sources` delegating to
an identically-signatured private twin) was collapsed in passing.

NOT VERIFIABLE while uncommitted: `dev/tests/test_import_hygiene_gate.py`
reads `git ls-files`, so it sees the tracked-but-deleted old path and cannot
see either new module. Its verdict on this relocation is meaningless until
the change lands. The ratchet shrink this relocation requires
(`import_hygiene_baseline.json`, an exact-set ratchet, ~31 reaches removed)
is therefore NOT done. RELEASING CONDITION: the change lands.
