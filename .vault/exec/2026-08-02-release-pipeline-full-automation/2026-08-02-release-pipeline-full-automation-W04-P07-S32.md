---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:46facf424700bd6ea6524cf5def74fb7fd932de82bb658e83ada8f6b396b7b5e'
step_id: 'S32'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Collapse the RELEASING.md release procedure from six part-manual stages to one dispatch followed by a post-publication verification tail, deleting the Stage 0 hand-transcription, the Stage 2 per-lane dispatch instructions, and the Stage 4 Gate 1 description that went with the deleted job, while keeping the reacquisition lanes and the docs tripwire described as verification rather than authorisation, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q and uv run --no-sync pytest dev/docs/tests -m docs -q pass with the runbook conformance assertions updated to the single-dispatch shape

## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

- Replace RELEASING.md's `## Operate a release` six-stage part-manual runbook
  (Stage 0 hand-transcription of the seven surfaces, Stage 0b's local-tag
  hand-soak, Stage 1-3's build/acquire/aggregate narration of what CI now
  does unattended, Stage 4's manual `gh workflow run publish-release.yml`
  dispatch plus its Gate 1 description, Stage 5's reacquisition) with four
  sections matching the landed automation: `### Dispatch the release` (one
  `release-orchestrator.yml` dispatch, its five automatic stages listed),
  `### Release-candidate soak (machine-held)` (the promoter mechanism),
  `### Publish` (Gate 2 + Gate 3, Gate 1 description deleted since W01
  deleted the job it described), `### Post-publication verification`
  (reacquisition lanes + docs tripwire, explicitly framed as verification
  rather than authorisation).
- Rewrite the top summary paragraph and the "Release at a glance" table from
  6 stages to 4 phases matching the new sections.
- Update `src/cadrumo/tests/test_release_config.py`'s
  `test_releasing_doc_documents_rc_soak_and_rollback` assertions: the
  now-optional `just release-readiness` local-diagnostic mention is kept
  (still true -- the recipe survives, just isn't mandatory), and the
  "release-candidate soak" literal-match is satisfied from body prose (the
  heading itself is capitalised, "Release-candidate soak", which does not
  match the test's lowercase substring -- fixed by adding a lowercase
  in-prose mention rather than weakening the test).

## Outcome

Gate green: `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q`
passes 9/9. `uv run --no-sync pytest dev/docs/tests -m docs -q` is RED (21
failed, 208 passed) but on inspection every failure is unrelated pre-existing
peer churn (Sphinx autodoc import errors for two genuinely-deleted
`cadrumo.core.identity` modules, translation-completeness, docs-search
parity, API-stub coverage, sequence-golden drift) -- none reference
`RELEASING.md` or any file this Step touched. Full attribution recorded on
the `W04.P07.S35` exec record, whose gate is the same suite; not duplicated
here.

## Notes

None.
