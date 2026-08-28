---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:22756991559f69838df05da24f53544aa203e3d9a5aa9e92b6c521e3064668f0'
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

- `S54` `M` `src/cadrumo/application/filing/_review.py`
- `S54` `M` `src/cadrumo/application/ledger/ratios.py`
- `S54` `M` `src/cadrumo/application/ledger/preflight.py`
- `S54` `M` `src/cadrumo/application/ledger/usage_ratio_repository.py`
- `S54` `M` `src/cadrumo/application/ledger/llm_classification.py`
- `S54` `M` `src/cadrumo/adapters/persistence/profile/usage_ratios.py`
- `S54` `M` `src/cadrumo/domain/transactions/_llm.py`
- `S54` `M` `src/cadrumo/domain/usage_ratios/_model.py`
- `S54` `M` `src/cadrumo/entrypoints/cli/_ledger.py`
- `S54` `M` `src/cadrumo/entrypoints/cli/_ledger_support.py`
- `S54` `M` `src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py`
- `S54` `M` `src/cadrumo/entrypoints/cli/_app_ledger_ratios_command_specs.py`
- `S54` `M` `src/cadrumo/locales/en/cli.yml`
- `S54` `M` `src/cadrumo/locales/es/cli.yml`
- `S54` `M` `src/cadrumo/locales/ca/cli.yml`
- `S54` `M` `src/cadrumo/locales/hu/cli.yml`

- `S21` `D` `src/cadrumo/domain/calculations/registry/validate_cross_revision_advisory.py`
- `S21` `M` `src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py`
- `S21` `M` `src/cadrumo/domain/calculations/registry/tests/test_public_api_boundaries.py`
- `S21` `M` `dev/registry/analysis/load_census_classification.py`
- `S21` `D` `docs/api/cadrumo.domain.calculations.registry.validate_cross_revision_advisory.rst`
- `S21` `M` `docs/api/cadrumo.domain.calculations.registry.rst`

- `S30` `M` `.vault/adr/2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr.md`

- `S41` `M` `src/cadrumo/application/_foreign_asset_thresholds.py`
- `S41` `M` `src/cadrumo/core/_foreign_asset_obligation.py`
- `S41` `M` `src/cadrumo/core/__init__.py`

- `S42` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/parameters/0001-parameters.toml`
- `S42` `M` `src/cadrumo/application/modelo/_art109_activity_income.py`
- `S42` `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `S42` `M` `src/cadrumo/domain/modelos/_dt12_reduccion.py`

- `S42` `M` `src/cadrumo/core/external_constants.py`
- `S42` `M` `src/cadrumo/application/modelo/_calculate_input.py`
- `S42` `M` `src/cadrumo/application/modelo/_dt12_antiquity_advisory.py`
- `S42` `M` `src/cadrumo/core/_rescate_type.py`

- `S39` `A` `dev/registry/analysis/modelo_branch_classification.py`
- `S39` `A` `dev/registry/analysis/modelo_branch_classification.toml`
- `S39` `A` `dev/registry/tests/test_modelo_branch_classification.py`

- `S38` `A` `dev/registry/analysis/regulatory_prose_parser_channel.py`
- `S38` `A` `dev/registry/analysis/regulatory_prose_parser_channel.toml`
- `S38` `A` `dev/registry/tests/test_regulatory_prose_parser_channel.py`

- `S25` `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `S25` `A` `src/cadrumo/domain/calculations/registry/tests/test_supported_filing_year_consumption_refusal.py`
- `S40` `M` `src/cadrumo/core/_amendment_kind_regime.py`

- `S12` `A` `src/cadrumo/domain/calculations/registry/validate_temporal_coherence.py`
- `S12` `A` `src/cadrumo/domain/calculations/registry/tests/test_temporal_coherence_advisories.py`

- `S11` `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `S11` `A` `src/cadrumo/domain/calculations/registry/tests/test_filing_bound_cell_advisories.py`

- `S18` `A` `dev/registry/analysis/coverage_residue_worklist.py`
- `S18` `A` `dev/registry/tests/test_coverage_residue_worklist.py`
- `S18` `A` `.vault/audit/2026-08-27-registry-temporal-coverage-coverage-residue-state-audit.md`

- `S15` `A` `dev/registry/retire_applicability_grade_markers.py`
- `S15` `A` `dev/registry/tests/test_applicability_grade_marker_retirement.py`
- `S15` `M` `src/cadrumo/_data/registry/aeat/modelos/`

- `S16` `A` `dev/registry/apply_revision_temporal_bounds.py`
- `S16` `A` `dev/registry/tests/test_revision_temporal_bounds_applier.py`

- `S23` `M` `src/cadrumo/domain/calculations/registry/inventory_bindings.py`

- `S40` `A` `dev/registry/derive_result_dispositions.py`
- `S40` `A` `dev/registry/tests/test_result_disposition_derivation.py`

- `S40` `A` `dev/registry/generate_result_disposition_fragments.py`

- `S25` `M` `src/cadrumo/application/filing/__init__.py`
- `S25` `A` `src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py`
- `S25` `M` `src/cadrumo/locales/en/application.yml`
- `S25` `M` `src/cadrumo/locales/es/application.yml`
- `S25` `M` `src/cadrumo/locales/ca/application.yml`
- `S25` `M` `src/cadrumo/locales/hu/application.yml`

## Notes

`W02.P05.S25` is NOT implemented, and the reason is a measured corpus fact
rather than a placement problem. The row asks the authority to refuse
production consumption for any filing year outside the supported-year
declaration. A guard was written at the authority snapshot boundary, landed,
and withdrawn from the working tree after it produced 36 refusals across the
registry suite and 8 in the Modelo 100 minimum-descendientes suites.

The measurement that should have preceded it: **37 of the 58 bundled modelos
ship revisions covering years the registry does not declare supported**, some
reaching back to 2003 (M156), 2012 (M145) and 2013 (M165); Modelo 100 itself
ships 2020 and 2021. The declaration carries 2022 to 2026. So a
supported-year refusal on any shared consumption path contradicts roughly two
thirds of the corpus, and the failures it produced were correct tests reading
revisions the registry genuinely ships.

That makes `S25` dependent on `W02.P05.S51`, which the plan does not record.
`S51` is the row that constrains unsupported claimed years, and until the
claimed-year set and the declared-year set agree, no refusal keyed on the
declaration can land without fighting the corpus. `S51` is itself blocked on
acquiring historical AEAT design artefacts, so the dependency is real and
external.

What survives for whoever picks `S25` up: the refusal shape is right (name the
year, name the declaration that would admit it) and the applicability rung must
stay readable, because an operator asking whether an out-of-scope year is due
is asking exactly the question the scheduling surface exists to answer. The
placement is the open question, and it cannot be settled before the claimed-year
contradiction is.

`W01.P03.S23` is partially complete, and most of its remainder is queued rather
than outstanding. Measured against the embed classification ledger: of the seven
regulatory data embeds, four are campaign-owned and four of the remaining rows
resolve as follows.

