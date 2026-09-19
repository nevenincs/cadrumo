---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:be9b57958101ab84d2598459b1392a5180b2f0945946ef8fc75168106628c491'
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

## Update: race explained, re-run green

The two failures were a stale build-snapshot race in the fast-moving shared worktree,
not a live regression:

- `docs/_inventories/python.inv` (the offline-hermetic vendored inventory the gate
  reads) contains `('py:method', 'logging.Logger.makeRecord')` and no `py:function`
  entry for it, so `:meth:` resolves correctly and `:func:` can never resolve. The
  `LogExtra` docstring at `cadrumo/core/logging.py:97` already reads `:meth:` (fixed by
  `a35b9fc00c`), confirmed by a live `import cadrumo.core.logging` reading the editable
  worktree source. Several of my re-runs, launched at different points across this
  session while peers actively landed commits into this shared worktree, snapshotted
  the docstring and the doc tree via `shutil.copytree` + `autodoc` import at moments
  that predated `a35b9fc00c` and/or `64b5a8a45d` even when the git `HEAD` I separately
  queried had already advanced past them - three of my runs reproduced the identical
  warnings this way.
- The team lead's independently-launched `test_sphinx_nitpicky_build_is_clean` run
  PASSED (1 passed, 766.51s) with both fix commits confirmed present in the built tree.
- I re-ran `test_changed_docs_validation_does_not_pollute_repository_docs[dev/docs/cli_reference.py]`
  fresh at HEAD `807778bd87bc` (2026-07-15T09:03:16+02:00, confirmed a descendant of both
  `a35b9fc00c` and `64b5a8a45d` via `git merge-base --is-ancestor`): `1 passed in 7.57s`.

Both previously-failing tests are green at current HEAD. No source change was needed;
the "regression" was an artefact of test-launch timing against a fast-moving tree, not
a defect in `64b5a8a45d`'s toctree retarget or `a35b9fc00c`'s docstring fix.

## Outcome

Step closed. Gate evidence: `test_sphinx_nitpicky_build_is_clean` green (team lead's
run, 766.51s) and `test_changed_docs_validation_does_not_pollute_repository_docs[dev/docs/cli_reference.py]`
green (this run, HEAD `807778bd87bc`, 7.57s). Both fix commits (`a35b9fc00c`,
`64b5a8a45d`) confirmed ancestors of that HEAD.

## Notes

Original (now-superseded) diagnostic: full battery `2 failed, 17 passed in 1246.06s
(0:20:46)` at an earlier, stale-relative-to-fixes snapshot. No files modified as part of
either verification pass; this record is diagnostic plus the closing gate evidence.
