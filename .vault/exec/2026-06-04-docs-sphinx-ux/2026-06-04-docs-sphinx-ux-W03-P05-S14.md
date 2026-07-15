---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S14'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# run docs dependency and stub drift gates

## Scope

- `docs conformance lane`

## Description

Ran the full `dev/docs/tests/test_docs_build.py` battery at HEAD (commit `d029acb9968f`,
2026-07-15) to spot-check the adjudication's cited "19/19 green on 2026-07-14" evidence.
The battery is RED: 2 failed, 17 passed, contradicting the cited evidence.

Failures:

- `test_sphinx_nitpicky_build_is_clean` - the nitpicky `-n -W` build fails with two
  warnings treated as errors: `docs/api/index.md: WARNING: document isn't included in
  any toctree [toc.not_included]`, and a `py:func reference target not found:
  logging.Logger.makeRecord [ref.func]` warning against the `LogExtra` docstring in
  `cadrumo/core/logging.py`.
- `test_changed_docs_validation_does_not_pollute_repository_docs[dev/docs/cli_reference.py]`
  - the single-changed-page build subprocess returns non-zero, almost certainly the same
    root cause propagating through the single-page build path.

`docs/api/index.md` was added by commit `64b5a8a45d`
("docs(docs-sphinx-ux): add curated API boundary overview and retarget the root API
entry (W02.P04.S10-S11)") - a docs-sphinx-ux commit for steps S10/S11, which this
adjudication pass was instructed not to touch. The toctree-inclusion regression traces
to that commit, so this is an in-scope-feature regression, not unrelated peer churn.

## Outcome

Step NOT closed. Evidence for this step does not hold at current HEAD; closure is
aborted per the adjudication's own instruction to abort any closure whose evidence
fails spot-check. Reported to the team lead for triage of the S10/S11 toctree
regression before this step (and the dependent `S15` rendered-build step) can close.

## Notes

Full battery: `2 failed, 17 passed in 1246.06s (0:20:46)`. No files modified as part of
this verification attempt; this record is diagnostic only.
