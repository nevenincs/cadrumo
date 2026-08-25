---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cefb0c3ee88219797794c0c7b786d6f4c848288de6d4dd083c35b531722c4d5e'
step_id: 'S49'
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
     The S49 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Flip continue-on-error off the per-push integration conformance step after the action-envelope campaign is audited complete and the unchanged authoritative four-module recipe is green. Closure evidence: the historical 2026-08-13 baseline was 6 failures among 48 then-collected tests, current suite evolution legitimately collects 46, all 46 pass, and the workflow remains pinned to the exact recipe with eight workers. The denominator is an observation, not a permanent release condition and ## Scope

- `.github/workflows/ci.yml and dev/ci/tests/test_ci_workflow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Flip continue-on-error off the per-push integration conformance step after the action-envelope campaign is audited complete and the unchanged authoritative four-module recipe is green. Closure evidence: the historical 2026-08-13 baseline was 6 failures among 48 then-collected tests, current suite evolution legitimately collects 46, all 46 pass, and the workflow remains pinned to the exact recipe with eight workers. The denominator is an observation, not a permanent release condition

## Scope

- `.github/workflows/ci.yml and dev/ci/tests/test_ci_workflow.py`

## Description

- Removed the four dead runnable-command citations from retained profile payload
  schema docstrings without registering retired verbs or weakening the live-tree
  conformance scanner.
- Re-ran the unchanged four-module per-push integration recipe and established a
  current green baseline of 46 collected tests. The historical 48 was an
  observation of the older suite, not a durable denominator.
- Removed `continue-on-error: true` from the named per-push integration
  conformance step while preserving its exact eight-worker recipe delegation.
- Added workflow conformance coverage requiring the named step to remain
  blocking.

## Outcome

The per-push integration conformance step now fails the workflow when its
authoritative recipe fails. The action-envelope prerequisite is closed and the
current recipe is green at 46 of 46.

## Notes

- Historical baseline: 6 failures among 48 tests on 2026-08-13.
- Current verification: `just test-per-push-integration-gates` passed 46 tests;
  the two focused workflow-conformance assertions passed; scoped Ruff, format,
  and diff checks passed.
- VaultSpec RAG located the live profile command-spec authority and confirmed
  that the four payload schemas preserve retired-surface evidence. No command
  declaration or competing authority was introduced.
- The workflow and primary conformance assertion landed concurrently in shared
  commit `04ea7186d05`; the remaining local test edit is formatting-only.
