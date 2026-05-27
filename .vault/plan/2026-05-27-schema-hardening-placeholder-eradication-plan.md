---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-label-artifact-inventory]]'
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `schema-hardening` `placeholder-eradication` plan

### Phase `P01` - Placeholder inventory and normalization policy

Convert the advisory placeholder inventory into a source-grounded cleanup
policy before touching registry data.

- [x] `P01.S01` - Confirm unresolved casilla-label placeholder scope across all modelos and code locations; `src/aeat/_data/registry/aeat/modelos`, `src/aeat/domain/calculations/registry`.
- [x] `P01.S02` - Ground M100 2021 placeholder tokens against official 2021 dictionary files and neighboring annual revisions; `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_100`.
- [x] `P01.S03` - Record the exact mechanical normalization rules and blocked edge cases after first cleanup verification; `.vault/exec`.

### Phase `P02` - M100 2021 casilla label cleanup

Remove unresolved formatting placeholders from registry labels without
changing ids, sections, data types, legal refs, source refs, formulas,
bindings, or loader semantics.

- [x] `P02.S04` - Mechanically normalize every M100 2021 casilla label containing `{0}` or `{2}`; `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas`.
- [x] `P02.S05` - Rebaseline the generic label-artifact regression gate from the legacy count to zero; `src/aeat/domain/calculations/registry/test_label_artifacts.py`.
- [x] `P02.S06` - Verify M100 registry loading, label-artifact inventory, cross-revision drift, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.

### Phase `P03` - Hard-fail rollout

Promote the placeholder detector from advisory inventory to a registry
validation gate once the committed corpus is clean.

- [x] `P03.S07` - Add a generic hard validator for unresolved casilla label placeholders and wire it into registry-scope validation; `src/aeat/domain/calculations/registry`.
- [x] `P03.S08` - Add mutation tests proving any future `{name}`/`{number}` casilla-label placeholder raises `RegistryValidationError`; `src/aeat/domain/calculations/registry tests`.
- [x] `P03.S09` - Run path-scoped registry validation and commit the hard-fail gate with the cleanup record; `.vault/exec`.

### Phase `P04` - Empty revision eradication

Remove registry definitions that only record authority metadata without a
casilla payload, and make the zero-casilla shape impossible to reintroduce
through the normal registry validator.

- [x] `P04.S10` - Identify every committed modelo revision with zero casillas and no calculation payload; `151`, `714`, `721`.
- [x] `P04.S11` - Remove the empty registered modelo definitions while preserving legal/source catalogue authority and CLI refusal behavior; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P04.S12` - Add a generic revision validator and regression tests proving zero-casilla revisions fail validation; `src/aeat/domain/calculations/registry`.
