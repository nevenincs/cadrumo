---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:eac0d4314f7d6cda642f25669d64e754469c5c042536ccd77524c8d0fd60f812'
step_id: 'S321'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the three family-2 delegate wrapper shims the import-hygiene gate refuses, by repointing their consumers rather than editing an exemption list: `append_bucket_events` and `decimal_to_string` in the ledger actions-common module and `earliest_safe_erase_date` in the retention floor module are forwarding wrappers, which the architecture rules prohibit outright. RECOUNT THE CONSUMERS RATHER THAN INHERITING THESE FIGURES -- a prior measurement found 2, 7 and 23 references respectively, but the 23 includes test references and at least one JSON payload key in the config-reset surface that is a STRING and not an import, so the real repoint count is smaller and a sweep driven by the raw number will touch things that are not import edges. Repoint every genuine consumer at the owning module's canonical definition, delete the wrappers, and land it atomically with `pytest --collect-only -q` clean immediately before; never resolve it by widening the documented-exemption inventory, which would convert a prohibited construct into a permanently accepted one. Note when reading the gate: production Family-1 stands at 137 and test-only at 165, which LOOKS like a regression against the previously reported 114 and 127 and is not -- the scanner was widened to judge private imported names as well as private target modules, so it now reports reaches it could never previously see; the gate's own failure text does not say this

## Scope

- `the ledger actions-common and actions-export modules`
- `the retention floor module`
- `every genuine import consumer of the three wrappers`
- `and the family-2 exemption assertion`

## Changes

- `M` `src/cadrumo/application/ledger/actions_common.py`
- `M` `src/cadrumo/application/ledger/actions_import.py`
- `M` `src/cadrumo/application/ledger/actions_export.py`
- `M` `src/cadrumo/application/ledger/actions_manual.py`
- `M` `src/cadrumo/domain/retention/_floor.py`
- `M` `src/cadrumo/domain/retention/__init__.py`
- `M` `src/cadrumo/domain/retention/tests/test_floor.py`
- `M` `docs/conf.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -k "delegate_wrapper" -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/domain/retention -m unit -n0` -> `fail`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/domain/retention --collect-only -q` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format --check` / `ty check` on the touched trees -> `pass`

## Notes

**Consumer recount.** The row's remembered figures were 2, 7 and 23 references.
The genuine import edges are 1, 5 and 0 call sites. `append_bucket_events` had
one consumer module; `decimal_to_string` had two external plus one internal;
`earliest_safe_erase_date` had ZERO external consumers -- its only call site
was inside its own module. Every other occurrence of that name in the tree is
the `RetentionBlockingRecord.earliest_safe_erase_date` model field, a locale
placeholder, or a JSON payload key in the config-reset surface. A sweep driven
by the raw 23 would have renamed a model field.

**Three details preserved by hand, each avoiding a later defect.** The
`build_ledger_bucket_event` docstring referenced the deleted function through a
Sphinx role; left alone it would have crashed the next nitpicky docs build on a
dangling target, so it was rewritten. The LGT art. 67 anchoring rationale
carried by the deleted retention wrapper was MOVED into
`assess_retention_floor`, which is where the floor is now applied, rather than
discarded with the code. The stale `docs/conf.py` nitpick-ignore entry naming
the retired symbol was removed.

**A red first run, recorded.** The first suite run was 170 failed / 1271
passed, from one defect of mine: `decimal_to_string` was deleted without adding
`format_decimal` to one consumer module's imports. Found, fixed, re-run. The
green result was reached through that correction, not on the first attempt.

**Remaining failures are not attributable to this work, by reasoning rather
than by bisection.** The re-run left 14 failures. Three are a public-module
inventory gate naming repository modules relocated by another change; eleven
are IVA category classification. This change touches decimal formatting,
bucket-event emission and a retention floor, none of which has a path to IVA
classification, and none of the fourteen names any of the eight files above. A
stash-based confirmation was not available in this shared tree, so this is a
reasoned attribution and is not claimed as a proof.

**Family-1 hygiene failures deliberately not absorbed.** The full hygiene gate
reports 5 failures on the Family-1 baseline and test-debt count/set assertions
(137 production, 165 test-only against a 114/127 baseline). These follow the
scanner being widened to judge private imported names as well as private target
modules. No baseline or exemption inventory was edited. This change only ever
removed imports, so it cannot have contributed.

**Gate proven to bite.** A forwarding wrapper was reintroduced at runtime from
outside the repository and the real scanner detected it; the file was removed
and left no residue. The same run's before-state independently confirmed the
three deletions took, leaving only the one documented exemption.

**Provenance.** This work was committed by another agent's broad commit
`0f79a7a18d` before its author reached the commit step. Content was verified
intact at HEAD across all eight paths. History was not rewritten. No commit
subject names this Step, so this record is the only surviving provenance for
the change.

**Production reachability.** Positive and direct: `emit_bucket_events` is now
called on the live ledger import path, `format_decimal` on the manual
transaction event payload and CSV export paths, and `shift_by_calendar_years`
inside `assess_retention_floor`, the retention domain's sole public assessment
entry point. The two rewritten floor tests drive that public entry point rather
than reaching past it.
