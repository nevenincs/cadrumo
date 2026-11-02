---
tags:
  - '#reference'
  - '#desktop-renta'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:00747637a89d755b61525c6007dd36cf980d3a4d045bff918f49cd0e850957e1'
related: []
---

# `desktop-renta` reference: `Renta workspace served shapes and gaps`

How the application serves the 2025 Modelo 100 to the desktop today, read for synthetic taxpayers through the registered read path (`modelo.work.form` and its builder in `src/cadrumo/application/modelo/work_form.py`), the profile view and the setup flow. Haiku discovery agents produced leads, and each finding below was checked against the code or a real envelope. Semantic search was not used.

## Summary

- The form layout is generated (`seed_source` xml_dictionary) for revisions 2020 to 2025 under `src/cadrumo/_data/registry/aeat/modelos/100/revisions/`. A 2026 Modelo 100 has no revision in force.
- The 2025 layout has 4 pages and 87 sections. 75 section headings are dictionary tokens served with disclosure `technical` (`src/cadrumo/application/modelo/work_form_models.py:116`), and 12 are localized. Page conditions are all `always`.
- Only two repeating blocks exist: inventory activity rows (0177, 0181, 0182) and patrimonial element rows. Descendants and ascendants are flat boxes.
- The envelope is about 3.8 MB per language, under the relay frame limit of 16,776,960 bytes.
- The calculation refuses without binding `renta-base-liquidable-negativa-general-anterior` (1388) and `renta-modelo-100-estimacion-directa-es-normal` (0168) and raises ModeloWorkMissingInputError. The form serves both as optional or overridable, not as needing the filer.
- Section counts show needs_input 0 and blocked 0 while 54 boxes need the filer, so the section attention roll-up is missing.
- Box 0700 is served as `editable_value` with origin words "Optional, left at 0" and no formula.
- Withholding boxes 0596, 0597 and 0603 are served `imported` with editability `source_policy_undecided` and source family registers. Their issue lines carry `surface: null`, so the read does not name the withholding register as the correction surface. Box 0599 is `locked_source` with an advisory proven-zero note.
- `modelo.project` result version 2 exists on feature/renta-withholding only (commits 009999acb4 and 38dafae403). It serves `unresolved_bindings` and `unresolved_casillas` as tokens with no words, and it refuses a caller value for 0596, 0597 and 0603.
- The export offer serves elections only where `asks_export_elections` is true (`src/cadrumo/application/modelo/work_form_export_offer.py:355`). For Modelo 100 `elections` is empty. The 303 serves refund, payment and prior-domiciliation questions.
- `modelo.work.compare_taxation` serves `recommendation_reason` as free text (`src/cadrumo/application/modelo/taxation_comparison_operation.py:79`), English only.
- `modelo.work.wizard_context` returns 1996 steps with Spanish labels in every language, uses raw binding ids as labels, and omits 1388.
- The imputation criterion is the profile path `irpf.activity_income_imputation_criterion` (`src/cadrumo/application/wizard/imputation_election.py:33`). It is written only through `election_changes` (`src/cadrumo/application/wizard/imputation_election.py:39`), and no registered operation reads or writes it.
- `user-profile.view` serves renta_filing, renta_taxpayer, renta_spouse and renta_family. declaration_type is a free string with its codes in help and no choices. The descendant and ascendant arrays are not served. `user-profile.descendants` exists but is not admitted (`native/desktop/src-tauri/src/shell/user_profile.rs:234`).
- `live.borrador.100.read`, `query` and `import` exist. Only import is admitted (`native/desktop/src-tauri/src/shell/aeat_sync/admitted.rs:66`). No borrador-versus-calculation comparison read exists.
- The fixture generator declares no Modelo 100 (`native/desktop/frontend/scripts/modelo_fixtures.py:65`).
