---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S286'
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
     The S286 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: replace monkeypatch.setenv abuse in application/auth/test_operator.py lines 230-260 and 477-521 with Settings override fixture and ## Scope

- `AEAT_CERTIFICATE_PATH and AEAT_CLAVE_MOVIL_DNI_NIE injection in application-layer tests should not use env-var monkeypatch`
- `src/aeat/application/auth/test_operator.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: replace monkeypatch.setenv abuse in application/auth/test_operator.py lines 230-260 and 477-521 with Settings override fixture

## Scope

- `AEAT_CERTIFICATE_PATH and AEAT_CLAVE_MOVIL_DNI_NIE injection in application-layer tests should not use env-var monkeypatch`
- `src/aeat/application/auth/test_operator.py`

## Description

- Run the required code RAG search for the auth operator env-var monkeypatch sweep.
- Inspect local execution, quality-gate, and test-integrity rules for the no-monkeypatch contract.
- Inspect auth test Settings override patterns in `test_operator.py`, `test_ensure_session.py`, and nearby application tests.
- Verify that the target certificate and Cl@ve Móvil injection cases already use `override_settings` or explicit `Settings` objects instead of env-var monkeypatching.
- Run the focused auth operator pytest and ruff gates.
- Review the target surface against the plan row and rules; no blocking findings were found.

## Outcome

`W09.P41.S286` is satisfied with no new source edit required in this execution pass. The target auth operator test file contains no `monkeypatch.setenv`, `AEAT_CERTIFICATE_PATH`, or `AEAT_CLAVE_MOVIL_DNI_NIE` references, and the focused auth operator tests passed with 26 tests green.

## Notes

The working tree already carried unrelated uncommitted edits, including a pre-existing formatting-only diff in `test_operator.py`; those changes were left untouched and are not part of this step closure.
