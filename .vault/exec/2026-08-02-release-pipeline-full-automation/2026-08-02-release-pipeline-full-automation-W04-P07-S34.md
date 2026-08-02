---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:6fffd752c9552866cb2df0683a8669a370162bcf3d44484f8a1f64769e6f4c9f'
step_id: 'S34'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Rewrite the RELEASING.md release-candidate soak stage to describe the machine-held wait, naming the candidate record, the promoter cadence, and the hotfix carve-out, so the documented soak and the enforced soak describe the same mechanism rather than a human holding a tag, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the release-candidate soak assertions retained and re-pointed at the promoter

## Scope

- `RELEASING.md`
- `docs/_release_checklist.yaml`
- `src/cadrumo/tests/test_release_config.py`

## Description

- Rewrite RELEASING.md's soak section (formerly `### Stage 0b:
  release-candidate soak (non-hotfix releases)`, describing a human
  creating a local `vX.Y.Z-rc.N` tag, manually running smoke twice, manually
  installing into a scratch venv, manually holding for 48 hours, then
  manually pushing the final tag) with `### Release-candidate soak
  (machine-held)`, naming the three real mechanism pieces: the sealed
  `dev.release.release_candidate` record (version, source commit, every run
  id, claimed channels, `dry_run`, computed deadline), the
  `release-soak-promoter.yml` hourly-cron cadence (select eldest-elapsed,
  re-verify readiness against the sealed cohort immediately before
  dispatching -- a regression invalidates rather than promotes on a stale
  green, and is never repaired in place -- dispatch `publish-release.yml`
  with the recorded run ids, mark consumed once the dispatch succeeds), and
  the hotfix carve-out (authorised ON THE CANDIDATE via an incident
  reference plus release-owner approval, refused at construction without
  both -- never a promoter-time input, so an emergency is recorded where it
  can be audited).
- Rewrite `docs/_release_checklist.yaml`'s `soak.vehicle` and
  `soak.exit_gates` from "local, tagged pre-release build... reviewed over
  the soak window before the real tag lands" to the sealed
  release-candidate record and its promoter re-verification, and the module
  docstring comment from "a human always runs `just release-apply`... and
  decides whether to push and publish" to naming the bump-time and Gate-2
  re-checks that now read this file. Field names and the pydantic
  `SoakChecklist` model shape are unchanged (`extra="forbid"`; only prose
  values moved), so no schema edit was needed.
- Retained the `just release-readiness` local-diagnostic mention (S32) so the
  documented soak and the enforced soak describe the same mechanism without
  losing the still-genuinely-useful local pre-check.

## Outcome

Gate green: `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q`
passes 9/9, including `test_releasing_doc_documents_rc_soak_and_rollback`
(the release-candidate-soak, rollback, `just release-readiness`/
`just release-rollback`, and `docs/_release_checklist.yaml` assertions all
still hold against the rewritten prose) and the `ReleaseChecklist`/
`SoakChecklist` strict-model parse of the rewritten
`docs/_release_checklist.yaml`.

## Notes

None.
