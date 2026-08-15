---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:6e73c6420c3d69d604319b5973057accc28faa40bbbc4ae3bc1990e7991ada31'
step_id: 'S171'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium regenerate the two generated quality manifests that still name the retired workspace-initialisation package and its three symbols, once the tree is quiet enough that regeneration does not sweep concurrent peer work into the change, neither manifest sitting inside the test paths so neither reds collection and both therefore drifting silently

## Scope

- `dev/quality/fixture_ownership.toml and dev/quality/error_code_default_recovery_rehoming.toml`

## Description

- Confirm which of `dev/quality/fixture_ownership.toml` and
  `dev/quality/error_code_default_recovery_rehoming.toml` is truly a
  regenerate-from-scratch manifest versus a hand-curated ledger validated
  against live evidence.
- Probe whether the tree is quiet enough for `fixture_ownership.py --write` to
  complete: run its guarded snapshot-before/after check repeatedly.
- Edit the one stale `setup/_service.py` ownership entry out of the
  `AuthProviderReservedError` row in `error_code_default_recovery_rehoming.toml`.
- Expand the row's subject per the dispatcher's message to the two further
  ledgers found citing retired custody-verb spellings:
  `dev/quality/cli_action_census_dispositions.toml` and
  `dev/quality/error_code_default_suggestion_preimage.json`.
- Remove the thirteen stale `cli_action_census_dispositions.toml` rows citing
  a deleted `_status_screen.py` `_RECOVERY_COMMANDS` module list and a deleted
  `_help.py` `_config_custody_section` function.
- Establish that `error_code_default_suggestion_preimage.json` is a
  commit-pinned historical ledger by design, not stale, and leave it untouched.

## Outcome

**`dev/quality/fixture_ownership.toml` — GENERATED, NOT regenerated; tree too
noisy.** Its schema (`fixture-ownership-v6`) and `write_manifest`/`check_manifest`
functions confirm it is a pure deterministic walk with no hand-curated fields.
The generator itself guards against exactly the hazard this row names: it
snapshots the source tree before and after the census and refuses if anything
changed mid-run. Five consecutive `--check`/`--write` attempts across this
session, spaced by the time each ~100-second walk took, every one refused with
a DIFFERENT set of concurrently-changed files (`user_profile/__init__.py`,
`workflow/_models.py`, `calculations/_m303_regimen_simplificado_annual_summary.py`,
`profile_custody/__init__.py`, `user_profile/_capsule_record.py`,
`wizard/__init__.py`, `wizard/_commands.py`, `workflow/__init__.py`,
`workflow/_profile_health.py`, `core/errors/registry/_application_part2.py`,
`domain/calculations/registry/_validate_export_layout_coverage.py` (added),
`domain/calculations/registry/_validate_revision_sections.py`,
`entrypoints/cli/_config/_manager_actions.py`, `_manager_frontend.py`,
`tests/test_config.py`, `tests/test_s89_action_conformance.py`), spanning
application, entrypoints and registry packages. This is the tool's own
race-guard biting, not a hypothesis: the tree is not quiet enough right now,
and every attempt cost roughly two minutes without ever completing. Per the
row's own condition, this was NOT forced. What would be run once the tree is
quiet: `uv run --no-sync python -m dev.quality.fixture_ownership --write`
from the repo root, followed by a diff review before trusting the result.
The single stale entry it carries
(`src/cadrumo/application/setup/tests/test_atomic_create_roundtrip.py:37:_cli_storage`)
is confirmed stale — the package is deleted and the fixture now lives at
`src/cadrumo/application/user_profile/tests/test_atomic_create_roundtrip.py:38` —
but it was left alone rather than hand-edited, since a generated manifest's
computed hashes, group ids and member counts cannot be correctly hand-derived,
and a hand-edited generated file is clobbered by the next honest regeneration
anyway.

**`dev/quality/error_code_default_recovery_rehoming.toml` — HAND-MAINTAINED,
edited.** Its `main()` only validates (`validate_rehoming_ledger`) or migrates
from a legacy ledger; there is no scan-and-regenerate mode, and ownership
(`owner_step`) is a curated judgement, not a mechanical derivation. Removed the
one stale ownership row (`AuthProviderReservedError`, `setup/_service.py:68`,
`owner_step = "S109"`) whose cited file no longer exists. Verified with a probe
script comparing `_scan_current_source()`'s live-source fingerprints against the
ledger row: current source carries exactly 4 fingerprints for this qualname
(the `_operator.py` constructor plus three `_auth.py` references); the ledger
carried 5 before the edit and 4 after, and the two multisets now match exactly.
Confirmed by running the module's validator before and after: `diff` of the two
runs shows exactly one line removed —
`E_REHOMING_FINGERPRINT_MULTISET:cadrumo.application.auth._operator_results.AuthProviderReservedError`
— and no new finding introduced. The historical `historical_old_value_source`
field on a *different* row (line 164, `"aeat config recover"`) was left
untouched: that field is permanently pinned evidence of what a past commit's
source said, never validated against live source, so it is not stale by this
gate's own design.

