---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:59384a08714f0df146319fb24c902af91bf6a5325b1a46ce9284a1a9e69f7ad1'
step_id: 'S29'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Fail when an adjudicated exception-override producer lacks an exclusive migration Step

## Scope

- `dev/cli_action_census_dispositions.py`
- `dev/cli_action_census_dispositions.toml`
- `dev/tests/test_cli_action_census_dispositions.py`

## Description

Implement a current-tree ownership gate for retired exception action overrides. Preserve the S01 stable CandidateKey identity while attaching exact physical observation fingerprints, require a semantically admissible disposition and one open canonical-plan owner, and fail on any source, ledger, or plan-linkage drift.

## Outcome

- Calibrated VaultSpec RAG covered exception override ownership and S29 migration evidence. Exact discovery used `fd`, `rg` for `suggestion=` and `.suggestion =`, and the live AST extractor.
- The live scan found 46 physical observations joining to 43 stable CandidateKeys. The repeated-observation groups are censo parser x2 and modelo profile-create x3.
- The workflow producer is historical-only because the current worktree no longer carries that override. S97 remains its plan proof Step and is not a live owner.
- TOML schema v2 stores `migration_step` and complete physical observation fingerprints on existing CandidateDisposition rows; no second authority ledger was introduced.
- The extractor covers registered error constructors, error-class `super().__init__` forwarding, `cast(CadrumoError, super())` cooperative MRO with structural proof, and except-bound `.suggestion` mutation.
- Open scoped owners include S67, S76, S40, S96, S78, S79, S98, S82, S37, S65, S84, S85, S99, and S87. S96 owns the modelo forwarding bridge, S98 registry forwarding, and S99 justificante cooperative-MRO forwarding.
- The gate reads Steps only through `vaultspec-core vault plan query --json`; it rejects missing, stale, duplicate, excluded, unknown, closed, and out-of-scope owners and missing, extra, or duplicated fingerprints.
- Independent review initially raised two HIGH findings: source read/decode/parse failures were silently skipped, and an active override could be labelled EXCLUDED. The gate now fails closed with deterministic source-path diagnostics and accepts only producer or transformer dispositions. Real-filesystem regressions cover directory read failure, invalid UTF-8, and invalid Python; real current-source/current-plan regressions cover excluded ownership and missing, extra, and duplicate fingerprints.
- `uv run --no-sync pytest -n 0 dev/tests/test_cli_action_census_dispositions.py -q` -> 21 passed in 128.64s. The direct owner gate reports 46 physical observations / 43 stable keys. Targeted Ruff, formatting, basedpyright, and `git diff --check` pass.

## Notes

The broad legacy general action-disposition ledger is a separately scoped revision-pinned S01 concern. S29 validates only live exception-override shapes against the current filesystem and canonical plan projection; unrelated ledger staleness remains visible and was not reclassified.
