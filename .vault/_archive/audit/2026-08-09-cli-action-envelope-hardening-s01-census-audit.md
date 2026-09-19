---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:7cdfd2e49f1c15598400c340dd3ec01baa814aa44299cb5f72c8695c4438f5d5'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S01 AST candidate census review`

## Scope

Reviewed `dev/cli_action_census.py` and `dev/tests/test_cli_action_census.py` against the accepted action-envelope ADR, its research and fixed-point reference, and plan Step `W01.P01.S01`. The review included calibrated semantic RAG searches for the canonical census and decision records, exact source confirmation, the targeted test command with xdist disabled, Ruff, and a bounded direct CLI census invocation. The campaign ADR, plan, reference, and research records were read from their working-tree copies only because their staged-deletion state belongs to another actor.

## Findings

### workflow-detail-map-omission | high | Known `next_action` producers are absent from the candidate ledger

`_CandidateVisitor` recognises aliases only as annotations, assignment targets, call keywords, and attribute reads. It does not recognise an action alias used as a string key in an `ast.Dict`. The campaign research names workflow detail maps as one of the fragmented producer shapes, and `src/cadrumo/application/workflow/_engine.py:902`, `:949`, and `:1034` each publish `"next_action"` with a recovery action in a `details` dictionary. A direct one-module visitor invocation emitted no `next_action` record, while exact source search confirmed all three rows. Those action outcomes will therefore receive neither a candidate identity nor a later disposition, defeating the fixed-point census before its first pass.

### missing-execution-marker | high | The new census tests cannot enter any project test lane

`uv run --no-sync pytest -n 0 dev/tests/test_cli_action_census.py -q` exited 4 before executing a test. The collection gate reported that both tests must carry exactly one of `unit`, `integration`, or `aeat_live`; neither module nor tests declare one. Project configuration selects `unit` by default and enforces marker integrity, so the asserted stable records are not a runnable proof in the normal quality lane.

### per-module-git-process-timeout | medium | A normal direct census did not complete within the bounded operational check

Ruff completed, but `uv run --no-sync python -m dev.cli_action_census HEAD --json` was stopped by its explicit 120-second command bound after 124.043 seconds without producing the JSON ledger. The implementation first lists every production module and then invokes a separate `git show` subprocess for each module. This is not proof that it cannot eventually finish, but it is an unverified operational boundary for the campaign's repeatable census and needs a bounded completion check after reducing the per-file Git process cost.

### locator-assertion-churn | medium | The test contradicts the location-independent candidate identity contract

`CandidateRecord.key` deliberately omits line and column so formatting moves do not create stale candidates. However, `test_census_observes_real_definition_producer_and_command_literal_sites` asserts full `CandidateRecord` equality including `line=138`. An unrelated line insertion in `src/cadrumo/core/json_contract.py` will fail the test despite preserving the candidate's stable key and action identity. The proof should assert the identity key and keep locations only as diagnostic locators.

### workflow-detail-map-omission-remediation | low | Resolved by dictionary producer extraction

The visitor now handles `ast.Dict` string keys in the initial alias vocabulary and emits the value as the producer action identity. The real-source test proves all three `src/cadrumo/application/workflow/_engine.py` workflow detail producers are present by stable key. Targeted pytest passed three tests with xdist disabled.

### missing-execution-marker-remediation | low | Resolved by a unit execution marker

The test module now declares one `unit` execution marker with its architectural marker. `uv run --no-sync pytest -n 0 dev/tests/test_cli_action_census.py -q` collected and passed all three tests in 23.07 seconds.

### per-module-git-process-timeout-remediation | low | Resolved by a single revision archive read

The census reads all production files from one pinned `git archive` stream instead of launching one `git show` process per module. A direct JSON CLI check parsed successfully with 1,265 candidates and 1,265 unique keys in 11.450 seconds, within its 60-second bound.

### locator-assertion-churn-remediation | low | Resolved by key-based source assertions

The source-anchor test now asserts `CandidateRecord.key` values, including the `Notice.suggestion` definition, rather than full records with a source line. Path, enclosing symbol, role, alias, and action identity remain asserted while locators stay diagnostic only.

## Recommendations

- For `workflow-detail-map-omission`, add dictionary-key producer extraction for the initial alias vocabulary, asserting the three existing workflow rows are emitted with their enclosing symbols and action identities before completing S01.
- For `missing-execution-marker`, mark the new module with the one appropriate project execution marker, then rerun the exact targeted command with `-n 0` and confirm collection plus both tests pass.
- For `per-module-git-process-timeout`, read the pinned revision through a bounded bulk Git mechanism rather than one `git show` process per source module, then preserve the revision-consistency property and rerun the direct JSON command within an agreed command ceiling.
- For `locator-assertion-churn`, rewrite the source-anchor assertion to compare `CandidateRecord.key`; retain path/symbol/action assertions without using a line number as acceptance identity.
