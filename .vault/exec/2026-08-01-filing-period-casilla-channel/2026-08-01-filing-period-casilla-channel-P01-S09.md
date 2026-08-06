---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:1c487bcb0a587d92eb566e6d555890b39b1fe7d21abfbedde198e8f34eb3b664'
step_id: 'S09'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Observe clean collect-only and land the whole set as one explicit-pathspec commit

## Scope

- `src/cadrumo`

## Description

- Run the two owning package suites and record the real counts against the pre-fix baseline.
- Run the full-tree collection gate, which is what catches the unimportable-HEAD hazard the partial-commit risk created.
- Lint every file entering the commit.
- Verify the staged set carries no peer work, then land the whole set as one explicit-pathspec commit.

## Outcome

The two package suites went from twenty-two failed and 1485 passed, in 219.94 seconds, to 1510 passed in 258.14 seconds. Zero failure lines in the post-fix log. Both runs retained tracebacks; the passing run has none to retain.

BASELINE CORRECTION. The dispatch brief stated two tests were failing. The real figure was twenty-two. The correction is attributable to the briefing rather than to the plan, which never claimed a count. The other twenty were the same defect surfacing one layer further out: the Modelo 303 and 369 end-to-end, refund-election, wallet-filing, deductible-evidence and export-output-path tests all reach the draft builder through a persisted revision replay, so the ordinal reached the typed text channel there too. All twenty-two pass now, and none was altered to make it pass - nineteen of them were never opened.

The collection gate collected 15247 of 18652 tests, 3405 deselected, in 43.19 seconds, with zero collection errors. The lint gate passed across all thirty committed files.

The index was confirmed empty before staging and the staged set was read back as exactly the thirty intended files before committing. The commit landed as thirty files, 582 insertions and 154 deletions, with an explicit pathspec. Peer working-tree changes across roughly fifteen other modules in the same packages were left untouched and uncommitted.

HEAD integrity was checked directly rather than inferred from the working tree: every symbol the commit imports across the package boundary was confirmed present in the committed blobs, including the two registry helpers absent at the previous HEAD and the atomic write helper the export module now calls.

## Notes

THREE BEHAVIOUR CHANGES BEYOND THE TYPED DISPATCH RODE IN ON THIS COMMIT. They were unratified when the commit landed and were flagged as such; the amending ruling has since examined and ratified all three individually. They are settled, and the ruling rather than this record is where each rationale lives.

A new one-based export offset alias tightens the export field offset constraint from non-negative to strictly positive. This is the one worth a later reader's attention: it is a validation tightening with registry-wide reach, and the ruling found it correct on the ground that both consumers already treat the offset as one-based, so the old lower bound admitted a value that read the wrong bytes silently on the deserialise path. A constraints consolidation replaces the two-field bounds re-projection on the schema protocol with the complete registry-owned constraints object. The export module switches its file write to the atomic write helper, and a typed decimal serialisation helper joins the oracle replay boundary.

All three were landed rather than split because each is import-coupled to the ratified change through the registry public facade, so separating them would have left HEAD unimportable - the precise hazard this Step exists to prevent. Splitting was considered and rejected on that ground, not overlooked.

The commit message describes the filing-period fix and does not mention these riders. That gap is deliberate on the ruling's part and is closed by the amendment, not by the commit message.

One inheritance for later phases: the period ordinal projection now has zero production consumers in the committed tree, so its retirement needs no consumer sweep.
