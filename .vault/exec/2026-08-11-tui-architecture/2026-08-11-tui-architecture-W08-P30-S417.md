---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:204607ef47ff2d38e134c728463599aae81f98c9bba54d733c9218d37c53aa23'
step_id: 'S417'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Report a read, genuinely empty local filing catalogue as ABSENT rather than never observed. INDEPENDENT REVIEW, REPRODUCED 2026-09-04: _overview_row marks the local side PRESENT only when the filing count is truthy and otherwise leaves it NOT_OBSERVED with no observation time, so a proven zero and an unread source become one value in the row an operator reads. AeatSyncSourceState.ABSENT exists for exactly this and is never used. The same projection already contradicts itself -- its own source observation for that read says available with item_count 0. Second instance in the same function: EVIDENCE_COMPARISON declares local.filings as its source but is excluded from the observed-local condition, so it reports NOT_OBSERVED even with filings present. This is the collapse no-silent-under-declaration forbids, inside a published projection.

## Scope

- `src/cadrumo/application/aeat_sync/workspace_reader.py`

## Changes

- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `A` `src/cadrumo/application/aeat_sync/tests/test_workspace_reader.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aeat_sync` -> `pass`

## Notes

The cause sat one layer below where it was reported. ABSENT was not merely unused: the
projector's own `_require` demanded a non-zero item count from any confident row state, so
an observed-empty catalogue could not be expressed as ABSENT at all and the only
representable answer was NOT_OBSERVED. The reader was obeying a contract that made the
honest answer illegal.

A row asserting ABSENCE now needs only an observable source; the non-zero requirement
stays for rows asserting something positive. The reader then spends all three local
answers, and EVIDENCE_COMPARISON joins the locally-read set alongside census and filed
declarations.

Teeth proven by restoring the previous behaviour: four of the six new tests fail, including
the one asserting the three answers are distinct from each other within one projection and
the one asserting the projection no longer contradicts its own source observation.
