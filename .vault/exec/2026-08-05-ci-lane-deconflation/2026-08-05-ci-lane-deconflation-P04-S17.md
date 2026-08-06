---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:606954fb76b0e95f105dc0fe7760f4e637a66ee5f152b6d0323f57d3e70add74'
step_id: 'S17'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Record a finding about the 204 semantic-dedup exec records rather than remediating them, all 204 carry empty Description Outcome and Notes and were bulk-scaffolded in one commit so 0 resolve to an implementing commit, and unchecking would assert work the tree shows was done and ## Scope

- `.vault/exec/2026-06-13-semantic-dedup-epic` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record a finding about the 204 semantic-dedup exec records rather than remediating them, all 204 carry empty Description Outcome and Notes and were bulk-scaffolded in one commit so 0 resolve to an implementing commit, and unchecking would assert work the tree shows was done

## Scope

- `.vault/exec/2026-06-13-semantic-dedup-epic`

## Description

- Measure what the 204 records actually contain before choosing a remedy.
- Attempt commit reconstruction by all three available instruments.
- Record the finding rather than remediate, once both branches of the row's remedy proved wrong.

## Outcome

**Split, as the row requires: 0 filled from commits, 0 unchecked, 204 recorded as
unreconstructable.** No close calls — the failure is uniform and structural rather than
case-by-case.

The finding is persisted as `2026-08-06-semantic-dedup-epic-exec-record-provenance-audit`, in
the owning feature rather than this one, because it is a finding about that campaign's record.

**"Empty Outcome" understates what was found.** All 204 carry an empty `## Description`, an
empty `## Outcome` and an empty `## Notes`. The only populated sections are the heading and the
Scope, both machine-filled by `vault add exec` from the Step row. They are scaffolds containing
nothing a human supplied.

**The date split is the empty split, exactly:**

    2026-06-13     8 records,   0 empty
    2026-06-14    23 records,   0 empty
    2026-07-04     4 records,   0 empty
    2026-08-02   204 records, 204 empty

All 204 were created in one commit, `253aeab859` at 09:21:51. That correlation is a
bulk-scaffold signature and nothing else produces it.

## Verification

Three instruments attempted, all three failing for reasons that are properties of the records:

    date-constrained    the date is the SCAFFOLD date, so it returns that day's unrelated
                        commits - it "resolved" 579fe525de, a CLI operator-contracts commit,
                        as the implementer of a Google-credential dedup step
    path-based          ambiguous: 114 of 204 match multiple same-day commits, and the scope
                        paths have been touched by later campaigns
    symbol-based        unavailable: zero of the 204 carry a backticked identifier anywhere,
                        because their bodies are empty

Counter-evidence against unchecking, spot-checked at HEAD:
`entrypoints/cli/_config/_google_credential_source_payloads.py` carries canonical-validation
code and `adapters/outbound/storage/_factory.py` carries the whitespace normalisation its step
describes. The work appears to have landed.

## Notes

**Both branches of the row's remedy are wrong here, and the row was reworded to say so rather
than closing as though 204 records had been handled.**

Filling is unreachable: 0 of 204 resolve to a commit, and filling from a step's own description
restates intent rather than recording outcome. **Unchecking is worse than it looks** — it would
assert the work was not done, which the tree contradicts, replacing an unevidenced record with
a confidently false one at scale in a plan this campaign does not own. An empty Outcome is
visibly incomplete; a wrongly-unchecked step is not.

So the honest position is the one neither branch expresses: **completion is unevidenced, not
disproven.** The evidence of the work is in the tree; what is missing is per-step provenance,
and recording that gap precisely is more honest than either alternative.

**The date-resolution failure is worth carrying past this row.** Constraining to the record's
own date was wrong *by construction*, because the constraint was the scaffold date rather than
the work date — and it produced a plausible, populated, wrong answer that no guard on the
output would catch. It was noticed only because the sample named a commit recognisable as
today's.

That is the second commit-resolution heuristic to fail this way in one session, after
`git log --grep` matching a peer's message body. **Both return confident wrong answers rather
than empty ones, and both were caught by recognising the answer rather than by checking it** —
which means neither has a guard, and the only defence is resolving by content that could not
belong to another commit.
