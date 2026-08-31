---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:182800ca02b813919ba04415ae8641036d37661f9e76462af610fc7b1bf04c7c'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `Review P05 S148 recovery chain`

## Scope

Independent review of P05.S148's original commit `4b3d118585`, intervening peer documentation `bf3aa52c`, record correction `9b8548259a`, source restoration `c3a5711d04`, and newline cleanup `54fe92be21`. Reviewed the plan mapping, execution record, immutable aggregate source diff, current worktree-only peer hunk, behavior, size evidence, and current HEAD. This review made no source, plan, execution-record, or shared-index change.

## Findings

No HIGH or CRITICAL findings. The immutable aggregate diff from the original parent through `54fe92be21` contains only `_ingest_evidence_attachment` and its direct replacement of the duplicated attachment-store/add call; it contains no clock-import transition. In contrast, the diff from `54fe92be21` to the current worktree contains solely the peer `core.time` to `core.time._clock` import change. The extracted helper remains private and local, retains the exact secure attachment authority, request fields, content digest result, and lifecycle ordering, and introduces no facade. The record corrects its initial overstatement rather than hiding it, preserves literal ruff and formatter outcomes, documents the historical collection exit 4 as an unrelated `bienes_inversion` import failure, and records the 179-of-180 callable result, 20 unrelated global callable offenders, and unchanged baseline. In the currently advanced peer worktree, the focused evidence lane now collects and passes 7 tests; that later external state does not invalidate the recorded historical attribution.

## Recommendations

Approve P05.S148. Keep the immutable aggregate-diff and current-worktree diff distinction for any future recovery that must separate a scoped change from concurrent peer work.