**`dev/quality/cli_action_census_dispositions.toml` — HAND-MAINTAINED, edited
(expanded scope).** Its full-coverage reconciliation (`checked_in_dispositions`)
runs against a pinned git revision argument passed at the CLI, and is not
wired into any pytest test — only `validate_exception_override_owners`, a
narrower sub-check keyed on `migration_step`, runs as a gate
(`test_checked_in_exception_override_owners_cover_each_live_physical_observation`).
Removed thirteen stale rows across three groups, each confirmed stale by
checking the cited symbol against `git show HEAD:<path>`:
- Six rows (plus one un-listed sibling, `aeat config login NAME`, discovered
  in the same block) citing `src/cadrumo/adapters/inbound/tui/_status_screen.py`
  lines 52-57's `_RECOVERY_COMMANDS` module list — confirmed absent from HEAD's
  copy of the file entirely (zero matches for `recovery`/`passphrase`/
  `RECOVERY_COMMANDS`).
- Six rows citing `_config_custody_section` in
  `src/cadrumo/application/operator_surface/_help.py` — confirmed the function
  itself no longer exists at HEAD.
- One row citing `_root_help`'s former `aeat config recover` HelpEntry —
  confirmed HEAD's `section_recovery` now offers `config login NAME`,
  `config repair`, `config repair profile` instead.
Total: thirteen rows removed (twelve matching the dispatcher's cited line
numbers, plus the un-listed `config login NAME` sibling from the same dead
`_status_screen.py` block, removed for consistency since leaving one stale row
from an otherwise-fully-swept defunct code path would be a half-fix). The
narrower gate that IS wired to pytest
(`test_checked_in_exception_override_owners_cover_each_live_physical_observation`)
was run before and after: it fails both times, but every failing row in both
runs cites files this row's scope does not own
(`_reconcile.py`, `operator_surface/_contract.py`, `_projection.py`,
`operator_surface/_errors.py`, `storage_management/_errors.py`,
`registry/_errors.py`, `contribuyente/_errors.py`, `user_profile/_errors.py`,
`wizard/_commands.py`, `adapters/inbound/censo/_parser.py`) — none of the
thirteen removed rows carry a `migration_step` field, so they were never part
of this narrower gate's population, and the failure is structurally
independent of this edit. This is pre-existing ambient drift from the
concurrently active tree (confirmed by the failing set differing between the
two runs), not caused by this Step.

**`dev/quality/error_code_default_suggestion_preimage.json` — NOT stale;
left untouched.** Its own docstring states the purpose plainly: "a fail-closed
HISTORICAL ledger for retired error-code default suggestions," pinned to a
fixed `SOURCE_COMMIT` and extracted via `git show` against that commit, never
against HEAD or the working tree. The row at line 602
(`RecoveryVerificationError`, `"aeat config recover"`) correctly preserves what
that field's source said at the pinned historical commit; editing it would
corrupt the audit trail it exists to hold, and its own gate
(`test_checked_in_ledger_matches_the_complete_immutable_error_code_preimage`)
runs green as-is, confirmed by an explicit pytest run
(`dev/tests/test_error_code_default_suggestion_preimage_ledger.py`, 4 passed).
The dispatcher's count of "fourteen entries" across "three development
ledgers" reconciles exactly: thirteen in the disposition ledger (now fixed)
plus this one preimage row equals fourteen; the preimage row and the
rehoming ledger's separate `historical_old_value_source` field are both
correctly-preserved history, not drift.

**Landing.** Both edits were captured by peer broad-sweep commits rather than
committed by this session: `error_code_default_recovery_rehoming.toml` in
`registry: continue authority-grade sweep (round 63)` (`715001d055`), and
`cli_action_census_dispositions.toml` in `registry: continue authority-grade
sweep (round 64)` (`7bcadaf18b`), consistent with this worktree's heavy
concurrent-commit cadence (HEAD advanced from round 59 to round 65 over the
course of this Step). Confirmed post-hoc against `git show` that each landed
diff is byte-identical to the intended edit, and that neither file shows
further modification in `git status`.

## Notes

`fixture_ownership.toml`'s stale entry remains open pending a quiet window;
the exact regeneration command and its guard are documented above so a later
agent does not need to re-derive them. This row's own condition — "once the
tree is quiet enough" — was tested empirically rather than assumed, and the
empirical answer was "not yet," repeatedly, across the whole span of this
Step's work.
