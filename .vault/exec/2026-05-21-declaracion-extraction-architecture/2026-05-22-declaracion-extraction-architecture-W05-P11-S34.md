---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S34'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-W03-P06-S20]]'
---

# W05.P11.S34 - M180 real declaration round-trip

BLOCKED. No Modelo 180 declaration PDF fixture exists in the local corpus, and the current M180 registry only exposes `export_record` extraction profiles for submitted-file artefacts.

Evidence checked:
- `src/aeat/tests/fixtures/` contains no Modelo 180 declaration/justificante PDF.
- `src/aeat/_data/registry/aeat/modelos/180/**/extraction_profiles/*.toml` contains only `accepted_artefact_kinds = ["submitted_file"]`.
- Existing W03.P06.S20 already records the legal/source blocker: M180 casilla IDs are electronic record positions, so `numeric_casilla` cannot be grounded against a printed declaration; a `named_label` profile needs real printed-form labels.

Action taken:
- Added backlog prerequisite `W05.P11.S92` to acquire a real Modelo 180 declaration PDF fixture from an authorised source before implementing S34.

No code changes for S34.
