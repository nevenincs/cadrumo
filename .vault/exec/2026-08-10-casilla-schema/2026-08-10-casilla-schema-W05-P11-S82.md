---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:861969fdb5f4ffb11f16697eea4015c48e275a5ed5c0de38459224ea1661e200'
step_id: 'S82'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# destructively rename the OfficialBoxStatus, official_box_status, and classify_official_boxes family to one Spanish casilla-stem authority, sweep every consumer, and prove zero English-name references without aliases or compatibility exports

## Scope

- `src/cadrumo/core/ and src/cadrumo/domain/calculations/registry/_export.py and src/cadrumo/application/modelo/ and src/cadrumo/adapters/inbound/tui/`

## Description

- Rename the core enum and owner module to `EstadoCasillaOficial` and `_estado_casilla_oficial.py`.
- Rename the registry classifier and private helpers to the `clasificar_casillas_oficiales` and casilla-stem family.
- Replace the review-row field with `estado_casilla_oficial` and retarget the modelo producer, TUI filters, locale registrations, and four locale catalogues.
- Preserve the serialized status values `addressed`, `represented_via_binding`, and `undefined` while deleting every retired Python identity, module, facade export, field, and filter key.
- Add sole-owner, real registry, TUI, and serialized-envelope proofs.
- Ratchet the complete retired family across every existing text-bearing file under `src/` and `dev/`, covering Python, registry/configuration, locale, markup, script, query, and sequence suffixes plus retired path names.
- Prove the ratchet bites by planting `official_status` in a temporary non-Python `dev/locales/*.yml` surface and requiring the production-free structural scanner to report it exactly.

Modified and renamed surfaces:

- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/_estado_casilla_oficial.py`
- `src/cadrumo/core/tests/test_estado_casilla_oficial.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/domain/calculations/registry/tests/test_clasificacion_casillas_oficiales.py`
- `src/cadrumo/application/modelo/_work_review.py`
- `src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py`
- `src/cadrumo/adapters/inbound/tui/tests/test_modelo_work_review_screen.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_work_review_envelope.py`
- `dev/locales/_fstring_registry.py`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/hu.yml`

## Outcome

- Passed 16 focused core, registry, review-model, schema-envelope, and TUI tests in 56.82 seconds.
- Passed the strengthened sole-owner, complete zero-retired-reference, and planted non-Python bite proofs independently: 3 tests in 31.78 seconds.
- Passed targeted BasedPyright with zero errors, warnings, or notes.
- Passed path-scoped Ruff and formatting checks.
- Passed direct imports of the core and registry facades, asserted the new review model field, and proved both retired facade attributes absent.
- Proved zero occurrences across `src/` and `dev/` of the retired enum, field, classifier, owner/classifier filenames, private channel helper, generic filter axis, concrete TUI filter id, and locale path tokens.
- Preserved the three external enum values and proved the serialized envelope emits only `estado_casilla_oficial`.

## Notes

- The first refreshed focused run encountered the registry loader's concurrent-write fingerprint refusal while a peer was changing registry data. The same suite passed completely after the registry tree settled.
- The repository-wide locale scaffold check remains red on unrelated current drift: renta-profile missing keys, retired verification extras, IVA-wallet inter-locale gaps, and ledger extras. It reported no missing or extra S82 filter key.
- The broad naming batch remains red on sixteen peer-owned M303 casilla-fragment filename mismatches and three pre-existing IVA-stem prose findings tracked by later campaign steps. Its other fourteen tests passed.
- All four locale files acquired unrelated `confirm_supply_nature_help` additions during this step. Those peer hunks were preserved and excluded from S82 ownership.
- The plan checkbox remains open by explicit execution instruction. No compatibility alias, shim, tolerant field, commit, staging action, or audit artifact was added.
