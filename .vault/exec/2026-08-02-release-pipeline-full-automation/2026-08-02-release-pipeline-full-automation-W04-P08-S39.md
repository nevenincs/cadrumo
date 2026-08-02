---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:50e97e3281dc75e16ca45215c57d40d2dbd1bdaf325c0723f60c3d93d8aec107'
step_id: 'S39'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
  - "[[2026-08-02-release-pipeline-full-automation-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S39 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Run the fresh-context honesty review against the campaign closure summary before the campaign is declared structurally complete, dispatching an independent reviewer with the ADR, this plan, and the commit range as context, and track every surfaced item as a new Step with a verification gate or formally defer it with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record and ## Scope

- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the fresh-context honesty review against the campaign closure summary before the campaign is declared structurally complete, dispatching an independent reviewer with the ADR, this plan, and the commit range as context, and track every surfaced item as a new Step with a verification gate or formally defer it with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record

## Scope

- `.vault/audit/`

## Description

- Read the accepted decision record, the L3 plan in full including its Verification section, all thirty-nine execution records, and the landed tree across the campaign commit range, with no prior exposure to the implementation work.
- Re-ran every gate command named by the Steps rather than trusting the records that claimed them, and read the three mechanisms the decision record names as most likely to be implemented subtly wrong.
- Parsed the orchestrator and promoter job graphs from the landed workflow documents rather than from their prose, and probed the live forge read-only for environment, protection-rule, label, and tracking-issue state.
- Proved the critical defect by executing the shipped promoter functions over a two-candidate set rather than by reasoning about the code.
- Persisted the findings as a vault audit document and tracked every one as a new Step carrying its own verification gate.
- Ran two further confirmation passes as remediation landed, replaying each original reproduction against the committed tree.
- Rejected a stale close request measured against an unchanged HEAD, and declined to infer authorisation to defer the one finding still open at that point.

## Outcome

Twelve findings: one critical, four high, four medium, three low. All twelve are
closed with verification. None was deferred.

The critical finding was that a rehearsal dispatch permanently deadlocked the
soak promoter, so no release would ever publish again after the first rehearsal.
It was reachable by the default value of the first input an operator supplies,
and the promoter's own test could not observe it because its fixture held a
single candidate. The high findings were an alerting default path that could not
deliver on the live forge because the label it names does not exist, a candidate
invalidated during its soak reporting to nobody, acquisition run ids dropped at a
job boundary, and, surfaced during the confirmation pass, a remediation that
corrected that drop by feeding an acquisition lane run id into the input the
publication authority consumes as an operator-minted release tag.

Each fix was confirmed by replaying the reproduction that found the defect, not
by reading the diff. The final correction was additionally proved
mutation-sensitive: planting the old wiring back reds the new assertions, and the
workflow was restored byte-identically afterwards. The four previously-closed
findings whose modules later corrections touched again were replayed and hold.
The full gate set is 433 green.

The campaign is structurally complete on the merits of this review.

## Notes

Two non-blocking observations are recorded in the audit for whoever maintains
this next: the acquisition stage still publishes a claude lane run id no
downstream consumer reads, which is unused rather than lost but reads like a
second dropped id; and the alerting guard detectors match by containment, so they
cannot distinguish a status function from its negation, a shape that predates
this campaign and that no shipped guard exercises.

Two process observations worth carrying. A green suite was never sufficient
evidence here: the acquisition-run-id defect and its remediation regression both
shipped with passing tests, the second because a new test asserted the defective
mapping as correct while reasoning only about ids not being dropped. A gate that
asserts a value arrives cannot answer what that value semantically is, and the
correction needed a negative assertion to ask the question the positive one could
not. Separately, one close request arrived against a tree that had not changed
since the previous report; re-measuring HEAD and the working tree before acting
is what caught it, and the review declined both to close on the stale premise and
to read a close instruction as authorisation to defer an open finding.