The applicability table is DONE for unowned trees. Only Modelos 303 and 390
still carry a Python `ModeloApplicabilityRule` literal, and both are held by the
export-fragment campaign, so they belong to `W03.P08.S19` rather than here. The
Lorca 2022 duplicate spellings the row names are likewise all in Modelo 303 and
orden-annual modules, so that duplication queues with them.

`inventory_bindings.py` is migrated in the half that was unambiguously an embed:
the `filing_year` pin is gone, so a later revision declaring an inventory
projection is an authoring change rather than a source edit. The Modelo 100 2025
revision already declares all three bindings with their own year and target
casilla, so the Python was duplicating the registry outright.

Its operation-to-casilla map was deliberately NOT retired, against the ledger's
classification. An operation names which figure it produces, so its destination
is what the operation MEANS rather than a value the law re-sets per year, and
retiring it would leave nothing checking that a binding declaring
`complete_acquisition_cost` targets the acquisition-cost box. A guard with no
replacement is worse than a duplicated declaration. That half needs
re-adjudication in the embed ledger before it moves.

`applicability_modelo202.py` remains outstanding: 146 lines whose migration
needs applicability fragments grounded in LIS art. 40.2 and 40.3 plus the
Spanish modality prose in all four locale catalogues. It is the one genuinely
unblocked piece of `S23` left.

`S23`'s last unblocked module, `applicability_modelo202.py`, turns out to need a
registry schema decision rather than authoring, and the measurement is worth
recording so nobody re-attempts it as a migration.

`ModeloApplicabilityRule` carries set-membership predicates only:
`applicable_entity_types`, `required_income_categories`,
`required_estimation_regimes`, `applicable_fiscal_residencies`,
`applicable_iva_regimes`, `required_payer_fact`, two prose reasons,
`cuota_bearing` and `legal_refs`. It has no numeric threshold, no conditional
branch and no multi-outcome vocabulary.

The Modelo 202 rule needs all three: a comparison against the INCN of the prior
twelve months, a branch, and three outcomes (art. 40.3 mandatory, art. 40.2
optional, incomplete). Expressing it would mean extending the fragment family,
which is a schema ruling of the same class as `W01.P03.S40`.

Two further facts narrow what a migration would even move. The threshold itself
is already grounded and correctly homed: `MODELO_202_ART_40_3_INCN_THRESHOLD_EUR`
sits in `core.external_constants` citing Ley 27/2014 art. 40.3, which
`aeat-registry-authority-flow` sanctions for a regulatory leaf constant. And the
classification ledger's stated destination for the Spanish modality prose --
the locale catalogues -- contradicts how the family actually works: the shipped
Modelo 202 applicability fragment carries its `applicable_reason` and
`not_applicable_reason` as Spanish prose inline. Whichever convention is right,
the two disagree today, and that is part of the same ruling.

`W01.P03.S42` closes on all four of its named items, two of them by a route the
row did not anticipate.

The art. 109 activity-income coefficient migrated as written: a grounded
`irpf.art_109_retained_income_exemption_ratio` parameter on the Modelo 130
revision, cross-checked in both the bundled BOE corpus and the AEAT
instructions, with the literal deleted and the consumer refusing rather than
defaulting when the parameter is absent.

The five DT 12a boundary years moved to `core.external_constants` beside their
sibling 40 per cent rate, each carrying the clause verified against the bundled
consolidated LIRPF, rather than into the registry. They are fixed once by the
2014 amendment and do not vary by filing year, so year-versioning them would
duplicate invariant data across six Modelo 100 revisions -- the pattern the
`registry-dated-validity` work retired for the category profiles.

The DT 12a advisory threshold was NOT migrated, and should not be. DT 12a fixes
no 20.000 euro figure; the only 20.000 euro amount in LIRPF is a vivienda
deduction base cap. The number is an advisory heuristic, and giving it
`legal_refs = ["ley-35-2006:dt-12"]` would manufacture a citation.

The finca tier coefficients needed no migration: `_resolve_tier_reduccion_rate`
already reads each tier rate from the Modelo 100 revision parameters and
overrides the module templates, and `_resolve_prior_rent_rebaja_threshold`,
`_resolve_ejercicio_amendment_year` and `_resolve_joven_tenant_age_range` do the
same for their values. The surviving module constants are documented reference
values that a shipped test pins against the registry, with unsupported
ejercicios failing closed rather than falling back to them. Verified live: tiers
50/60/70/90 resolve to 0.50/0.60/0.70/0.90 from the 2022, 2024 and 2025
revisions.

One correction landed alongside: every DT 12a site named the amending provision
as apartado 4, art. 1.86 of Ley 26/2014. The bundled consolidated LIRPF states
"Se anade el apartado 3 por el art. 1.85". Corrected across the legal catalogue
and seven source and test modules.

`W01.P03.S40` names three per-modelo tables resident in `core`. Measured, they
resolve into one that needs no migration and two blocked on the same missing
registry vocabulary.

**Obligation-scope prose: nothing to migrate.** `UNMODELED_OBLIGATIONS` is
empty -- every recognized AEAT obligation is now registry-modelled. The prose
around it documents a live extensible mechanism, carries an explicit recorded
decision that the emptiness is deliberate rather than an oversight, and warns
against deleting the consuming branch as dead code. It describes machinery, not
regulatory data, and it belongs where it is.

**Result-disposition table: blocked.** The table pins each modelo's final result
casilla as a design-record number (M303 71, M130 19, M131 15, M111 30, M115 05,
M123 14, plus M200 and M202). The registry declares casillas by semantic role in
a different id space, and the role naming is not consistent enough to derive
from: Modelo 303 says `iva_resultado_autoliquidacion`, Modelo 130
`irpf_pf_resultado_final`, Modelo 131 `irpf_pf_modulos_resultado_declaracion`,
while Modelos 111, 115 and 123 carry only
`resultado_anteriores_autoliquidaciones`, which names the PRIOR filing's result
rather than this one's. The registry does not mark "this is the modelo's final
result casilla" as a first-class fact, so any deriver would encode the
modelo-to-role mapping in Python -- the transcription the row is trying to
remove.

**Rectificativa effective dates: blocked, same class.** Recorded earlier: the
registry does not declare rectificativa adoption as a first-class fact either,
and is inferable only from three unrelated incidental spellings.

Both blocked items want the same thing: a registry vocabulary for declaring a
per-revision fact about the modelo itself, rather than one inferable from how
something happens to be spelled. That is one schema ruling, and it also settles
the threshold-and-branch vocabulary `W01.P03.S23` needs for the Modelo 202
modality rule.

Refinement on the `S40` result-disposition finding, having read the table rather
than its constant names: it is not a casilla-id map. Each entry carries the
result casilla ids AND the disposition semantics -- what a negative result and a
zero result MEAN for that modelo (Modelo 303 negative is `COMPENSACION` and zero
is `NEGATIVA`, and the others differ). Several modelos declare more than one
result casilla, Modelo 123 and Modelo 202 among them.

That makes the migration a new revision-scoped fragment family in the shape of
`applicability` -- schema model, loader support, section validation, authored
TOML for roughly ten modelos each needing the legal basis for its own
disposition mapping -- plus a core-to-application inversion, because `core`
cannot read the registry that is built on it. It is the largest single piece of
work left in this campaign, not a transcription.

