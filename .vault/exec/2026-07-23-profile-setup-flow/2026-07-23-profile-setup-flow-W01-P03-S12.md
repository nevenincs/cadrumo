---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:25923bf60877beb11e471b2a6022ded34c8032eee724ed9875a5aaa7956a206f'
step_id: 'S12'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Add the censal file --file ingestion sub-command routing parsed facts through the manual enrolment path

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Description

- Add `config profile censo file --file PATH` (`_censo_file.py`), the
  one file-transport door for the G313 certificate per the
  pull-and-file standard; the `pull` sibling stays retired.
- Preview by default; `--apply` routes projected candidate facts
  through `set_active_fields` (the wizard's own manual-enrolment write
  path - no parallel route), always at the non-official artefact tier,
  stated on an info Notice.
- Typed payloads (`CensoFileFactPayload`, `CensoFileIngestResult`)
  registered on the shared envelope spine; verb copy in all four
  catalogues via the locales CLI.
- Three real-CLI integration tests pin the refusal envelope contract
  (parse code + suggestion) while extraction is unpinned, plus the
  boundary refusal on a missing artefact.

## Outcome

Committed (`feat(censo): config profile censo file ingestion verb`).
Verb suite 3/3 through the real cached CLI.

## Notes

The repo CLI conformance suites are red at HEAD from a peer regression
(commit `f065545fd7` removed `_ask_wizard_text` while
`_modelo_amend_wizard_cli.py` still imports it; 118 collection-level
failures) - owner-triaged and reported to the coordinator; this verb's
conformance re-verification is owed once the peer red clears.
