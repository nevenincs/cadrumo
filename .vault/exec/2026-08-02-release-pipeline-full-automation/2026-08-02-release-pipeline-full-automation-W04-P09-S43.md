---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:3df646f1dd74179481a97953282ca40b615fa3c74ce008f027a64259bc79ec77'
step_id: 'S43'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Record the release-alert label as a named operator provisioning action alongside OP-10 so the forge state the default alerting path depends on is verifiable rather than assumed, and extend the read-only environment inventory probe to report whether that label exists, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions section asserting the label item, and uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes over a fixture payload with the label absent

## Scope

- `dev/release/environment_inventory.py`
- `dev/release/tests/test_environment_inventory.py`
- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

Added `LabelRecord` and `fetch_label()` to `dev/release/environment_inventory.py` (the same read-only forge probe extended for orphan detection in S36), reading `gh api repos/{repo}/labels/{name}` and distinguishing three outcomes exactly as `fetch_environments` already does: `exists=True` (confirmed present), `exists=False` (a genuine 404, read from the API's own JSON `status` field rather than gh's CLI wrapper text — real, actionable state), and `exists=None` (gh missing, a timeout, or any other failure — never guessed as absent). `main()` now fetches and reports the `release-alert` label alongside the environment inventory; the `--json` output shape changed from a bare list to `{"environments": [...], "labels": [...]}`.

Live-measured the forge myself before writing anything: `gh api repos/nevenincs/cadrumo/labels/release-alert` → 404. Confirmed the label genuinely does not exist.

Added the `release-alert` label creation as a named item "alongside OP-10" in RELEASING.md's Operator actions section — held until S49 (another agent, concurrently adding OP-10/OP-11 to the same section) landed, per the coordination note, then added my paragraph after theirs. Names the `gh label create` command and the `environment_inventory` verification path.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests -q -k environment_inventory` — 23 passed (17 pre-existing + 6 new). `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q` — 9 passed, extended to assert the `gh label create release-alert` command and `dev.release.environment_inventory` module are both named in the operator-actions section. Landed as two commits: `b2cacd6444` (module + tests, ahead of S49) and `b071adcc7f` (RELEASING.md + the extended test, after S49's `24bc845cee` landed) — both verified via `git show --stat` immediately after committing.

## Notes

No incidents. Deliberately split into two commits to respect the coordination note: the `environment_inventory.py`/test portion has no dependency on RELEASING.md's current shape and landed immediately; the RELEASING.md portion waited for S49's concurrent edit to the same Operator actions section to land first, avoiding a paragraph collision. The `ALERT_LABEL` string is declared as a local literal in `environment_inventory.py` rather than imported from `dev.release.alerting.ALERT_LABEL` — that module was uncommitted/live-WIP (task #12/#16) at the time and importing it would have made this module's commit order depend on that one's; documented as a must-stay-byte-identical duplication in both modules' comments.
