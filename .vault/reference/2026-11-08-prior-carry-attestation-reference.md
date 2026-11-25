---
tags:
  - '#reference'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:45f311666f991423b22f9fe104bc135b159bb6ce6fdb5304c46cf1c44fcabc9f'
related: []
---

# `prior-carry-attestation` reference: `how an absent prior-year carry reaches the Modelo 100 edit`

Traced from the APP-QA D33 run (cadrumo.log, 2026-11-08 08:43Z to 09:06Z) through
the production resolvers and the edit pipeline, at commit 22cf420559.

## Summary

- The four Modelo 100 Anexo C carries read the previous Modelo 100: 1380 from
  1384, 1382 from 1387, 1385 from 1390 and 1388 from 1391, declared from
  `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:47`
  and `:1084`, citing Ley 35/2006 art. 50.
- The previous-filing provider is
  `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
  (`resolve_previous_filing_binding_values`). With no stored observation it leaves
  the binding unsatisfied. With an observation that lacks the source casillas it
  returns `_UnobservedCasillas` and raises
  `errors.calc.previous_filing_casillas_unobserved`.
- Filing the Modelo 130 chain stores a previous-year Modelo 100 observation
  holding only the boxes a 130 reads (0224, 1479, 1553, 1577), so the carries
  raised that refusal even when the filer had typed them.
- The edit pipeline is `apply_modelo_edit`
  (`src/cadrumo/application/modelo/edit_execution.py`). It runs `_prepare_edit`,
  then the calculation; `pre_effect_refusal` turns a pre-effect `CadrumoError`
  into a typed no-effect refusal. A refusal without an address delivers no
  prerequisite to `modelo.edit.apply_prerequisite`, so the window had no door.
- The operator's values live in `CalculationOperatorLayer`
  (`src/cadrumo/domain/modelos/calculation_revision_operator_layer.py:39`) as
  canonical strings per binding, with nothing saying how a value was meant.
  Binding intents are `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE`
  (`src/cadrumo/application/modelo/edit_models.py:125`).
- A caller value that differs from a filed figure is recorded as
  `precedence_tier_divergence`, one of the disagreement reasons in
  `src/cadrumo/domain/modelos/calculation_revision_sources.py:265`, and the form
  serves its action through `src/cadrumo/application/modelo/work_form_issue_lines.py:99`.
- A bound box empty before any calculation is classified `NOT_IMPORTED_YET`
  (`src/cadrumo/application/modelo/work_form_field_state.py:107`), whose family
  words read "not in your profile yet" for profile-fed boxes such as the
  declarant's NIF.
- The edit baseline lasts five minutes
  (`src/cadrumo/application/modelo/edit_admission.py:76`); renewal re-admits it
  only when nothing but its lifetime changed (`edit_admission.py:451`).
