---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:26656903c52e5c9925211162315ab4538447d69dafc06cc981939eae955883a4'
step_id: 'S27'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Extend the identifier rename tool to every id-keyed schema family (parameters, export_layouts, deadline_windows, application_links, workbook_parity_refs, constructs, verification_expectations, dependency_classifications, extraction_profiles, filing_schedules, live_cross_references, bindings, formulas), stripping edition tokens per member under the signal's year rule, rewriting every reference in the same pass, refusing collisions, and applying per modelo with the family signal line before and after

## Scope

- `dev/registry/rename_formula_binding_identifiers.py`
- `dev/registry/analysis/edition_delta_status.py`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/`

## Changes

- `M` `dev/registry/rename_formula_binding_identifiers.py`
- `A` `dev/registry/tests/test_rename_family_identifier_collapse.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/036`
- `M` `src/cadrumo/_data/registry/aeat/modelos/038`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100`
- `M` `src/cadrumo/_data/registry/aeat/modelos/117`
- `M` `src/cadrumo/_data/registry/aeat/modelos/123`
- `M` `src/cadrumo/_data/registry/aeat/modelos/126`
- `M` `src/cadrumo/_data/registry/aeat/modelos/128`
- `M` `src/cadrumo/_data/registry/aeat/modelos/130`
- `M` `src/cadrumo/_data/registry/aeat/modelos/131`
- `M` `src/cadrumo/_data/registry/aeat/modelos/136`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151`
- `M` `src/cadrumo/_data/registry/aeat/modelos/165`
- `M` `src/cadrumo/_data/registry/aeat/modelos/180`
- `M` `src/cadrumo/_data/registry/aeat/modelos/181`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184`
- `M` `src/cadrumo/_data/registry/aeat/modelos/185`
- `M` `src/cadrumo/_data/registry/aeat/modelos/187`
- `M` `src/cadrumo/_data/registry/aeat/modelos/188`
- `M` `src/cadrumo/_data/registry/aeat/modelos/190`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193`
- `M` `src/cadrumo/_data/registry/aeat/modelos/194`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200`
- `M` `src/cadrumo/_data/registry/aeat/modelos/202`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210`
- `M` `src/cadrumo/_data/registry/aeat/modelos/216`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303`
- `M` `src/cadrumo/_data/registry/aeat/modelos/308`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322`
- `M` `src/cadrumo/_data/registry/aeat/modelos/341`
- `M` `src/cadrumo/_data/registry/aeat/modelos/345`
- `M` `src/cadrumo/_data/registry/aeat/modelos/349`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353`
- `M` `src/cadrumo/_data/registry/aeat/modelos/360`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390`
- `M` `src/cadrumo/_data/registry/aeat/modelos/490`
- `M` `src/cadrumo/_data/registry/aeat/modelos/604`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714`
- `M` `src/cadrumo/_data/registry/aeat/modelos/721`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763`
- `M` `src/cadrumo/locales/ca/modelo/schema/131.yml`
- `M` `src/cadrumo/locales/en/modelo/schema/131.yml`
- `M` `src/cadrumo/locales/es/modelo/schema/131.yml`
- `M` `src/cadrumo/locales/hu/modelo/schema/131.yml`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_rename_family_identifier_collapse.py -n 0` -> `pass`
- `verify:` `just report-registry-edition-delta-status --totals-only` -> `pass`
- `verify:` `just check-locales` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `fail`

## Notes

`publish-authority` exits 1 on a governed-fact citation failure in the untracked
file `src/cadrumo/_data/registry/aeat/facts/0092-modelo-rendering-declarations.toml`,
which this change did not create or touch; the authority artifact is therefore not
republished here. Two edition-keyed identifiers remain in modelo 200 revision 2024
(`modelo-200-2024-portal`, `modelo-200-2024-cuota-chain-verification`): each
edition already declares the token-free spelling as a separate member, so the
collapse is refused as a collision and the duplicate declarations need a decision.
The deadline window family is withheld from the rename entirely: its members are
identified by the typed filing year and period they state.
