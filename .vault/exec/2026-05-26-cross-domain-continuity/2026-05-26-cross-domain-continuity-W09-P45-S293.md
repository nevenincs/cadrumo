---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S293'
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
     The S293 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R8-MARC-B verification finding text drifts to Castellano while CLI interface is Catalan and ## Scope

- `missing_required_casilla finding inner text not routed via tr() with profile output_language context`
- `locate verification finding rendering and route the message body via tr()`
- `src/aeat/application/modelo/_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R8-MARC-B verification finding text drifts to Castellano while CLI interface is Catalan

## Scope

- `missing_required_casilla finding inner text not routed via tr() with profile output_language context`
- `locate verification finding rendering and route the message body via tr()`
- `src/aeat/application/modelo/_actions.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Ground the testimonial with `vaultspec-rag` against the cross-domain continuity plan and current verification finding implementation.
- Confirm that the current missing-required-casilla owner is `src/aeat/application/modelo/_verification_actions.py`, not the stale plan-row path `src/aeat/application/modelo/_actions.py`.
- Verify that `_missing_required_casilla_finding` already renders `application.modelo.findings.missing_required_casilla` through `tr()`.
- Add a real active-profile language regression using the secure runtime, `UserProfileLifecycleRepository`, and the live Modelo 130 registry casilla definition.
- Assert that the same finding renders Catalan under an active profile with `preferences.output_language=ca`, then Spanish under `preferences.output_language=es`.

## Outcome

- Closed with regression coverage only. No production change was needed because the live implementation already routes the finding message through `tr()` and the central output-language resolver.
- Closed. The new regression proves the Catalan message contains `La casella obligatòria`, the Spanish message contains `La casilla requerida`, and the Spanish phrase does not leak into the Catalan rendering.
- Closed. Existing companion tests continue to prove the message is not the raw locale key, interpolates the casilla id, and carries registry legal/source provenance.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Review found no issues. Residual risk is limited to the regression asserting representative localized substrings rather than the full rendered message; existing tests cover interpolation and non-key rendering.
- Validation: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_verification_finding_language.py -q` passed.
- Validation: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_actions.py::test_missing_required_casilla_finding_message_is_localised src/aeat/application/modelo/tests/test_actions.py::test_missing_required_casilla_finding_message_changes_with_casilla_id src/aeat/application/modelo/tests/test_verification_substance_workflow.py::test_missing_required_casilla_finding_carries_registry_provenance -q` passed.
- Validation: `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_verification_finding_language.py` passed.
