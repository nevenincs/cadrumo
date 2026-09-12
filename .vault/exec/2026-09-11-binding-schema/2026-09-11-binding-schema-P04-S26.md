---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:394b4f6ef135f575d30b6080fc2764ee1eb419b571d7c543cd07891e0623d1ed'
step_id: 'S26'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Strip the fixed-width span segment from generated binding ids in the 57 modelos where the within-edition collision count is zero (3,164 ids), through the rename tool with within-edition uniqueness proof, rewriting every reference and regenerating export trees in the same run; the export generator's id rule emits page and slot names without spans from then on

## Scope

- `dev/registry/pipeline/_export_tree.py`
- `dev/registry/rename_formula_binding_identifiers.py`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/bindings/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/`

## Changes

- `M` `dev/registry/rename_formula_binding_identifiers.py`
- `A` `dev/registry/tests/test_binding_span_strip.py`
- `M` `dev/registry/edition_export_scenarios.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/*/bindings/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/131/revisions/*/bindings/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/*/bindings/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/720/revisions/*/bindings/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/application_links/0002-application-links.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/constructs/0005-constructs.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/application_links/0002-application-links.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/constructs/0005-constructs.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/verification_expectations/0002-verification-expectations.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/verification_expectations/0003-reconcile-when-present.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/verification_expectations/0002-verification-expectations.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/verification_expectations/0003-reconcile-when-present.toml`
- `D` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/verification_expectations/0001-verification-expectations.toml`
- `D` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/verification_expectations/0001-verification-expectations.toml`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_binding_span_strip.py dev/registry/tests/test_rename_edition_year_collapse.py dev/registry/tests/test_rename_family_identifier_collapse.py -n 0 -q --noconftest` -> `pass`
- `verify:` `load_modelo_directory` on modelos 369, 131, 360, 720, 200 -> `pass`
- `verify:` `uv run ty check dev/registry/rename_formula_binding_identifiers.py dev/registry/tests/test_binding_span_strip.py` -> `pass`
- `verify:` `just report-registry-edition-delta-status --lines --totals-only` -> `pass`

## Notes

Modelos 232, 353 and 390 are refused by the generated-export-tree guard and were
not applied. Probing the strip on an isolated copy of modelo 353 showed the
strip alone leaves every one of its 166 generated-tree binding references
dangling; `load_modelo_directory` returns OK on that state, so it does not gate
the hazard. The regeneration must land in the same change, and the owning
generator cannot run: the pipeline entry point fails at import because a
governed fact is not registered, and the core modelo enum cannot be iterated.
Modelo 714 is withheld from the pass entirely; its 128 within-edition collisions
need the generator's repetition index.

Test modules naming a stripped id are reported, never rewritten -- they belong to
their authors. Modelo 131's stripped ids are still named by three test modules
whose owner must move them.

The modelo 200 verification-expectation duplicate was not the subset it was
described as: the keyed row covered casilla DP200014B:00599, which the surviving
row did not. That casilla was unioned into the surviving row before the keyed row
was deleted, so no verification coverage was dropped.

A src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/identifier_evolutions/0001-replaced-regimen-simplificado-lorca-relabel.toml
A src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/identifier_evolutions/0001-retired-regimen-simplificado-reducciones.toml
