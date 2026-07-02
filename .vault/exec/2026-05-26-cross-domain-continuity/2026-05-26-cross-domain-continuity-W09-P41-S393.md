---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S393'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S393 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The FU-task-198 land Convenio doble imposicion + representante fiscal IRNR surfacing for Olivia round-16 and ## Scope

- `harmonise representante_fiscal_nif field shape between user_profile schema task 197 partial work and the Phase 1 M210 engine`
- `surface representante-fiscal-required refusal at modelo work create when fiscal_residency=NON_RESIDENT and ue_eee_status is False`
- `src/aeat/domain/user_profile/_schema.py + src/aeat/entrypoints/cli/_modelo.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# FU-task-198 land Convenio doble imposicion + representante fiscal IRNR surfacing for Olivia round-16

## Scope

- `harmonise representante_fiscal_nif field shape between user_profile schema task 197 partial work and the Phase 1 M210 engine`
- `surface representante-fiscal-required refusal at modelo work create when fiscal_residency=NON_RESIDENT and ue_eee_status is False`
- `src/aeat/domain/user_profile/_schema.py + src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground the row with RAG for M210 representative-fiscal work-create behavior and the S393 plan context.
- Confirm the user-profile schema and M210 registry predicate already expose `representante_fiscal_nif`, `representante_fiscal_nombre`, and `m210-representante-fiscal-required` under TRLIRNR Art 10.
- Reproduce the remaining gap: M210 engine-live `work create` for a legacy non-EEA IRNR profile missing representative facts leaked a generic CLI validation-boundary error before the readiness gate surfaced the missing fields.
- Catch `ValidationError` only around the applicability projection in `modelo_work_create_applicability_refusal`, returning `None` so the existing profile-readiness gates produce the operator-facing refusal before any work unit is created.
- Add a real CLI regression for the engine-live M210 missing-representante path and a separate ordering regression proving not-applicable M130 still wins over pre-activity readiness for an IRNR profile.
- Preserve service import boundaries through the application package facades after code review.

## Outcome

- `aeat app modelo work create --modelo 210` with `aeat_m210_engine_live=True` now reports `REFUSED_MODELO_PROFILE_READINESS` for a legacy GB IRNR profile missing `taxpayer_type.representante_fiscal_nif` and `taxpayer_type.representante_fiscal_nombre`, rather than leaking `REFUSED_CLI_VALIDATION_BOUNDARY`.
- Existing applicability ordering is preserved: resident-IRPF M130 creation for an IRNR profile with a future activity date still reports the not-applicable refusal and `--allow-not-applicable` guidance before pre-activity readiness.
- Focused validation passed: 10 integration checks across the new regressions, work-create applicability, and profile-create representative refusal; 17 M210 convenio-rate tests; ruff on changed Python files; scoped diff-check.
- S393 was closed through the vault plan CLI after review passed.

## Notes

- Review rejected the first implementation because an early readiness call could have changed unrelated refusal ordering. The accepted patch instead defers only projection-validation failures from the applicability policy to the existing readiness gate.
- Full `test_modelo_work_readiness_ux.py -m integration` still has an unrelated dirty-worktree M349 readiness expectation failure caused by concurrent applicability-rule edits outside the S393 write set.
- Shared worktree already contained extensive unrelated dirty state; this step did not revert, clean, stage, or commit unrelated files.
