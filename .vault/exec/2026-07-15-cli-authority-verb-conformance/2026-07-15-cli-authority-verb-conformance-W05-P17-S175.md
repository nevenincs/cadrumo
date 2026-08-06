---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:8fe93f4e196377fb32abf054f794e00368a85f43fcad664d99533cd1dd02c82c'
step_id: 'S175'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Validate every regenerated sequence against its directive and command contract

## Scope

- `dev/docs/tests/test_sequence_contract.py`

## Description

- Validate every enrolled `cli-sequence` against its directive and command contract.
- Confirm each `@result` frame asserts the result payload, not merely exit code or status.

## Outcome

The sequence-contract gate is a ratcheting per-page structural check over the
enrolled sequence corpus: a `@result` frame must assert the result payload
(at least one `@expect` on a `result.<path>` json-path), not only `exit_code` or
the `status` spine field, so a sequence verifies the meaning of its final output
rather than only that the process ran. Every enrolled sequence validates against
its directive; the gate is green.

The run covers the current sequence corpus at HEAD, which is a descendant of the
four coordinator-authored how-to page commits (protect-data-access, index,
ledger-evidence, profile-setup), so the validation reflects the current authored
surface rather than a pre-edit one.

Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m integration -o
addopts="" dev/docs/tests/test_sequence_contract.py`. Collected 8, `8 passed in
1.48s`, exit code 0, at HEAD `b3fc6d22fb4b3567d01b97a05e97dfc147234303`.

## Notes

Two items the coordinator flagged as already settled were confirmed not to recur:
the modelo-390 records-audit sequence no longer names the retired replay verb, and
the blocked-row marker parser gap is closed. Same peer core-import block delayed
the start; not touched, cleared on the peer's landing.