Sized here so the next attempt starts from the real shape. The same fragment
family would carry the rectificativa adoption fact `S40` also needs, and the
threshold-and-branch vocabulary `S23` needs for the Modelo 202 modality rule, so
one design covers all three.

Final confirmation on the `S40` result-disposition table: it declares ZERO
`legal_refs`. Its grounding is a module comment saying the spec is "grounded in
each bundled diseno's 'Tipo de declaracion' note" plus a short comment per
entry. That is precisely the defect the row names for the rectificativa dates --
grounding carried by a comment rather than a reference -- so it applies to two
of the row's three items, not one.

The consequence for whoever migrates it: under `aeat-calculation-grounding`
every entry must declare the provision that establishes it, with a `corpus_ref`
resolving to real AEAT text. That means verifying the "Tipo de declaracion" note
in roughly ten bundled disenos and authoring a citation per modelo, on top of
the fragment family itself. The values are believed correct and are exercised in
production; what they lack is the citation the registry would require of them.

CORRECTION to the note above, which overstated the `S40` result-disposition
blocker. It claimed the migration needs per-modelo grounding research. It does
not.

Every modelo in the disposition table already has enrolled diseno sources in the
legal catalogue -- between three and eighteen entries each for Modelos 303, 130,
131, 111, 115, 123, 200, 202 and 210. And the bundled diseno corpus carries the
grounding text directly: thirty files under `modelo_303` mention "Tipo de
declaracion", and the note states the vocabulary verbatim -- "El tipo de
declaracion puede ser: C (solicitud de compensacion) D (devolucion) G (cuenta
corriente tributaria-ingreso) I (ingreso) N (sin actividad/resultado...)" --
which is exactly what the core table encodes. Modelos 130 and 111 carry the same
note in their own disenos.

So the grounding is bundled, enrolled and quotable. What remains is engineering
rather than research: a revision-scoped fragment family in the shape of
`applicability` (schema model, loader support, section validation), authored TOML
per modelo citing its own diseno source with the note as `required_text`, and a
core-to-application inversion because `core` cannot read the registry.

Recorded as a correction rather than an edit to the earlier note, so the
overstatement and its refutation both stay visible. A blocker claim that turns
out to be false is worth more to the next reader than a tidy one.

MEASURED COST of the fragment family `S23` and `S40` both need, so the next
attempt starts from the number rather than an estimate.

Adding a collection field to `ModeloRevision` is not a local change. The schema
derives its family set from the annotations themselves:
`REVISION_COLLECTION_SHAPED_FIELDS` is computed from the type, and
`REVISION_SCHEMA_FAMILY_FIELDS` from the `SCHEMA_FAMILY` markers, with the
stated contract "one disposition row per member, always, so a family nobody has
built is a row saying so rather than an absence". A contributor cannot opt out:
appearing there is a consequence of the type they wrote.

The corpus carries 19 schema families across 128 revisions. A twentieth family
therefore costs **128 new per-revision disposition rows**, before any of its
actual data is authored. On top of that: the schema model, loader support,
section validation, the roughly ten modelos of real disposition data with their
diseno citations, and the core-to-application inversion because `core` cannot
read the registry built on it.

This is by design and the design is right -- it is what stops a family being
added and quietly left empty everywhere. But it means the migration is a
corpus-wide change rather than a module-sized one, and it should be planned as
its own campaign row with that number in front of it rather than folded into
`S23` or `S40` as if it were a transcription.

The grounding remains available and quotable, as the correction above records.
Nothing here is blocked on evidence; it is blocked on scope.

FAILURE MODE of the family addition, measured rather than assumed, because it
determines how the change must be sequenced.

`RevisionCoverageManifest._rows_cover_every_enrolled_family_once` RAISES
`RegistryValidationError` when the manifest rows do not cover every enrolled
family exactly once. Enrolment is automatic from the field's own type. So the
moment a twentieth collection field lands on `ModeloRevision`, all 128 revisions
fail their coverage manifest until each carries a disposition row for it.

Registry validation is all-or-nothing: one revision's refusal takes the whole
authority down, and with it every consumer. On a shared worktree with other
campaigns in flight, a half-applied family addition therefore stops the registry
loading for everyone, not just for the author.

The change is consequently atomic-or-broken: the field, the loader support, the
section validation and all 128 disposition rows must land in one commit. That is
achievable -- the rows are mechanical and a one-shot in the shape of
`retire_applicability_grade_markers` would generate them -- but it is not
something to begin without the whole sequence prepared, and not while peers hold
other trees.

So the blocker on `S23` and `S40` is neither evidence nor difficulty. It is that
the change is corpus-wide and atomic, and it needs to be scheduled as such.

SECOND CORRECTION, retracting the failure-mode note above. That note claimed a
new schema family costs 128 authored disposition rows and is atomic-or-broken.
Both halves are wrong.

