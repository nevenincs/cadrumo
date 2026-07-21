---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S423'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Localize parser wrappers, formula operators, draft state, verification advisories, and next actions for Catalan and Hungarian selected-language CLI journeys

## Scope

- `src/aeat/entrypoints/cli/ src/aeat/application/modelo/ src/aeat/locales/ src/aeat/**/tests/`

## Description

- Ground the S147 findings with `vaultspec-rag` and direct selected-language CLI probes.
- Localize Typer's vendored missing-parameter, invalid-value, integer-detail, and usage presentation after the root language selection resolves.
- Render formula operations and saved calculation state as localized text while leaving persisted values, JSON schema fields, identifiers, and formula operation tokens unchanged.
- Localize the persisted pre-activity cross-period advisory and its next action at the verification finding source.
- Add and populate locale leaves through `aeat.locales scaffold` and `aeat.locales set` for all supported locales.
- Add real subprocess Catalan and Hungarian M130 profile, calculate, and verify regressions.
- Correct the independent-review HIGH finding by retaining the canonical cross-period finding in the content-addressed report and localizing it only in CLI text, JSON, and notice projections.
- Add a cross-locale persisted-report regression: verify once in Catalan, view the same report in Hungarian, and read the encrypted catalogue through its production repository to prove unchanged identity and canonical stored semantics.
- Correct the renewed-review state-refusal leak in the selector-to-Typer adapter: retain the canonical selector exception and render only the already-verified verification refusal with the selected language's human state label.
- Add real Catalan and Hungarian already-verified `work verify` refusal coverage and a non-granted M390 draft re-verification route that proves same-revision report identity and one-record persistence across locales.
- Correct the third-review M390 finding leak by matching only the canonical `cross_period_dependency_unclean` message and its observed evidence-capture next action at the CLI rendering boundary; retain every persisted field, context value, machine reference, and report identity unchanged.
- Extend the real non-granted M390 Catalan-to-Hungarian re-verification journey with localized blocking-message and next-action assertions alongside its stable report ID and single-record persistence checks.

## Outcome

Implementation corrected after independent review; awaiting renewed review. The direct selected-language personas emit localized parser errors, formula labels, draft state, verification advisories, next actions, and already-verified refusals for the recorded S147 surfaces. The cross-locale report regressions prove that selecting a language changes only the projection, not the persisted finding or report identity, including the non-granted M390 blocking finding.

## Notes

- `ruff check` passed for every touched source and test module.
- Focused unit coverage passed: 15 tests in `test_modelo_state_text_labels.py` and `test_cross_period_clean_state_gates.py`.
- Focused real-entrypoint coverage passed: 2 selected-language subprocess personas in `test_s423_selected_language_cli.py`.
- `aeat.locales scaffold --check` and `aeat.locales audit` passed for ca, en, es, and hu.
- Scoped diff review and `git diff --check` found no S423 defect. A concurrent pre-existing docstring addition in `_modelo_rendering.py` was excluded from S423 review ownership.
- The shared rolling audit was deliberately not edited, per execution direction.
- Independent review reopened S423 because localized prose entered content-addressed verification findings. The repair keeps the canonical raw message/action persisted and applies localization in `_modelo_rendering.py` only.
- Renewed focused gates: Ruff passed; 15 focused unit tests passed; the parent-run explicit selected-language integration group passed with 3 tests in 162.84s; locale scaffold and audit passed.
- Renewed review also found raw English and Spanish state tokens in the already-verified selector refusal. The CLI-only selector adapter now localizes the exact verified-complete verification refusal without changing the canonical selector error or any persisted record.
- Focused reruns passed: the non-granted M390 cross-locale re-verify continuity test passed in 60.77s; the Catalan and Hungarian already-verified refusal personas passed in 112.20s; the canonical persisted-report projection test passed in 52.67s; Ruff, 15 focused unit tests, locale checks, and scoped diff check passed.
- Third review found that the canonical M390 `cross_period_dependency_unclean` message and its evidence-capture action still projected in English. The exact full-message/full-action renderer match localizes only that observed M390 form; the separate missing-activity finding and all stored values remain canonical.
- Final replay passed: all 4 real selected-language subprocess personas completed in 211.30s, including the non-granted M390 Catalan-to-Hungarian re-verification with localized blocking message/action, one stable report ID, and one encrypted-catalogue report record. Ruff, 15 focused unit tests, locale scaffold/audit, and scoped diff checks also passed.
- S423 remains unchecked pending renewed independent review.
