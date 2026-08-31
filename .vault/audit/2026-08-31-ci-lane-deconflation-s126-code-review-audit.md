---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:58224b2a671ab446ccb300fdd306b85e06c279538e904634613a105d2e5f3c9d'
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

# `ci-lane-deconflation` audit: `P05 S126 code review`

## Scope

Independent review of source/plan/execution commit `3835fa11c87d8bda7c94a69cfadf1960685ec95f` and pure feature-index companion `41feb5eac51ae3d8ecb6ed04382166b13a25ccb4`. Reviewed the approved CI-lane and execution-evidence ADRs, exact source diff, all resolver-map branches, custody-port call sites and public exports, the referenced real-adapter test sources, the size baseline diff, and the companion index diff. Current `HEAD` was the feature-index companion; shared-worktree residue was not read as part of the review.

## Findings

### P05 S126 code review | high | execution record does not quote any real result

`.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S126.md` records the full ruff and two-test commands but gives each only `-> pass`. This conflicts with the accepted CI-lane execution-evidence ADR: records must quote the runner's verbatim summary line so test count, deselection state, duration, and exit result are inspectable. The record also omits a formatter gate and the exact size-budget measurement required to establish this P05 refactor's line compliance. Replace the three bare claims with complete invocations and their actual result lines: ruff check, ruff format check, and the targeted real-adapter pytest invocation; add a complete measurement command and its observed count under the 1,250 ceiling. No placeholders are present, but a bare `pass` is not reproducible evidence.

## Recommendations

- Amend the S126 execution record with complete commands and verbatim output summaries, including a formatter result and the measured line count, then re-review the record-only repair.

The source extraction is otherwise sound: all 38 resolver namespace keys remain present, `_natural_key_resolvers` retains its private aggregation role, the four split helpers are private implementation details rather than a new facade, and the public custody port continues to call only `collect_profile_custody_carry` and `restore_profile_custody_carry`. The referenced tests use real encrypted SQLite adapters and cover bound-resolver/rekey behaviour. The target is 431 lines, below the 1,250 ceiling; neither source commit changes `dev/audit/size_budget_baseline.json`. The companion changes only the generated CI-lane feature index, adding current S120 through S126 records and their audits.