`build_revision_coverage_manifest` states it "reads the revision and nothing
else" and builds `rows=tuple(_schema_family_row(family, revision) for family in
sorted(REVISION_SCHEMA_FAMILY_FIELDS))`. The rows are DERIVED, not authored. A
new family therefore costs zero authored rows: every revision gets its row
automatically, and an empty family lands as `blocked_pending_evidence`, which
the authorizing ADR names as the intended fail-closed default and a visible
worklist entry rather than a defect.

`_rows_cover_every_enrolled_family_once` does raise, but only if the rows fail
to cover the families exactly once -- which the derivation guarantees by
construction. It cannot fire from adding a family. And `fully_resolved` has no
consumer in the grade machinery, so unresolved rows report rather than gate.

What the family actually costs is ordinary engineering: the schema model and
field, loader support, section validation, the roughly ten modelos of real
disposition data with their diseno citations, and the core-to-application
inversion. Hours of work, not a corpus-wide atomic commit.

Recorded as a retraction rather than an edit because the overstatement is the
more useful artefact: four separate blocker claims in this campaign turned out
to be false on inspection, always in the direction of over-caution, and always
discoverable in minutes by reading the code that was said to block. A reader who
notices that pattern will trust the remaining blockers less and check them,
which is the correct response.

THIRD AND FINAL WORD on the `S23`/`S40` family cost, this time established by
EXECUTION rather than by reading, which is why it differs from both notes above.

The field was added to `ModeloRevision` and the registry was loaded. It loaded
clean -- 58 modelos, 20 families -- and the coverage row derived itself as
`blocked_pending_evidence` exactly as the second correction predicted. Zero
authored rows. So the retraction above was right about the coverage manifest.

But running the schema gates found the real gate, which neither note had:

    modelo 130 revision 2019-y-siguientes claims 'filing' authority grade while
    ['result_dispositions'] remain blocked pending evidence. The filing rung
    asserts every enrolled family is resolved: populate each one, or declare it
    not applicable with a reason and citations.

The constraint is the AUTHORITY-GRADE check, not the coverage-manifest
validator. Every filing-grade revision in the corpus -- 68 of the 128 -- fails
the moment a twentieth family is enrolled, until each either populates it or
declares it not applicable WITH a reason and citations. The not-applicable route
is authoring, not generation: a reason and citations cannot be produced
mechanically.

So the original instinct was right in substance and wrong in mechanism, and the
two corrections were right about the mechanism they examined and wrong about the
consequence. The change was reverted; the registry is back to 19 families and
loads clean.

The honest cost for whoever schedules this: 68 filing-grade revisions each
needing a populated declaration or an authored not-applicable reason, landing
together with the schema, loader and validation in one commit, because the tree
is unusable in between. That is a campaign row of its own, and it is why `S23`
and `S40` cannot close inside another row.

Why the `S23`/`S40` family cannot be attempted from a session sharing this
worktree, stated from observed behaviour rather than policy.

During this campaign's execution, uncommitted working-tree changes were swept
into peer commits at least four times: the filing-year threading, the corpus
year-coverage gate, the cross-revision advisory retirement, and the
supported-year consumption guard. The last is the instructive one. It landed as
`7829338af1` while its blast radius was still being measured, produced 36
refusals across the registry suite and 8 more in the Modelo 100 suites, and
needed `d287abbe0a` to revert it.

The family addition must land as one commit -- schema, loader, validation, and
all 68 filing-grade revisions carrying either a populated declaration or an
authored not-applicable reason -- because the authority-grade gate fails every
filing-grade revision in between. A sweep that commits half of it takes the
registry down for every session, and registry validation is all-or-nothing.

So the constraint is not the size of the work. It is that a multi-file atomic
change cannot be staged safely in a tree where another process commits the
working directory. Whoever schedules it should hold the tree, or work in an
isolated worktree, and land it in a single commit.

FINAL SIZING of the `S23`/`S40` family, derived from the corpus.

Of the 128 revisions, 68 claim filing grade and so must resolve every enrolled
family. They split cleanly on whether they declare formulas:

- **14 informative revisions** declare no formulas and settle no figure --
  Modelos 145, 165, 184 and their siblings. For these, "not applicable: an
  informative declaration settles no cuota, so no Tipo de declaracion result
  disposition exists" is an honest reason, and it is derivable rather than
  templated.
- **54 revisions declare formulas** and therefore settle a figure. Only about
  ten of them appear in the `core` disposition table. The other 44 would be
  demoted out of filing grade the moment the family enrols, because
  `blocked_pending_evidence` is exactly what the filing rung refuses.

So the authoring cost is not the ten entries the `core` table holds. It is 54
result-disposition declarations, each needing its own modelo's "Tipo de
declaracion" note read out of its own diseno de registro and cited, plus 14
derivable not-applicable declarations.

That is the honest size, and it is why this belongs in its own campaign with its
own research pass rather than inside `S23` or `S40`. The grounding is available
for every one of them -- the disenos are bundled and enrolled -- but availability
is not the same as having been read.

BREAKTHROUGH on the `S23`/`S40` family, which changes it from speculative to
schedulable. The authoring cost was the blocker: 54 filing-grade revisions each
needing a result-disposition mapping read out of its own diseno. That reading is
now mechanical and proved.

The diseno states the admissible "Tipo de declaracion" letters verbatim, and the
letters ARE the disposition: `ResultDisposition` members carry the AEAT codes
themselves (C compensacion, B resultado a deducir, D devolucion, N negativa).
So the mapping is read, not transcribed, on the letters' own precedence -- C,
else B, else D, else N.

`dev/registry/derive_result_dispositions.py` implements it and reproduces ALL
NINE mappings the hand-authored `core` table carries, independently, with zero
divergence. That agreement is the whole evidence that it reads what the table's
author read.

Coverage over the 68 filing-grade revisions: 38 derive a mapping from their
diseno's code list; the remaining 30 belong to fifteen modelos -- 145, 165, 180,
184, 190, 193, 232, 296, 322, 347, 349, 360, 369, 390, 720 -- whose disenos
never mention the field across 105 real corpus files between them. Those are the
informative declarations, and the measured absence is what makes `not
applicable` an honest declaration for them rather than a shrug.

The loader needs no wiring: `_compute_revision_section_fields` is "derived from
the schema so a new section field is section-classified automatically". The
schema addition was tested live and loads clean at 20 families.

What remains for whoever schedules the commit: the schema model and field, the
generated declarations for all 68 revisions, and the core-to-application
inversion, landing together. Every input is now derived and gated.

The `S23`/`S40` family is blocked on `W03.P08.S19`, and therefore on the
export-fragment campaign's `S84`. This dependency is not recorded on the plan,
and it is the third such omission this campaign has surfaced.

The chain is short and measured. The authority-grade gate requires EVERY
filing-grade revision to resolve every enrolled family. There are 68 of them.
Ten sit in campaign-owned trees: Modelo 303 carries six filing-grade revisions
(2022, 2023, 2024-desde-09-y-3t, 2024-hasta-08-y-2t, 2025, 2026-y-siguientes)
and Modelo 390 four (2022 through 2025). So enrolling the family requires
writing declarations into trees the export-fragment campaign holds, which is
precisely what `S19` exists to do and precisely what it is blocked on.

The generator therefore renders 58 of the 68 -- 32 with a mapping derived from
their diseno, 26 declared not applicable on measured absence -- and skips the
ten owned ones rather than writing into a held tree. Nothing was applied; the
registry tree is untouched.

What this leaves ready for the day `S84` lands: the derivation, proved against
all nine hand-authored mappings; the generator, covering 58 revisions now and
the remaining ten the moment the trees are released; and the measured knowledge
that the loader needs no wiring and the schema addition loads clean. The
remaining work is the schema model and field, the generated declarations, and
the core-to-application inversion, in one commit.

One scope decision is recorded in the generator itself: the fragment declares
the disposition SEMANTICS only, not which casilla holds the result. The casilla
identification is not derivable -- the semantic roles disagree across modelos --
and deriving it would reintroduce the modelo-to-role transcription this
migration exists to remove.

`W02.P05.S51` is COMPLETE, and was completed by peer work during this campaign
rather than being blocked on external acquisition as this ledger earlier
recorded. Verified against all three of the row's own conditions.

The whole-tree claimed-year layout-design gate passes: ten tests green in
`test_layout_design_applies_to_claimed_years.py`, with no allowlist, no xfail
and no skip anywhere in the module, and its own anti-tautology proof
(`test_a_genuine_presentation_span_violation_is_still_detected`) passing
alongside.

Nothing was backdated. Every one of the eleven named modelos plus Modelo 180
carries fully hash-pinned record designs -- 35 designs, 35 with a `sha256`, each
with a real sede.agenciatributaria.gob.es source URL, a `retrieved_at` stamp and
`applies_from`/`applies_to` bounds. The historical eras the row asked for are
there: Modelo 180 back to 2000, Modelo 309 to 2004, Modelo 341 to 2005, Modelo
576 to 2008, Modelos 181 and 308 to 2009. Several carry a `retrieved_at` of
2026-08-25, which is this campaign acquiring them.

Modelo 180 ejercicio 2022 is adjudicated: the modelo carries a bounded
`2019-2022` revision closing 2022-12-31 and a `2023-y-siguientes` successor, so
the ejercicio resolves to exactly one revision and the presentation axis is
settled.

The one failure in the neighbouring catalogue suite --
`executable_parity_evidence` coverage gaps on Modelos 714 and 200 -- is a
different axis and a different blocker; Modelo 714 waits on a wealth-asset
register that does not exist yet.

Note for `W02.P05.S25`, which this ledger recorded as depending on `S51`: that
dependency is now discharged, but `S25` is NOT thereby unblocked. Its own
blocker is the separate finding that 37 of the 58 bundled modelos ship revisions
for years the supported-year declaration does not carry. `S51` constrained
claimed-year LAYOUT coverage; it did not reconcile the declared support window
with the shipped revision set.

`W02.P05.S25` is COMPLETE, and the earlier note recording it as blocked on
`S51` and on the year-set contradiction was wrong. Both claims are retracted.

The first attempt placed the refusal on `ValidatedRegistryAuthority.snapshot`,
which serves structural inspection as well as production consumption. It
produced 36 refusals across the registry suite and 8 more in the Modelo 100
suites, was reverted, and the conclusion drawn was that the corpus itself made
the row impossible: 37 of the 58 bundled modelos ship revisions for years the
declaration does not carry.

That conclusion conflated the shared accessor with the boundary the row names.
The row says production calculation and filing CONSUMPTION. Measured with an
out-of-repo pytest plugin wrapping `build_draft` across the whole filing suite,
every call used a declared year -- 2023 once, 2024 eleven times, 2025 five
times, 2026 sixty-seven times. Nothing that inspects a historical revision
passes through that boundary.

So the guard went there instead. With it in place the filing suite reports 41
failed and 495 passed, byte-identical to the same suite measured before the
guard existed, and zero failures cite it. It is inert for every existing path
and refuses only a filing built for an undeclared year.

Five proofs cover it: every declared year admitted (so a guard refusing
everything cannot pass), the year below and the year above the window both
refused, the refusal naming the years it would accept, and -- the one that
encodes the earlier mistake -- Modelo 100's 2020 and 2021 revisions still
loading and inspecting with their casillas intact, proving the guard governs
filing rather than reading.

RETRACTION: `W02.P05.S51` was closed prematurely and has been REOPENED. The
closure note above verified the row's stated gate condition and stopped there;
the row's substance has a hole that a different gate catches.

What the closure got right: the whole-tree claimed-year layout-design gate does
pass, with its bite proof and no exemptions, and 35 record designs across the
named modelos are sha256-pinned with real AEAT URLs. None of that is withdrawn.

What it missed: `test_catalogue_verification.py::test_committed_registry_tree_has_required_model_law_coverage`
fails on `modelo 165 revision 2023-2025: layout_authority coverage gap`, and
Modelo 165 is named in `S51`'s own list. The modelo ships FOUR revisions --
2013-2015, 2016-2022, 2023-2025, 2026-y-siguientes -- and only THREE record
designs, whose windows run 2013-01-01..2015-12-31, 2016-01-01..2022-12-31 and
2026-01-01 onward. Ejercicios 2023, 2024 and 2025 are uncovered.

A false lead worth recording, because the next reader will hit it too. The
bundled file `01-165-diseno-de-registro-actualizado-en-2023.pdf` looks like the
missing artefact and is enrolled as `aeat-dr-165-2026` with
`applies_from = 2026-01-01`, which reads like a three-year mis-dating. It is
not: page 1 of the document states "Ejercicio 2026". The filename records when
AEAT last updated the web page, not the ejercicio the design governs. The
enrolment is correct and must not be re-dated.

So the gap is real and the remedy is the row's own first branch: acquire and
hash-pin the Modelo 165 design for ejercicios 2023-2025. Widening the
2016-2022 window to reach 2025 is barred -- `aeat-calculation-grounding` names
widening a window to admit a filing year as the exact act that fabricates a
citation.

The row's alternative branch, constraining the claimed years, is available and
does not need AEAT: the 2023-2025 revision could be withdrawn or bounded until
its design exists. That is an operator ruling about whether the product claims
those ejercicios, not something to decide inside a cleanup pass.

Separately measured while here: the audit's other channel,
`executable_parity_gaps`, carries 764 entries across many modelos, but
`RegistryCoverageAudit.ok` is `not self.required_gate_failures`, so those are
advisory and fail nothing. The earlier note naming Modelos 714 and 200 as the
blocker was reading a truncated output; the single blocking entry is Modelo 165.

### Modelo 308 ejercicio 2011 AD-HOC: adjudicated irreducible, not a defect

The residue cell refusing `modelo 308, 2011, AD-HOC` between revisions
`2009-2011-junio` and `2011-julio-2015` is CORRECT behaviour, and the queue
item's proposed remedy -- "constrain the overlapping selector" -- would have
been fabrication. Both revisions genuinely govern parts of ejercicio 2011.

Grounding, verified against the bundled consolidated corpus rather than the
registry's own `required_text`: `orden-eha-1033-2011.html` states "La presente
Orden entrara en vigor el dia 1 de julio de 2011" verbatim, and the legal
catalogue entry `orden-eha-1033-2011:disposicion-final-unica` carries
`effective_from = 2011-07-01`, matching the revision's `valid_from`
independently of the revision's own claim. The mid-year boundary is AEAT's.

The discriminator is the PERIOD axis, and the corpus makes it visible. Five
modelos split mid-year with co-claimants: 303 (2024), 308 (2011), 369 (2021),
490 (2022) and 763 (2018). Only 308 refuses, because only 308 declares the
same period token -- `AD-HOC` -- on both sides. Everywhere else the halves
carry disjoint period sets (`1T` vs `2T-4T`, `1T-3T` vs `4T`, the three OSS
schemes), so the period names the design without a date. `AD-HOC` has no
sub-year granularity, so neither year nor period can discriminate; only a date
can, and `select_revision(..., on=...)` resolves each half correctly.

A date-aware coverage probe was measured and REJECTED. Passing a date drawn
from each revision's own window flips exactly 2 cells to validated -- the M308
pair -- and reproduces all 1,718 others. It was not taken: a date drawn from
the revision's own window satisfies the window predicate by construction, so it
would weaken the window axis to near-tautology across all 1,718 cells to clear
two. Trading a strong check for a weak one to clear a residue cell is the
inverse of what the residue exists to surface.

Landed instead: `src/cadrumo/application/registry/tests/`
`test_irreducible_year_only_selection_refusals.py`, holding every year-only
refusal to its justification -- co-claimants overlapping on period, windows
disjoint and breaking inside the refused year, and the later half grounded in a
legal entry whose own `effective_from` falls on that boundary. Grounding is
read from the legal catalogue, never from the revision that claims it, so a
revision cannot vouch for its own date.

No tallies and no hardcoded modelo: a new grounded mid-year AD-HOC split passes
untouched, an ungrounded one fails. Two proofs beyond the positive case -- an
anti-tautology proof that a date resolves each refused coordinate to a distinct
revision (so "refuses and is grounded" cannot be satisfied by a corpus no date
can resolve either), and a discrimination proof that period-separated splits
resolve without a date, so the rule is not a rubber stamp licensing any overlap.

Gate proven to bite by runtime monkeypatch from OUTSIDE the repo (nothing under
`src/` edited, so a peer sweep cannot commit the mutation): moving every legal
`effective_from` reds the grounding test with `modelo 308: revision
2011-julio-2015 opens on 2011-07-01 ... but no orden it cites carries that
effective_from`. 5 passed clean; 1 failed under the mutation.

The residue cell stays refused. It is now a documented, grounded and tested
fact rather than an unexplained entry -- the coverage matrix's `(year, period)`
coordinate is coarser than the law it measures, for exactly one boundary AEAT
published.

### Red-gate sweep of `dev/`: five reds, one mine

Ran `dev/tests`, `dev/registry/tests` and `dev/quality` (430 passed, 5 failed).
Every failure was re-run SEQUENTIALLY before triage, per `aeat-local-execution`
-- and that step changed the verdict on one of them.

`test_registry_conformance_cli.py::test_report_text_renders_provenance_counts_`
`and_degraded_absence` is NOT a defect. Under xdist it failed asserting
`construct_evidence_rows=425`; run with `-n0` it passes. Verified directly:
the CLI renders 425 and the fixture computes 425, identical. The pytest output
elided the middle of the row line, which made a matching value look absent. A
parallel-run artefact, of exactly the class the rule anticipates.

`test_test_inventory.py::test_central_harness_has_no_owner_specific_behavior_`
`modules` was genuinely red and is FIXED.
`src/cadrumo/tests/test_canonical_decimal_string_uniqueness.py` declared
`hex_domain` but imported `adapters.inbound.financial` at runtime to assert the
package does not alias `canonical_decimal`. Relabelling the marker would NOT
have helped: the gate's else-branch flags any central-harness test exercising a
production owner without assertion-local structural evidence, so a marker swap
moves the violation rather than removing it.

The invariant is live -- that `__init__.py` does re-export from `.providers` --
so it was kept and made structural: the assertion now parses the package
`__init__.py` and checks the name is not bound. That is the honest thing to
inspect, since the claim is about what the namespace DECLARES, and an alias
reintroduced behind a failing import would still be a reintroduced alias.

Five anti-tautology proofs were added, one per route by which the name could
come back -- plain import, aliased import, assignment, `__all__` entry, def --
plus a discrimination proof that an unrelated namespace does not fire. Without
them an AST walker blind to one form would pass vacuously. 9 passed; the gate
is green.

Not mine, left alone with their owners named:
`test_export_tree.py::test_renderer_module_has_no_old_tree_or_approximate_`
`admission_surface` and `test_generated_export_trees.py[m184-2023-2024]` belong
to the export-fragment campaign. `test_import_hygiene_gate.py::test_production_`
`family1_violations_do_not_exceed_baseline_count` (116 cross-package private
imports against a hard-zero baseline) belongs to
`2026-07-01-import-centralization-plan`.

The `src/cadrumo` half of this sweep is NOT yet done -- only `dev/` was
covered. A full `src/cadrumo` run is in flight; its failures still need the
same sequential re-run before any of them is called a defect.

### Modelo 165 2023-2025 re-verified by execution: blocked, and the tempting fix is wrong

The earlier "blocked on an external artefact" claim was re-tested rather than
accepted, per this campaign's own rule that six such claims were made and all
six were false. It survives, and is now measured rather than asserted.

First check -- is the artefact already present but unenrolled? No. Modelo 165
ships exactly three corpus PDFs and exactly three enrolled record designs, and
they map one-to-one: `02-...orden-hap-2455-2013` to `aeat-dr-165-2013-2015`,
`03-...orden-hfp-1822-2016` to `aeat-dr-165-2016-2022`, and
`01-...actualizado-en-2023` to `aeat-dr-165-2026` (its page 1 states
"Ejercicio 2026"). Nothing is sitting unenrolled.

Second check produced a real hypothesis and then destroyed it, which is the
part worth recording. The `2023-2025` revision declares
`authority_grade = "applicability"` while both neighbours declare `filing`, and
all three cite the SAME orden (`orden-hap-2455-2013:art-1`) -- so the split is
not orden-driven. That looks exactly like a gate defect:
`_model_law_coverage_findings` in
`domain/calculations/registry/coverage.py:496` iterates every
`REQUIRED_COVERAGE_TIERS` entry regardless of `revision.authority_grade`, while
the sibling `parity_gaps` line right beside it IS scoped (`and
revision.formulas`). The code plainly knows how to scope a finding to what a
revision claims, and the required-gate path does not.

Measured before changing anything, and the measurement REFUTED it. Layout
authority is not a filing-only concern in this corpus: applicability-grade
coordinates are 730 satisfied against 3 gapped, and the 3 are all Modelo 165
2023-2025. Calculation grade is 103 satisfied, 0 gapped; filing grade 884
satisfied, 0 gapped. Fifty-three of the fifty-four applicability-grade
revisions carry a record design.

So exempting applicability grade would not correct an over-strict gate. It
would silence one genuine missing artefact AND drop the check from 54 revisions
that currently pass it, so a future applicability revision could ship with no
design and nothing would say so. That is weakening a gate to clear a single
cell -- the same trade refused for the Modelo 308 date probe, arrived at from
the opposite direction. Do not make this gate grade-aware to close this row.

Standing conclusion, unchanged but now evidenced twice: AEAT's Modelo 165
record design for ejercicios 2023-2025 is genuinely absent from the corpus. The
remedies remain acquiring and hash-pinning it, or an operator ruling to
withdraw or bound the 2023-2025 revision. Widening the 2016-2022 window stays
barred by `aeat-calculation-grounding`.

### Import-time configuration guards converted to test-time fixtures

`test_project_test_control_modules_do_not_execute_control_flow_at_import_time`
was red on five modules -- `dev/corpus/tests/test_extraction_sidecar_freshness`,
`dev/identity/tests/test_identifier_namespace_enrollment_gate`, and three under
`dev/packaging/tests`. It had not been seen earlier because the tick-4 sweep ran
with `-x` and stopped after five failures before reaching it.

This was a genuine gate-versus-gate overlap, not sloppiness. Commit
`9fadfdfda6 fix(dev): point three packaging gates back at the repository root`
ADDED those guards to fix a real bug: after a relocation, `parents[N]` silently
retargeted and the gates scanned `dev/` or a directory above the repository.
Each guard raised at import if the computed root was not real.

The tempting fix was to wrap the guard in a helper and call it from a
module-level assignment. The gate walks only `tree.body` and permits `Assign`,
so that passes the matcher while still running the control flow at import --
which is precisely the "hide the construct from one gate's matcher" resolution
`aeat-quality-gates` forbids. Rejected on that ground.

Taken instead, following the gate's stated intent ("keep collection import
side-effect free"): each guard became a module-scoped autouse fixture asserting
the same condition. The protection is unchanged in strength but now fails a
named test with its message instead of breaking collection, which is the more
actionable failure -- a collection error reports a broken module rather than
which gate lost its root.

Checked before converting: none of the five resolves the root at COLLECTION
time. No `parametrize` in any of them, so there is no path where a wrong root
yields zero cases and the fixture never runs. Had one existed, the conversion
would have silently weakened the guard.

`dev/tests/test_test_inventory.py` now passes 47/47, up from 46 passed 1 failed.

The five modules still carry PRE-EXISTING content failures, unrelated to this
change and not caused by it: `parents[3]` plainly resolves to the repository
root here, so the old import-time guard passed and those tests already ran and
already failed the same way. None of the failures is the root assertion. They
are 33 stale extraction sidecars whose declared xlsx sources are absent from the
committed tree (the corpus tree is CLEAN in git, so this is long-standing
acquisition debt rather than a peer's in-flight edit), corpus PDFs and
record-design workbooks without sidecars, and unadjudicated identifier-named
fields. The last belongs to `2026-08-07-canonical-identifiers-plan`; the sidecar
set is corpus-acquisition work outside this queue.

Peer sweep, again: tick 4's work was committed by a peer as `4cd0abf4c9 test:
count every name a module binds when proving decimal string uniqueness`, taking
both the canonical-decimal fix and the irreducible-refusal gate. Only the
subsequent `pairwise`/format polish remains uncommitted.

### src/cadrumo sweep: 475 reproducible failures, one root cause worth 80

The sweep capture was botched and then salvaged. The first launch combined
`nohup ... &` with the harness's own backgrounding, so the wrapper exited while
the process survived; the relaunch truncated the same log path and BOTH runs
wrote into it. Two full suites therefore ran concurrently on a share this repo
documents as failing under concurrent I/O.

Rather than discard it, the two runs were compared: 952 FAILED lines, 477
distinct ids, 475 of them present in BOTH runs and only 2 in one. Two
independent runs reproducing the same 475 failures is strong evidence they are
deterministic rather than I/O noise, so the numbers were kept. The 2
non-reproducing ids are both `test_acceptance_wall_catalogue` cases -- the
actual concurrency casualties.

Clustering by exception signature (not by FAILED line, which under `-q` carries
no message and only counts parametrised cases) put ONE cause far ahead: 80
failures plus a share of the 71 collection errors, all
`AssertionError: _SETUP_OPTION_INFOS is missing entries for catalogue question
ids: ['third-party-declaration-roles']`.

`application/wizard/commands.py:608` asserts AT IMPORT that every catalogue
question id has a `typer.Option` entry. Commit `5ad0f86a75` -- the same
relocation that swept tick 6's work -- added the catalogue question and its
`wizard.setup.taxpayer-type.declaration-roles.*` locale keys but no option
entry, so importing the wizard module raised and every test reaching it died.

The first fix was incomplete and said so under test. Adding the option made
typer pass `third_party_declaration_roles` into `SetupAnswers`, which forbids
extras: `Extra inputs are not permitted`. The field already exists -- as
`declaration_roles`. Field name is `question.id.replace("-", "_")`
(`commands.py:950`), so the id must be `declaration-roles` to reach it, and
every other surface already agrees: the `SetupFieldSpec` key
(`core/setup_answers.py:236`), the profile_key `taxpayer_type.declaration_roles`,
the validator, and the locale key family. The question `id=` was the lone
outlier. Renaming the FIELD instead would have rippled through the profile
schema; renaming the id is the minimal coherent fix.

Landed: catalogue id and option both `declaration-roles`, choice values derived
from `ThirdPartyDeclarationRole` in the established
`_taxpayer_type_choice_values` pattern so the flag cannot drift from the enum,
and `wizard.setup.flags.declaration-roles.help` added to all four catalogues
through `dev.locales set` with real translations -- no self-referencing
placeholder, no `_intentional_identical` entry. The mistaken
`third-party-declaration-roles` help key was removed from all four.

Wizard suite: from every test erroring at import to 299 passed, 4 failed.

Three of the four remaining are `test_scripted_parity`, and they were NOT
papered over. The rejection lands on page `tax-residence-jurisdiction-scope`,
not on the new page -- a token-ALIGNMENT shift, where the new always-visible
optional CHECKBOX displaces every later token by one. That points at
`_project_scripted_answers` and `run_scripted_flow` disagreeing about the new
page, which is an engine question. Adding a fixture answer would have turned
those three green while hiding that asymmetry, so it was left for a focused
pass. The fourth, `test_every_cli_translation_resolves_in_every_locale`, is
pre-existing and not mine: it and `test_parity` fail on 15 `cli.*.view_help`
keys from another peer's new `view` verbs, none of them declaration-roles.

### Correction: the executable-parity gaps DO have teeth, via filing_eligible

Tick 3 concluded that the queue's "executable_parity_evidence gaps on Modelos
714 and 200" premise was wrong because the single blocking
`required_gate_failures` entry is Modelo 165. That was right about
`RegistryCoverageAudit.ok` and INCOMPLETE about everything else, and the
second-largest failure cluster in the sweep is what exposed it.

52 failures are `RegistryValidationError: ... declares '<grade>' authority
grade, which cannot satisfy the requested 'filing' snapshot authority`. Grouped:
Modelo 200 43, Modelo 390 5, Modelo 038 2, Modelos 721 and 036 one each. The
Modelo 390 five belong to the export-fragment campaign.

Modelo 200 is not a recent downgrade -- both its 2024 and 2025-y-siguientes
revisions have declared `calculation` since the revision split in
`1d1b203114`, and record designs exist through `aeat-dr-200-2025`. Measured
directly: all three Modelo 200 coverage ledger rows report
`filing_eligible = False`, and the ONLY gapped tier on each is
`executable_parity_evidence`.

So the causal chain is: no executable parity evidence -> not filing-eligible ->
the revision honestly declares `calculation` -> every test requesting a filing
snapshot for Modelo 200 fails. The advisory gaps do not fail `audit.ok`, but
they are load-bearing one layer down. Both statements are true and the earlier
note only carried the first.

What closing it would take, measured rather than assumed. The gate
(`coverage.py:_executable_parity_gate`) accepts a tier source ref, a live
cross-reference decision, or a workbook parity ref whose `coverage_kinds` is
`formula_form`. `WorkbookParityReference` validates that `formula_form` REQUIRES
`runner_required = True`, and the tier is meant to carry `output_cells` and a
fixture -- it asserts an executable check, not a declaration.

Corpus-wide there are 112 distinct workbook parity references: 72
`record_design_layout`, 40 `static_layout`, and **zero `formula_form`**, every
one `runner_required = False`. Modelo 200's own two refs are
`record_design_layout` pointing at `aeat-dr-200-2025` with empty `output_cells`.
Its 2025 formula workbook IS present in the corpus
(`01-200-ejercicio-2025-10-9-mb-xls.xlsx`; ten sibling sidecars have had their
sources pruned).

So executable parity is UNBUILT INFRASTRUCTURE rather than a missing datum for
one modelo. Enrolling the present workbook as `formula_form` would be a
fabricated grounding claim without a runner that actually evaluates it and
grounded output cells -- and `no-silent-under-declaration` is explicit that the
oracle must follow the fix, never precede it. Writing one to turn 43 tests
green would convert a live gap into verified behaviour behind an AEAT-branded
name.

Item 3 therefore stands blocked, now with a sharper boundary than "needs an
artefact": it needs a workbook formula-parity runner plus grounded output
cells, which is feature work, and even then raising the authority grade is the
`S17` operator attestation that no program may perform on its own. The 764
advisory `executable_parity_gaps` are the same absence counted per coordinate.

### Canonical profile identities: 13 tests migrated, one false assertion corrected

The third sweep cluster was 13 `ValueError: profile_id is not a canonical
profile identity` (the 13 `badly formed hexadecimal UUID string` entries are the
same failures' `from exc` causes, not a separate cluster).

Chain: test -> `isolated_runtime_profile(bucket_id=...)` ->
`provision_test_profile_bucket_session` -> `publish_test_profile_capsule` ->
`canonical_profile_bucket_id`, which accepts only a version-4 UUID. Commit
`fd1b71807b` (2026-08-18, ten days old and not in flight) routed the production
keying sites and left three test files addressing buckets by readable label.

A measurement went wrong and was caught. A `grep -A3` for `bucket_id=` near
`isolated_runtime_profile(` suggested hundreds of readable literals reaching the
capsule path, implying a 227-site migration. Running one such file
(`test_filing_record_repository_roundtrip`) returned 32 passed, refuting it: the
`-A3` window was catching `bucket_id=` lines belonging to other calls. The real
scope is three files, and the corpus already has the convention -- structured
valid UUIDv4 constants such as `30330300-0000-4000-8000-000000000700`.

Migrated to canonical UUIDv4 constants, readable names kept as the `label` the
helper already takes separately: `test_multi_bucket_runtime` (4 tests),
`test_justificante_capture` (7), `test_review_package_signing` (the rest). All
29 tests across the three files pass.

The migration exposed a test asserting the opposite of the documented design.
`test_signing_keypair_refuses_foreign_or_whitespace_payload_bucket[whitespace]`
fed a whitespace-wrapped bucket id and demanded a refusal. It only ever passed
because the readable label failed UUID parsing BEFORE any bucket comparison --
a refusal for the wrong reason. With a canonical id the padded spelling is
accepted, and that is correct:
:data:`~cadrumo.core.identity.BucketId` declares
`StringConstraints(strip_whitespace=True, ...)`, and `canonical_bucket_id`'s own
docstring states the rule it protects -- a whitespace-wrapped spelling of a
VALID id must not yield a different address, "two buckets to the address, one
bucket to every other layer".

So the case was not deleted and no strictness guard was bolted on to make it
green. The refusal test now covers the `foreign` case alone -- which for the
first time exercises a REAL bucket mismatch rather than a malformed id -- and a
new test proves the normalisation contract positively: a padded row is stored,
loaded and resolves to the same bucket. An accidental pass became two honest
assertions.


### Localized refusals: five tests matching prose that is now a translation key

Two sweep clusters were checked and left alone as another campaign's, with the
evidence for saying so.

The 24 `NoRevisionForPeriodError` are 14 Modelo 390 and 8 Modelo 303 -- both
export-fragment trees this loop is barred from -- plus two 2010 filing years
outside the supported window. The 21
`CalculationRevision ... requires context-bound aggregate validation` come from
`b66bc26f05 feat(m303): bind rectificativa motive authority [W04.P07.S92]`,
which is a CLOSED row in the export-fragment plan (its `W04.P07.S84` is the row
still open). Attributing the failing tests by the log's own test headers rather
than by a grep window showed all 16 are `cancel_or_modify`,
`rectificativa_nota_three` or `prior_domiciliation` -- that campaign's feature.
An earlier read had mistaken an adjacent header (a Modelo 184 test) for one of
them.

The 19 `Regex pattern did not match` failures are a different thing and were
fixable. Errors across filing, storage and ledger have moved from English prose
to typed translation keys, and these assertions still matched the old sentence:
`'not present in the calculation registry'` now raises
`application.filing.runtime.errors.modelo_not_in_registry`,
`'no active bucket session|route does not match'` raises
`errors.storage.runtime.not_ready`, `'missing requested modelo definitions'`
raises `application.filing.runtime.errors.registry_missing_requested_modelos`.

Fixed to the convention the codebase already uses in 574 files --
`assert excinfo.value.translated_message == "<key>"` -- in
`test_schema_completeness`, `test_review_runtime_storage`,
`test_testing_registry` and `test_evidence_storage_errors`. 25 tests across the
four files pass. Matching rendered prose tracked the locale catalogue's wording
rather than the contract, which is why a reword silently broke them.

One of these needed more than a key swap. Both purchase-invoice evidence-input
refusals -- unreadable file and unsupported extension -- now carry the SAME key
`errors.refused.refused_ledger_evidence_input`, so asserting the key alone would
have let the extension test pass on an unreadable-file failure. The
unreadable-file test already discriminated on
`terminal_precondition_verdict.failed_condition_id`; the extension test now does
too, against `EVIDENCE_FILE_EXTENSION_SUPPORTED`. Swapping prose for a shared
key without that would have quietly widened what the test accepts.

The remaining regex failures in this cluster are M303 carry, IVA-wallet and
M303-exonerado-390 messages, left to the campaign that owns them, plus two
genuine rewordings rather than key migrations.


### Ledger confirm tests: the fixture invoice named no role, so direction blocked

Nine `TestConfirmInvoiceDraftFromEvidence` cases failed with
`ConfirmationBlockedError`. Probed the refusal context with an out-of-repo
pytest plugin rather than editing anything: one unresolved blocker,
`unresolved_direction` -- "the identifier 'B12345674' verified, but no role
evidence ties it to the counterparty; accepting it because it is the only one
left would name whichever unrelated entity happens to appear on the page".

The gate is deliberate and carries its own passing tests
(`test_direction_cross_check_at_the_confirm_boundary`,
`test_absent_identity_is_not_a_failed_role`). `identity_roles.py` withholds a
resolution when a verified identifier carries no `role_evidence`, and
`grounded_reading.py` keeps role evidence only when
`printed_excerpt_occurs(...)` confirms it in the transcription -- an
anti-hallucination guard, so a reader that invents a heading loses it.

The fixture was the defect. `_FULL_INVOICE_LINES` printed a bare
`"NIF: B12345674"` with nothing tying it to the supplier, and
`_FULL_INVOICE_FIELDS` supplied no `supplier_tax_id_role_evidence`. These nine
cases are about MINTING, IDEMPOTENCY, OVERRIDES and LINKING, so the document was
made well-formed rather than the gate worked around: the line now reads
`"Proveedor NIF: B12345674"` and the reader returns
`supplier_tax_id_role_evidence = "Proveedor NIF:"`, which occurs in the
document text and therefore survives the excerpt check. The file had been
adapted the same way once before, when wiring the semantic reader made these
cases stop at a connection error.

What was NOT done: no resolution was injected to answer the blocker, and no
candidate was promoted for being the only one left. Either would have made nine
tests green while retiring the guard's meaning for this fixture -- the blocker
exists precisely because one verified identifier is not evidence of whose it is.

22 tests in the file pass, up from 13 passed 9 failed, and the direction gate's
own 16 selected tests still pass.

The constants are file-local: `entrypoints/cli/tests/`
`test_ledger_evidence_extract_cli.py` defines its own same-named
`_FULL_INVOICE_LINES`, which this change does not touch.

