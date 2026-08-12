---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c7dfabc3b62be596386cdc1097241b8d48a94cbca2205387b548c5bcb94614f0'
step_id: 'S27'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# widen the modelo.requires classifier to bucket previous_filing, relation_prefill and live_observation sources, read alternate bindings, and surface unbucketed sources as an advisory

## Scope

- `src/cadrumo/application/modelo/_data_inventory.py`
- `src/cadrumo/application/modelo/tests/test_data_inventory_profile_keys.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_requires_data_inventory.py`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/hu.yml`

## Description

- Classify each canonical bound-casilla binding pair through `bound_casilla_binding_ids` instead of reading only the primary binding.
- Add distinct `previous_filing`, `relation_prefill`, and local observation/register/invoice-backed `live_observation` checklist buckets.
- Preserve sources outside the explicit classifier in `unbucketed_sources` and emit a localized warning Notice with source, binding, and casilla facts but no invented recovery action.
- Extend the strict `modelo.requires` payload and text projection with four stable machine section names.
- Replace the mirrored classifier expectation with real bundled-registry behavior for M130, M100 alternate bindings, and M390 local-state resolvers.

## Outcome

`modelo.requires` no longer silently omits cross-filing sources or alternate bindings. One casilla may appear once per declared binding-source pair, preserving M100 casilla 0596's two relation-prefill bindings and its `manual_input` alternate. That alternate is deliberately unbucketed and proves the advisory against the bundled corpus.

`live_observation` means local application state read by active calculate resolvers; it does not claim a remote AEAT query. Review found that `ATRIBUCION_MEMBER` reads active-profile facts, so it was removed from the live-observation family. Bundled M184 2025 has four attribution-member binding declarations but no bound-casilla pairs; the production-backed regression therefore pins the real resolver's source ownership directly rather than fabricating a CLI row.

## Notes

- Primary implementation landed in `b20a786869`; the review repair regression landed in `6ce2a97018`. The second commit is a review-discovered correction, not a compatibility surface or history rewrite.
- Focused application and CLI behavior passed 8 tests after repair.
- Ruff format and check passed across the changed Python surfaces; strict BasedPyright passed the classifier and direct tests with zero diagnostics; scoped diff checks passed.
- The exact isolated console command `aeat --format json app modelo requires 130 --year 2024 --period 2T` succeeded and emitted all four new fields plus the previous-filing row.
- The broader schema lane passed 339 tests with one unrelated quiet-profile fixture failure before S27 behavior. Broad CLI BasedPyright retains 146 existing diagnostics.
- Locale scaffold check retains unrelated catalogue drift; the S27 advisory key is present in all four catalogues and is consumed without a fallback default.
