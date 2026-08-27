---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:d5c342f12d70304328a3ba0231ea40f4adaac2c4138557aa7cb5b19b3bc40517'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# `registry-temporal-coverage` ledger

## Changes

- `S01` `T` `src/cadrumo/core/`
- `S01` `T` `src/cadrumo/domain/calculations/registry/_schema.py`
- `S01` `T` `src/cadrumo/domain/calculations/registry/_loader.py`
- `S01` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S02` `T` `src/cadrumo/domain/calculations/registry/_schema.py`
- `S02` `T` `src/cadrumo/domain/calculations/registry/_coverage.py`
- `S02` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S03` `T` `src/cadrumo/domain/calculations/registry/`
- `S03` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S04` `T` `src/cadrumo/domain/calculations/registry/_schema.py`
- `S04` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S04` `T` `src/cadrumo/domain/calculations/registry/`
- `S05` `T` `src/cadrumo/domain/calculations/registry/m303_orden_census_artefact.py`
- `S05` `T` `src/cadrumo/domain/calculations/registry/m303_orden_manifest.py`
- `S05` `T` `src/cadrumo/domain/calculations/registry/tests/test_m303_orden_census_artefact.py`
- `S06` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S06` `T` `dev/`
- `S07` `T` `src/cadrumo/domain/calculations/registry/_loader_cache.py`
- `S07` `T` `src/cadrumo/domain/calculations/registry/_loader_fingerprints.py`
- `S07` `T` `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
- `S07` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S08` `T` `src/cadrumo/domain/calculations/registry/ids.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/schema.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/loader.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/_validate_applicability_section.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/tests/test_applicability_fragment_family.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`
- `S09` `T` `dev/registry/authoring_migrate_applicability_fragments.py`
- `S09` `T` `src/cadrumo/_data/registry/aeat/modelos/`
- `S09` `T` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S09` `T` `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`
- `S13` `T` `src/cadrumo/domain/calculations/registry/_coverage.py`
- `S13` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S14` `T` `src/cadrumo/domain/calculations/registry/_coverage.py`
- `S14` `T` `src/cadrumo/domain/calculations/registry/_snapshot.py`
- `S14` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S21` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S21` `T` `.vault/audit/`
- `S22` `T` `dev/registry/analysis/modelo_embed_classification.py`
- `S22` `T` `dev/registry/analysis/modelo_embed_classification.toml`
- `S22` `T` `dev/registry/tests/test_modelo_specific_embed_classification.py`
- `S24` `T` `src/cadrumo/_data/registry/aeat/`
- `S24` `T` `src/cadrumo/domain/calculations/registry/`
- `S24` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S26` `T` `dev/`
- `S26` `T` `src/cadrumo/domain/calculations/registry/`
- `S26` `T` `.vault/audit/`
- `S27` `T` `dev/`
- `S27` `T` `dev/registry/_export_tree.py`
- `S27` `T` `dev/registry/mappings/`
- `S27` `T` `dev/registry/render_profiles/`
- `S27` `T` `src/cadrumo/`
- `S27` `T` `.vault/audit/`
- `S28` `T` `src/cadrumo/domain/calculations/registry/_formula_runtime_ops.py`
- `S28` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S29` `T` `src/cadrumo/domain/calculations/registry/loader.py`
- `S29` `T` `src/cadrumo/domain/calculations/registry/loader_cache.py`
- `S29` `T` `src/cadrumo/domain/calculations/registry/loader_fingerprints.py`
- `S33` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S35` `T` `src/cadrumo/domain/calculations/registry/_m303_orden_projection_models.py`
- `S35` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S36` `T` `src/cadrumo/domain/calculations/registry/_source_evidence_fingerprint.py`
- `S36` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S36` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S39` `T` `dev/quality/`
- `S39` `T` `src/cadrumo/`
- `S39` `T` `src/cadrumo/tests/`
- `S43` `T` `src/cadrumo/_data/registry/aeat/legal/modelo-038.toml`
- `S43` `T` `src/cadrumo/_data/registry/aeat/modelos/038/revisions/`
- `S43` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/`
- `S43` `T` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py`
- `S44` `T` `src/cadrumo/_data/registry/aeat/modelos/182/`
- `S44` `T` `src/cadrumo/_data/registry/aeat/legal/modelo-182.toml`
- `S44` `T` `src/cadrumo/domain/calculations/registry/tests/test_legal_review_authority_scope.py`
- `S45` `T` `src/cadrumo/_data/registry/aeat/modelos/187/`
- `S45` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S45` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_187/`
- `S45` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S46` `T` `src/cadrumo/_data/registry/aeat/modelos/188/`
- `S46` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S46` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/`
- `S46` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S47` `T` `src/cadrumo/_data/registry/aeat/modelos/194/`
- `S47` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S47` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/`
- `S47` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S48` `T` `src/cadrumo/_data/registry/aeat/modelos/220/`
- `S48` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S48` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/`
- `S48` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S49` `T` `src/cadrumo/_data/registry/aeat/modelos/721/`
- `S49` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S49` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_721/`
- `S49` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S50` `T` `src/cadrumo/_data/registry/aeat/modelos/763/`
- `S50` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S50` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/`
- `S50` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S51` `T` `src/cadrumo/_data/corpus/aeat_official/disenos_registro`
- `S51` `T` `src/cadrumo/_data/registry/aeat/modelos`
- `S51` `T` `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`
- `S52` `T` `src/cadrumo/domain/calculations/registry/_validate.py`
- `S52` `T` `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py`
- `S52` `T` `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `S52` `T` `src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py`
- `S53` `T` `src/cadrumo/_data/registry/aeat/modelos/200/`
- `S53` `T` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `S53` `T` `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`
- `S53` `T` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`

- `S37` `M` `src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`
- `S37` `M` `src/cadrumo/application/modelo/profile_binding.py`

- `S10` `M` `dev/quality/import_hygiene_scan.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/_validate_applicability_section.py`
- `S34` `M` `dev/quality/import_hygiene_scan.py`
- `S34` `M` `src/cadrumo/domain/calculations/registry/tests/__init__.py`

- `S55` `A` `src/cadrumo/application/registry/tests/test_exact_key_corpus_year_coverage.py`
