---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:41a95bbc16b06e0234f55de216bd728a02d9271233566fa95f62397c19bffe53'
step_id: 'S03'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Add the adjudicated disposition model with stale-exclusion detection and symbol-scoped reasons

## Scope

- `dev/cli_action_census_dispositions.py`

## Description

- Add the versioned TOML disposition representation and closed role taxonomy.
- Convert each candidate identity directly from `CandidateRecord`, preserving all five census key fields without repeating discovery logic.
- Reconcile parsed dispositions against the pinned real census and reject missing, duplicate, stale, malformed, or unrecognized records with deterministically aggregated diagnostics.
- Require symbol, enclosing-function, and nonblank-reason grounding for exclusions; reject exclusion grounding on every other role.
- Add a checked-in-ledger validation entry point while leaving full ledger population to S04.
- Add real-census temporary-ledger tests, then incorporate independent review remediation for schema drift, all unknown-field scopes, diagnostic ordering, duplicate census input, exclusion misuse, and absent-ledger CLI failures.

## Outcome

The campaign now has an executable adjudication substrate. It distinguishes a syntactically valid partial ledger from complete current coverage, so the later ledger-population Step cannot silently inherit stale decisions or hide a newly observed action site. The module retains no census count baseline and does not classify the full candidate universe prematurely.

Modified files:

- `dev/cli_action_census_dispositions.py`
- `dev/tests/test_cli_action_census_dispositions.py`

## Verification

`uv run --no-sync pytest -n0 dev/tests/test_cli_action_census_dispositions.py -q`

`9 passed in 34.64s`

`uv run --no-sync ruff check dev/cli_action_census_dispositions.py dev/tests/test_cli_action_census_dispositions.py`

`All checks passed!`

`uv run --no-sync ruff format --check dev/cli_action_census_dispositions.py dev/tests/test_cli_action_census_dispositions.py`

`2 files already formatted`

`uv run --no-sync basedpyright dev/cli_action_census_dispositions.py dev/tests/test_cli_action_census_dispositions.py`

`0 errors, 0 warnings, 0 notes`

`git diff --check -- dev/cli_action_census_dispositions.py dev/tests/test_cli_action_census_dispositions.py`

Exited successfully with no whitespace errors.

## Notes

The initial six-test implementation passed before review. The final nine-test serial run is the accepted verification after the independent review remediation. No full disposition ledger was authored in this Step; that is intentionally deferred to S04.
