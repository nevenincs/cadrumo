---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b583bc0e22c2f0c8515a46f33c5f126a1aaca0918be78a9cd26d1109dd134e3f'
step_id: 'S102'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-run operation catalogue, recovery-action, migration-manifest, import-linter, AST, and Textual-location fixed-point gates

## Scope

- `src/cadrumo/tests`

## Changes

- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_operation_catalogue.py -m unit -n0` -> `fail`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py dev/tests/test_tui_migration_manifest.py src/cadrumo/tests/test_importlinter_ledger.py -m unit -n0` -> `fail`
- `verify:` `uv run --no-sync pytest dev/tests/test_cli_action_census_dispositions.py dev/tests/test_action_coverage_closure.py -m unit -n0` -> `fail`

## Notes

No code changed in this Step; it is a re-run. Four of the six named gate
families live under `dev/` rather than the path the Step row cites.

Recovered since the earlier run in this Phase: the migration-manifest fixed
point, the Textual-location gate, the retired-TUI fixed point, the canonical
TUI package importability check, the launch-seam gate and the delegate-wrapper
exemption gate are all green again. Every one of them was red earlier only
because a half-landed rename left the calculation-sheets package unimportable
in the shared working tree. That has since cleared, which confirms the earlier
reading: those failures were working-tree state, not regressions.

Still red, in three classes, none of them originating in this Phase.

The import-hygiene scanner reports 134 production cross-package private
reaches against a hard-zero baseline and 165 test-only reaches against 32
documented. The scanner was widened to judge imported names as well as target
modules, so it now reports reaches it previously could not see. The numbers
are recorded rather than accommodated; no baseline or debt inventory was
touched.

The import-linter ledger fails on three counts because its pinned module names
no longer resolve on disk: the compensation-history module and the
calculation-sheets parity harness were both renamed from private to public by
relocations elsewhere, and the linter configuration was not swept in the same
change. A related test-debt entry now records an occurrence that no longer
happens. This is a relocation that did not land atomically, and it is reported
for its owner rather than repaired here.

The recovery-action census fails because several ledger actions carry no
disposition, and the action-coverage closure fails alongside it. That is
ledger work enrolling actions without registering them, again outside this
Phase.

The operation-exposure census reports eight joins green and one red, which is
its recorded and deliberate state: the projection claims that reach no surface
are the finding, and reconciling them is tracked separately.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
