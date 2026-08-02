---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:42d93c9e812faee22514d21b7aea991d0db39a2aeb477113bce5a16520634bda'
step_id: 'S35'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Sweep every remaining user-facing and developer-facing surface that describes the release flow as part-manual, including the release notes template soak wording and any documented command naming the deleted apply target, gate: uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q and uv run --no-sync pytest dev/docs/tests -m docs -q pass

## Scope

- `docs/`
- `dev/docs/tests/`

## Description

- Swept the tree for remaining part-manual release-flow prose and the
  deleted `release-apply` target (S32-S34 covered `RELEASING.md`;
  this Step covers everything else): `docs/_release_checklist.yaml`'s
  header comment ("a human always runs `just release-apply`... reviews the
  printed checklist, and decides whether to push and publish" ->
  automated bump-time + Gate-2 re-checks) and `audit_state_gate.description`
  ("before `just release-apply` is trusted" -> "run automatically by the
  bump stage and again by publication Gate 2"), landed alongside S34's soak
  rewrite since both are the same file.
- `docs/_release_notes_template.md`'s intro comment described filling the
  block "from the `just release` dry-run log... and paste it as the GitHub
  Release body when the tag is pushed" -- stale, since Gate 3 now creates
  the GitHub Release automatically. Rewrote to describe pasting the
  hand-filled longer-form companion into the auto-created release body
  after publication, and sourcing the soak-window line from the sealed
  release-candidate record's actual `opened_at`/deadline rather than
  implying a human tracked it.
- Confirmed via `rg -rln "release-apply|CADRUMO_PUBLISH_ENABLED" docs/` that
  no other file under `docs/` names either; `README.md` carries neither.

## Outcome

`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q`
passes 354/354.

`uv run --no-sync pytest dev/docs/tests -m docs -q` is RED (21 failed, 208
passed), but every one of the 21 failures is attributed to unrelated,
pre-existing peer churn, not this Step's changes -- confirmed by grepping
the full failure output for `RELEASING|release_checklist|release_notes_template|releasing`
(zero matches) and by inspecting the failure causes directly: two Sphinx
autodoc import errors for `cadrumo.core.identity._snapshot` /
`._transaction`, modules that genuinely do not exist on disk
(`ls src/cadrumo/core/identity/` confirms; `git log` on that directory shows
recent unrelated identity-primitive refactor commits, e.g. `72286e9c66`) --
an orphaned API-doc stub from another campaign's incomplete
`apidocs scaffold` sweep, per `aeat-docs-scaffolding-cli`. The other 19
failures are translation-completeness (es/ca/hu), docs-search deployment
parity, API-stub coverage, and sequence-golden drift -- none plausibly
caused by a markdown/YAML prose rewrite. Per the plan's own Verification
section ("a red owned by a peer campaign is recorded and attributed, never
absorbed silently into this plan's completion claim"), this Step is closed
on the scoped evidence above rather than the raw suite exit code.

## Notes

Not further diagnosed or fixed -- fixing the orphaned identity-module doc
stubs or the other 19 failures is unrelated campaign work, well outside this
Step's `docs/, dev/docs/tests/` scope and the runbook-collapse plan this
Phase executes. Flagged to the coordinator for triage/routing to whichever
campaign owns `cadrumo.core.identity` and the docs-search/i18n/goldens
surfaces.
