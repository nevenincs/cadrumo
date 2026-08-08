---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:18b854d5cc081c7d29c8e74f770c1e5bcefba801662dbd79bcf2aaf78875f141'
step_id: 'S283'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Repair the incomplete relocation that deleted dev/packaging/evidence_release.py in commit 4841bc6bd3 while three modules still import from it - release_candidate.py line 44, seal_candidate.py line 31 and soak_promoter.py line 36 - and the symbols download_release_assets, list_releases, resolve_gh, run_gh_with_retry, EvidenceLane and evidence_tag exist nowhere else in the tree, so dev/release fails to collect at HEAD and the whole release lane is blocked - decide whether the module returns or the symbols land in a named new home and sweep every consumer in ONE commit

## Scope

- `dev/release`

## Description

- Read the deleting commit before choosing a repair, to establish whether the deletion was deliberate with a planned destination or collateral.
- Confirm no destination exists: search the decision corpus and the tree for the deleted symbols and for any planned new home.
- Restore both deleted files byte-exact from the deleting commit's parent, capturing raw bytes rather than decoded text.
- Verify every symbol the three importers name resolves from the restored module.
- Prove clean collection across the developer tree, immediately after the restore.
- Land the repair as one commit over exactly the restored paths.

## Outcome

The deletion was collateral, and the evidence is in the commit itself. Its subject and body describe the ingestion human-review gate in detail and never mention release evidence; its stated pathspec names twenty-five source and generated-reference files, none of which appear in the commit; and the commit contains exactly two files, both deletions, totalling 1387 lines. The pathspec text survives inside the commit MESSAGE rather than acting as a pathspec, which is the signature of a message quote left unclosed before the separator. The command therefore ran as a bare commit and took the whole index, and what the index happened to hold was a staged deletion belonging to someone else.

No relocation destination was ever planned. None of the seven symbols the three importers name is defined anywhere else in the tree, no plan row asks for the module to move, and the only decision-corpus mention of it is an audit finding recommending that six fragmented evidence modules eventually be CONSOLIDATED, which is a different act with a different destination and was never carried out. So the repair is restoration rather than a new home.

The three importers needed no change at all, which is worth stating because the row anticipated sweeping them. They were never wrong: their import paths are correct and were correct throughout. Nothing had moved, so nothing needed repointing; a file had simply been lost. The atomic change is therefore exactly the two restored files, and a consumer sweep would have been a change with no defect behind it.

Restoring un-masked a second, larger regression that had been invisible. Collection aborted the entire developer-tree run, so no test in the release directory had been executing at all; with collection clean, seven failures surface in the publish-workflow gate. Those are recorded in the notes and are not this row's to fix: they belong to the workflow the release lane owns, they include drift unrelated to evidence release, and one of them is security-relevant enough to deserve its own owner rather than a repair folded into this one.

## Verification

    uv run --no-sync pytest dev/ --collect-only -q -p no:cacheprovider
    2018/2734 tests collected (716 deselected) in 13.16s

Exit status zero and no collection errors. The reading immediately before the restore, at the same scope, was `943/956 tests collected (13 deselected), 2 errors in 1.50s` with the run interrupted, so the comparison is a collected count against a collected count rather than a pass claim against a failure claim.

    uv run --no-sync pytest dev/packaging/tests/test_evidence_release.py dev/packaging/tests/test_preflight_recipe_selection.py -n0 -p no:cacheprovider -q
    68 passed in 101.84s (0:01:41)

The restored test module passes in full, and both previously-failing checks in the recipe-selection gate are green. Those two had been failing on a subprocess return status of two, which is the collection abort rather than a selection defect, so they were reporting the broken tree correctly.

Every symbol the three importers name was resolved from the restored module in one import before any suite was run, so the fix was confirmed at the seam the break was reported at rather than only in aggregate.

    git show 19b19cec9c --numstat
    711 0 dev/packaging/evidence_release.py
    676 0 dev/packaging/tests/test_evidence_release.py

## Notes

Seven failures in the publish-workflow gate are live, pre-existing, and were masked by the collection abort. They are not regressions from this repair; they became visible because of it, and they mean the release path is still blocked after this row closes.

The same pattern that deleted this module also stripped the workflow steps that CALL it, across two further blanket commits whose messages likewise say nothing about release evidence. The publish workflow carried five references to the module and now carries three: the two surviving are input plumbing that passes a value through, and the two removed were the steps that actually ran the leak sweep over release evidence before it is attached to a public release. A third invocation, the evidence verification step, was removed separately by another such commit. So the input is still collected and threaded through a path that no longer sweeps or verifies anything with it, which is worse than the input being absent, because the workflow reads as though the control is present.

That surface was deliberately not repaired here. The gate also fails on job-permission drift unrelated to evidence release, restoring steps into a workflow that has been restructured since needs the lane that owns it, and a security control re-landed piecemeal by a lane that does not own the path is how a control comes back in name only.

The recurring mechanism behind all of this is worth naming once: a bare commit takes the entire index, so it takes whatever any other agent has staged. Three separate strips of one subsystem were carried by commits whose messages describe unrelated work. The deletions are individually invisible in review, because each commit's message and its actual contents are about different things.
