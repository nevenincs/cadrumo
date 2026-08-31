---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:354ad11c2d9826a68cd3fa42a72ab1eb32f8c057faa7da796fcf6e3b7f7e6a42'
step_id: 'S34'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep the dev quality dispositions and CLI benchmark goldens

## Scope

- `dev/`

## Changes

- `M` `dev/quality/cli_action_census_dispositions.toml`
- `M` `dev/docs/sequences/_schema.py`
- `M` `dev/docs/tests/test_static_frame_reasons.py`
- `M` `dev/locales/tests/test_ledger_notice_action_conformance.py`
- `M` `dev/locales/tests/test_s89_action_conformance.py`
- `M` `dev/tests/test_utf8_enrollment_inventory.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_archive_reconcile.py`
- `M` `dev/benchmarks/cli/capture_baseline.py`
- `M` `dev/benchmarks/cli/baseline.json`
- `M` `dev/benchmarks/cli/baseline.census.json`
- `verify:` `pytest dev/docs/tests + dev/locales/tests (sequential)` -> `pass`
- `verify:` `capture_baseline.py --check` -> `pass`
- `verify:` `dev.quality.cli_action_census_dispositions --current-tree` -> `69 residual, all peer-owned`

## Notes

Two defects were found here, both introduced by this campaign. The S89 config
module scope had `_google_sync_calc.py` RENAMED to `_modelo_spreadsheet_cli.py`
when the file had in fact left `_config/` and needed deleting from the set; the
three modules the archive subject added were also absent. And moving
`_app_maintenance.py` into `_config/` brought it under that directory's ban on
`tr(..., default=...)` fallbacks, which it had carried legally outside it; the
three fallbacks are removed, their keys already being present in all four
catalogues.

The tracked `dev/benchmarks/cli/baseline.census.json` is NOT refreshed. It was
already stale before this campaign (peer verbs `evidence attachment-queue`,
`attachment-view`, `inventory closing-authority-record`, `modelo work run` are
live and absent from it), re-capture requires an uncontended tree, and
hand-editing it would fabricate timing provenance.

**Completion.** Both halves of this Step are now done, and the Step is CLOSED.
The earlier body above described work toward it and left the benchmark goldens
unrefreshed; that condition no longer holds.

**Half A, dev quality dispositions.** `dev.quality.cli_action_census_dispositions
--current-tree` went from 77 findings to 69. The eight cleared were all
campaign-owned: three stale `action_identity` rows in
`application/operator_surface/_help.py` left by this campaign's own show->view
rename (`_app_help` audit, `_config_help` profile, `_config_storage_section`
storage), the paired "missing" rows the same rename created, and the
`_ledger_lifecycle_cli.py::ledger_evidence_pull` pair. The mechanical
`--write-current` adjudicator was deliberately NOT used: it rewrites every
candidate row and would have claimed roughly seventy rows of concurrent peer
relocation work. The residual 69 findings are exactly that peer work
(`_actions_*.py` -> `actions_*.py`, `_models.py` -> `models.py`, wizard,
workflow) and clear when its consumer sweep lands.

**Half B, CLI benchmark goldens.** Both artifacts are re-captured:
`dev/benchmarks/cli/baseline.json` and its derived
`dev/benchmarks/cli/baseline.census.json`. The capture tool itself had to be
repaired first — `_policy_payload` read `node.execution_policy`, an attribute
deliberately removed from `LiveCommandNode` ("Policy is intentionally absent from
this Click census"), so the tool could not run at all. It now resolves policy
through `command_execution_policy_for_cli_path`, the public entrypoint boundary
written for cross-distribution consumers; no API was promoted and no private
import was added.

**What the baseline attests, and what it does not.** The artifact is
captured-and-valid-at-digest. It is NOT permanently current: verification with
`require_current_source` compares the recorded manifest against the live tree and
refuses with "baseline source snapshot is stale against the current source tree",
and this worktree takes peer commits continuously. Read the pair as evidence of
the surface at its snapshot digest, not as a standing claim about HEAD.

**Deliberately unfixed, and why.** Six dead-verb prose citations remain, all in
directories a concurrent peer campaign is actively restructuring, where an edit
would collide with in-flight work:
`adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py:3`,
`adapters/outbound/google/tests/test_drive_folder_bulk_fetch_roundtrip.py:3`,
`application/ledger/evidence.py:13`, `domain/attachments/_enums.py:75`, and
`google sync calc` prose in `adapters/outbound/google/` and
`application/storage/calc_sheets/`. They are citations only; no runtime value
reads them.

**Carried forward, not closed here.** A repair-policy row governing a retired
verb, and the governance regression this campaign's own D2 rename introduced, are
recorded in the eighth addendum of the close-honesty audit. Neither is fixed by
this Step.

**Attribution note.** The file changes listed above are already in HEAD. A
concurrent peer's broad commits absorbed them under unrelated subjects, so they
cannot be found by commit message; locate them by path and timestamp.
