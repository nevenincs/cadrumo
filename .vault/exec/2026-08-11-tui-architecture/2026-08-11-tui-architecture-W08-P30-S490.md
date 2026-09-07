---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f5de2bff287dfe2b04f1bc303c1375c26669a4f9ac78af09187ceb614e9925f9'
step_id: 'S490'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Establish that the modelo 390 2022 export tree is blocked on a reviewed bootstrap target row rather than on the check mode pin that earlier firings named, since the generated export bootstrap authority carries only two reviewed modelo 200 rows and each attests a reviewed official source by hash, and correct the reading that the pipeline module run as a script passes when it has no main guard and exits zero without running TUIMODELO_SCOPE: RETAINED_BY_SOURCE_OWNER; modelo-subject and UNCOVERED: searched the tuimodelo plan for the modelo 390 export-tree subject and found no step, so it is retained rather than assumed absorbed.

## Scope

- `dev/registry`

## Changes

M dev/registry/pipeline/generated_export_bootstrap_targets.toml

    the derived modelo 390 2022 bootstrap row (committed by another writer in 87354e0b0a)

The step's establishment holds and was then acted on. Two further claims this
record must carry, because BOTH WERE MINE AND BOTH WERE WRONG:

RETRACTED - "blocked on a reviewed EEDD registration". Twenty-eight export trees
are published (151, 184, 185, 200, 202, 210, 222 and others) and this product has
never been a registered entidad desarrolladora. `AeatProductSoftwareIdentity`
gates EMITTING a filing, not publishing a tree. One directory listing disproved a
claim repeated across many iterations.

RETRACTED - "only 2022 fails" as a fact about 2022. Five modelo 390 revisions
exist (2021-2025), NONE has a published export tree, and only 2022 appears in the
enrolled tree list, so exactly one row can red. The singularity came from the
enrolment list, not from the data.

THE REAL REMAINING BLOCKER, found by adding the row and re-running the check: the
adjudication for a genuine typo in the official AEAT file lives where the
publication CLI cannot read it.

    MECHANISM  dev/registry/pipeline/_source_defects.py            pipeline-owned
    RENDERER   render_complete_export_tree(..., source_defects=()) accepts them
    CLI        _render_candidate() passes NONE
    DATA       _SOURCE_DEFECTS is declared ONLY in dev/registry/tests/test_generated_export_trees.py

The test harness therefore renders this tree and the publication CLI cannot, for
the same tree and the same design. The typo is real and already adjudicated: pages
1-6 and 8 print `</T3900N000>` at twelve characters, page 7 alone prints
`</T3900700>` at eleven while its own length column says twelve.

## Notes

THE ROW LANDED WITHOUT REVIEW. Another writer committed it inside
`87354e0b0a refactor(dev): follow the narrowing delegators screen with its gate`.
A bootstrap row authorises a FIRST PUBLICATION of a filing-grade export tree; it
should not enter under an unrelated message. Fifth time this session in-flight
work of mine was swept into another commit, which is why "uncommitted, awaiting
review" is not a safe way to hold a proposal on this worktree.

FOLLOW-ON, grounded separately: the enrolment list that produced the misleading
singularity is itself the subject of
`2026-09-07-registry-temporal-coverage-enrolment-versus-declared-projection-research`.
Twenty-nine of one hundred and twenty-eight declared revisions are enrolled, and
forty-four of fifty-eight modelos have none.
