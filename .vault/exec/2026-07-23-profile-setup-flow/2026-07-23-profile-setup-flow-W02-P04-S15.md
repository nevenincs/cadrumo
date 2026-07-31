---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:c23c37f5c455fe2615a99526f3d4c7c2f933cf4d3102230094e029e32ae84d78'
step_id: 'S15'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Regenerate the api reference stubs and re-verify documented-command conformance after the re-sequence

## Scope

- `docs/api/`

## Description

- Run the apidocs drift gate after the re-sequence: the catalogue
  reorder itself adds/removes no modules, but the gate surfaced the
  stub owed from the profile-grounding module's landing.
- Regenerate stubs via the apidocs CLI and commit this feature's slice
  (`_profile_grounding` stub + registry parent toctree) with an
  explicit pathspec.
- Re-verify documented-command conformance post-re-sequence (348/348,
  run as part of the S13 landing).

## Outcome

Committed the stub slice (`docs(api): stub the profile-grounding
registry module`). Conformance 348/348 green.

## Notes

The scaffold run also regenerates the substrate stream's flows/tui
stubs (17 files); left uncommitted for that stream's sweep - the
generated-reference discipline says regenerate-never-hand-edit, and
committing them belongs to the module owner's landing.
