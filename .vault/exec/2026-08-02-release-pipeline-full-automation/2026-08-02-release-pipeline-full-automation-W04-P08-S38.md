---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:6fed425e513ac0f1bb51bc78c1c22c0f2caec3c25ef7d2f28a0d1f4fecb21421'
step_id: 'S38'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Narrow the delivery record OP-3 on every operator-facing surface to its one remaining half, the deploy-role variable on the already-created docs environment, and state alongside it that the docs environment required_reviewers removal is the second half of OP-9 rather than a separate obligation, so a reader is not told to create an environment that exists, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions section asserting exactly the outstanding halves and ## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Narrow the delivery record OP-3 on every operator-facing surface to its one remaining half, the deploy-role variable on the already-created docs environment, and state alongside it that the docs environment required_reviewers removal is the second half of OP-9 rather than a separate obligation, so a reader is not told to create an environment that exists, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions section asserting exactly the outstanding halves

## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

Narrowed OP-3 on RELEASING.md's Operator actions section and the Distribution-complete tripwire prose: the `docs` GitHub environment already exists (created alongside `release`, carrying the same `required_reviewers` rule OP-9 removes from it), so OP-3's only remaining half is setting the deploy-role variable `docs-publish.yml` reads to assume its OIDC role on `release: published`. States explicitly that removing the `docs` environment's `required_reviewers` rule is the SECOND HALF OF OP-9, not a separate obligation, so a reader is never told to create an environment that exists or perform the same rule-removal twice under two different names. Extended `test_releasing_doc_operator_actions_section_names_the_outstanding_halves` (added in S37) to also assert the OP-3 wording, the "already exists" phrase, and the "second half of OP-9" phrase are present — normalizing whitespace first (`" ".join(section.split())`) since RELEASING.md's ~80-column prose wrap can split a multi-word phrase across a line break, which a raw substring check would falsely fail on.

## Outcome

Gate green: `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q` — 9 passed. Verified the ACTUAL committed content this time (not just the pre-commit staged diff), per the lesson from S37's incident: `git show --stat d78b5c4c85` confirms exactly 2 files / 37 insertions / 9 deletions, and `git show d78b5c4c85:src/cadrumo/tests/test_release_config.py | grep -c bootstrap_sha` returns 3 (the pre-existing, untouched peer content from S37's fix-forward commit) with no additional entanglement. HEAD had already advanced past this commit by the time of verification (a peer's `feat(release): chain the packaging campaign by run identity` landed immediately after) — confirmed by SHA, not by assuming HEAD still pointed at my own commit.

## Notes

No incidents on this Step. This closes W04.P08 in full: S36, S37, and S38 all landed and checked, completing the phase's three independent-of-W02/W03 Steps per the team-lead's dispatch scope (P06 alerting and P07 runbook collapse remain blocked on the W03 orchestrator, per the plan's own parallelization note).
