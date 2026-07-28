---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S175'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S175 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Validate every regenerated sequence against its directive and command contract and ## Scope

- `dev/docs/tests/test_sequence_contract.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
