---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a03935f0e16d2460402a82eefae927f977917d95ed92553014de46116338af76'
step_id: 'S64'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Translate the continuity-key locale entries that copy the Spanish source text, before the live pilot. The 303 dry run showed inherited rows resolving a predecessor's real translation where the full copy fell through to a continuity-key entry holding untranslated Spanish in ca, en and hu (84 casillas per 303 edition). A copied source string does not satisfy locale coverage, so this is a catalogue defect that inheritance exposes, not a migration error. Through the canonical locale workflow only, give each affected continuity key a real translation in every supported locale, grounded in the lineage's existing translations, and add a locale-coverage check that fails when a continuity-key entry equals its Spanish source in a non-Spanish locale unless it is classified as untranslatable. Proof: the round-trip gate's locale identity passes on the migrated 303 dry run; the new check fails on a planted copied entry.

## Scope

- `src/cadrumo/locales`

## Changes

- `M` `src/cadrumo/locales/ca/modelo/schema/100.yml` (582 continuity labels)
- `M` `src/cadrumo/locales/ca/modelo/schema/131.yml` (1 continuity label)
- `M` `src/cadrumo/locales/ca/modelo/schema/180.yml` (1 continuity label)
- `M` `src/cadrumo/locales/ca/modelo/schema/303.yml` (84 continuity labels)
- `M` `src/cadrumo/locales/en/modelo/schema/100.yml` (582 continuity labels)
- `M` `src/cadrumo/locales/en/modelo/schema/131.yml` (16 continuity labels)
- `M` `src/cadrumo/locales/en/modelo/schema/303.yml` (84 continuity labels)
- `M` `src/cadrumo/locales/hu/modelo/schema/100.yml` (582 continuity labels)
- `M` `src/cadrumo/locales/hu/modelo/schema/131.yml` (16 continuity labels)
- `M` `src/cadrumo/locales/hu/modelo/schema/303.yml` (84 continuity labels)
- `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` (loader alias plugin) -> `pass`
- `verify:` `pytest test_casilla_label_spanish_source_coverage.py` on `git archive f7e5d56096` plus overlaid shards -> `pass`
- `verify:` `ruff check`, `ruff format --check`, `ty check` on the test module -> `pass`

## Notes

Measurement (pre-change HEAD 8543517fe7). Stored entries equal to the Spanish source: 0 in every locale. The rendered Spanish came from unfilled (`null`) continuity labels, which `resolve_modelo_localization` resolves through Spanish. Unfilled labels with Spanish populated: ca 677, en 691, hu 691 (2,059). Per modelo: 100 582/582/582, 303 84/84/84, 131 1/16/16, 390 9/9/9, 180 1/0/0.

Translated: 2,032 through `dev.locales set-batch` (1,885 reused from a same-lineage occurrence key with identical Spanish; 117 derived from a same-lineage sibling differing only in embedded years, with Hungarian year suffixes re-harmonised (31 values); 30 authored in catalogue terminology). Four legitimate identicals are in the classified per-key allowlist: ca Matrícula, ca/en Total, ca NIF del perceptor.

Not done: modelo 390's 27 unfilled labels (9 lineages x 3 locales). They have no translation at any tier, and 390 is outside this Step's permitted surface. The new gate does not flag them, because it judges copies and stranded lineages, not lineages untranslated everywhere.

Environment: HEAD 8543517fe7 deletes `cadrumo.domain.calculations.registry.loader` (moved to `dev/registry/compiler/loader.py`) while `dev/locales/_registry_scanner.py` and many tests still import it, so `dev/locales` fails at collection. Gates were run with a scratch pytest plugin aliasing the module. With it, dev/locales reports 512 passed and 3 failed (`test_parity::test_codebase_to_locale_parity`, `test_audit::test_committed_catalogues_pass_production_audit`, `test_dynamic_prefix_registry_coverage::test_allowlist_entries_are_live_and_reasoned`). Those are key-set and namespace drifts present identically in es and independent of these value-only edits. The registry does not load on HEAD (missing `_data/registry/authority/authority.json`), hence the snapshot proof.

- The reviewer persona could not be launched. The orchestrating session reviewed the translations and the guard. Translations were written through `set-batch`, reused only where the same lineage has identical Spanish, and the only other catalogue change removed `label: null`. The allowlist is per key with a reason. The orchestrating session confirmed that the 10 touched catalogues parse. The registry does not load on the current tree (the signed `authority.json` is absent, and `dev.locales` still imports the relocated loader), so the label sweep and the honesty gates were proven on a `f7e5d56096` snapshot. Modelo 390's 27 labels are untranslated at every level and are left for 390's own work.
