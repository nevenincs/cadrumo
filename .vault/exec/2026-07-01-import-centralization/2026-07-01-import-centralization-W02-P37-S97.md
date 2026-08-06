---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:57bb342b4c83958cade04196955cfea2fe5d72d43fa82425e353fde8d22f59f9'
step_id: 'S97'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.fincas`

## Scope

- `src/aeat/adapters/persistence/profile/fincas.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.adapters.persistence`, `aeat.adapters.outbound`, and `aeat.adapters.inbound` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P37` (persistence), `W02.P39` (outbound), and `W02.P42` (inbound) in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 50 adapters files as one atomic explicit-pathspec commit.

## Outcome

50 files rewritten and committed (commit `85c3b2ad6`, `refactor(adapters): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P37`, `W02.P39`, and `W02.P42` are covered by this one record and this one commit, batched per the Wave dispatch brief. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
