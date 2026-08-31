---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2f4ab90f35807ae2d686b36636530411a3eaf8ff9310135b56a49e8950a31640'
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

# `ci-lane-deconflation` audit: `P05 S133 independent code review`

## Scope

Independent review of P05.S133 at `09b3eb5d1f` and current `09b3eb5d1f`. Reviewed the approved CI-lane plan and ADRs, the S133 execution record, and all four committed paths. Checked the candidate-validation and Modelo binding contracts, loss and duplicate test inventory, direct test imports, line-budget/baseline scope, and claimed sequential and parallel test evidence.

## Findings

### s133-exec-evidence-placeholders | high | The execution record does not provide literal reproducible validation evidence

`2026-08-05-ci-lane-deconflation-P05-S133.md` lines 23-26 record each verification only as `pass`; they omit the test collection command/result, raw collection and deselection accounting, the claimed 42 sequential tests and exit status, and the transient parallel import failure and its retry/disposition. The size command at line 26 is not executable as written because its tuple uses doubled opening and closing quotes around both paths. Consequently none of the claimed ruff, format, test, or size outcomes can be independently reconciled.

## Recommendations

- Replace the four placeholder outcomes with exact executable commands, verbatim result summaries, and exit statuses. Include marker-free collection with raw `42` and deselected `0`; the explicit sequential run with `42 passed` and exit `0`; the exact parallel invocation, transient import failure, clean retry, and why the transient error is not a S133 failure; and a valid size command reporting both measurements, their thresholds, and baseline state.

The source disposition is approved pending evidence repair. The six candidate contract tests and their support builders move intact to `test_iva_ledger_candidates.py`; the original retains all 36 transaction-projection and Modelo 303 binding tests. The final inventory is 42 tests with 42 unique names, so no test was lost or duplicated. The new test module calls the established aggregation surface directly rather than adding a test facade. The original is 1,156 physical lines and the candidate sibling 313, both below the unchanged default 1,250-line ceiling; the S133 commit does not alter the size policy or baseline. A focused current-worktree run was attempted, but all 42 tests error during repository setup because shared WIP is missing `cadrumo.core.iva_category_resolution`; that external import failure is not attributable to S133.

