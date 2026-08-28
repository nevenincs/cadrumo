---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:93229790ae00bae0476708a79f90b64fee196d53ed0d6ccec7e16933c9d90170'
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

### Modelo 111 colegio-concertado: an undeclarable fact the fixtures never stated

Twelve tests across M100, M111, M184, M190 and M303 scenarios failed with
`ModeloProfileReadinessError: application.modelo.errors.profile_readiness_missing`.
Probing the refusal context with the out-of-repo plugin named the single missing
requirement: **"Es un colegio concertado"**.

The requirement is correct and must not be relaxed. Commit `60e81539e5
filing(m111): give the colegio concertado declaration a source` gave the Modelo
111 fichero a filer-data row for it, and
`application/filing/_producer_snapshot.py:1548` refuses a `None`: "Modelo 111
colegio_concertado must be explicitly declared". That is
`no-silent-under-declaration` working -- a regulatory flag cannot carry a
default, because defaulting it declares something on the operator's behalf.

Scoping was checked rather than assumed. Even the test named for Modelo 100
reports `modelo: '111'` in its refusal, because its scenario files an M111 whose
retencion folds into the M100 trabajo boxes. So the requirement is M111-scoped
and fires only where M111 work actually happens; it is not a baseline field
gating every modelo.

Fixed by declaring the fact where the fixtures build a COMPLETE profile:
`withholding.colegio_concertado = False`, which is the truthful value for a
natural-person filer, in `_file_flow_support`, `_import_flow_support`,
`test_m111_retenciones_observation_live`,
`test_modelo_100_2025_retenciones_credit_fold_in_live`,
`test_renta_annual_reconciliations_fold_in_live` and
`test_source_boundary_and_enrollment` (two lists) -- seven insertions.

Checked before inserting: `test_source_boundary_and_enrollment` builds its
`incomplete_facts` by REMOVING one path from the complete tuple and asserts the
length is exactly one less, so adding a fact preserves that invariant rather
than breaking the fixture that proves the refusal still fires.

A systematic sweep was considered and rejected as over-broad: 67 files reference
`censo.activity_start_date` without this fact, but five are production and most
test scenarios never touch M111, so adding the declaration everywhere would be
noise rather than correctness. The support modules the failing tests actually
use were patched instead -- and the first pass missed `_import_flow_support`
precisely because it was found by following the failing test's imports rather
than by pattern-matching.

Outcome: the M111 file is fully green, and
`test_amend_locally_filed_still_refused_after_import_path_exists` passes. The
remaining cases advanced PAST readiness into distinct defects -- Modelo 100 and
the renta fold-ins now stop at `ModeloAggregationBindingError` over rejected
`renta-2025-inventory-activity-*` bindings, which is the separate seven-count
cluster, and the M303 wallet cases belong to the export-fragment campaign.

### A hand-listed locked-source set went stale the moment `inventory` enrolled

The failures tick 13 uncovered were `ModeloAggregationBindingError` with
`rejected_binding_ids` naming `renta-2025-inventory-activity-*`.

The engine is right to refuse. `_reject_caller_overrides_of_source_bindings`
rejects any caller-supplied binding a bucket source resolver owns, because a
caller override would leave the persisted revision no longer reflecting the
sources it claims to aggregate. `4b031370bb feat(inventory): enforce
source-owned calculation inputs` enrolled `BindingSourceKind.INVENTORY` in the
`LOCK` tier of the caller-override ladder, so inventory values must now come
from bucket substrate.

The defect was in the test helpers, and it is the exact failure mode
`aeat-registry-bindings` names -- "a hand-listed string set for a family". Two
files computed "bindings the caller must supply" by excluding a HARDCODED set of
source tokens: `profile`, `relation_prefill` and six ledger/invoice kinds. That
list was correct when written and silently wrong the moment a seventh locked
kind was enrolled: every inventory binding was then offered to the engine as a
caller value, and the lock rejected the whole calculate.

Fixed by DERIVING the locked half from the ladder that declares it --
`precedence_ladder_sources(CallerOverrideDisposition.LOCK)`, whose own docstring
says it exists "so a source kind's lock-vs-carry disposition is declared once
... rather than hand-listed per set". Only the two genuinely scenario-specific
exclusions stay literal, and they now carry the reason they are there:
`profile` comes from the seeded record, `relation_prefill` is left unset so the
enrolled resolver folds from the store. A future `LOCK` enrolment is picked up
without touching either file.

`test_modelo_100_2025_retenciones_credit_fold_in_live` (2 tests) and
`test_modelo_100_2025_expense_inspection_live` (1) now pass.

The same hardcoded shape survives in four more files
(`test_invoice_accumulative_cross_modelo_periods`,
`test_derived_aggregate_override_real_path`,
`test_e2e_ledger_m130_quarters_to_m100_annual`,
`test_pulled_history_reaches_calculate`), three of them currently failing. They
were left for their own tick rather than swept blind: each needs its scenario
exclusions read before the literal set is replaced, and
`test_pulled_history_reaches_calculate` is green today, so rewriting it would be
churn with no failing gate to prove the change.

### A guard test that had been silently disarmed by a refactor

Deriving the locked-source set (previous note) was applied to the two remaining
failing files that carried the same hand-listed shape,
`test_derived_aggregate_override_real_path` and
`test_e2e_ledger_m130_quarters_to_m100_annual`. Their combined sweep failures
fell from 8 to 4: the binding-lock cause cleared, and what remained was a
different defect underneath.

That remainder is worth recording on its own.
`test_operator_write_door_refuses_a_value_at_the_derived_aggregate_path` and
`test_the_art_58_computation_can_no_longer_be_displaced_by_a_stored_value` were
failing `DID NOT RAISE ProfileSchemaValidationError`. Both exist to pin a real
defect: casilla 0513 carries the computed Art. 58 aggregate, and a stored
profile value at the derived path would displace the law.

The production guard turned out to be INTACT. The schema declares
`renta_family.descendientes_minimos_aggregate_{filing_year}` as a derived
selector and `derived_selector_for_path` resolves it for the test's 2024 year.
What had gone was the test's reach to it: the probe called
`set_active_test_profile_facts`, described in the test as "the real single-field
operator write door", but that function is a SEEDING helper -- its own docstring
calls it "the successor to the retired application-side plural fact command" --
and it merges facts onto the record without judging them. The probe therefore
exercised no guard at all, and the test asserted a refusal that could not fire.

This is the more dangerous shape of a red test: it reads as protecting the
override channel while protecting nothing. Had it been "fixed" by relaxing the
assertion, the channel would have looked closed and been open.

Repointed at `reject_invalid_profile_facts`, which
`application/user_profile/fact_write.py` names as the shared authority --
"what is shared is not the door but the JUDGE: every one of them refuses
through" it, registration, the wizard's fact patch and the cotejo censal alike.
Proving the judge refuses a derived path binds every door rather than one
surface. Both tests pass, and the refusal names the derived path as the test
already required.

`test_e2e_ledger_m130_quarters_to_m100_annual` still has 2 failures on a
separate cause, left for its own tick.

### Justificante CSV shape, a deeper key migration, and a fixture that rotted

Three distinct defects closed two files.

**The justificante CSV shape.** Fixtures built the reference id as
`f"JUST-130-{year}-{period}-AUTONOMA-C19"`, but that id IS the justificante
CSV and `Justificante.csv` pins `^[A-Z0-9]{8,32}$`. A codigo seguro de
verificacion is uppercase alphanumeric, so the readable hyphenated spelling was
a shape AEAT never issues and could not survive the pattern. Rewritten without
separators in `test_e2e_ledger_m130_quarters_to_m100_annual` and
`test_verificado_completo_regression`. Checked that `ExternalEvidence.
reference_id` carries no such pattern, so the hyphenated ids in
`test_external_evidence` and `test_modelo_filing_record` are legitimate and were
left alone -- both files are green.

**The key migration went one level deeper.** An aux-block assertion already
anticipated a localized wrapper and read `__cause__` for the structural detail,
but the CAUSE is localized too now, so `"aux_version" in str(cause)` matched a
translation key. The refusal carries `undeclared_fields` in its context, so the
assertion now reads that plus the cause's own key -- strictly stronger than the
substring match it replaces, because it reads the structured field the refusal
exists to name rather than hoping the rendered sentence spells it.

**A fixture that rotted, and looked like a production bug.**
`test_tampered_revision_raises_drift_error` failed
`AttributeError: 'CalculationRevision' object has no attribute
'source_provenance'`, raised INSIDE
`calculation_revision_identity_inputs_from_revision` -- which reads like a
production defect in the integrity check. It is not: the model declares the
field. The fixture built its tampered revision with `model_construct` and a
hand-enumerated field list, and `model_construct` neither validates NOR
populates unlisted fields, so every field added to `CalculationRevision` after
the list was written was simply absent from the object. The test then failed on
a missing attribute instead of on the drift it exists to prove -- the guard was
never reached.

Rebuilt with `model_copy(update=...)`, which also bypasses the validators (the
property the test needs, so the hash mismatch is not caught at build time) while
carrying every other field from the original. It cannot rot the same way again.
The test now genuinely raises `StoredCalculationDriftError`.

`test_e2e_ledger_m130_quarters_to_m100_annual` is fully green at 5 passed (4
sweep failures), and `test_verificado_completo_regression` at 3 passed (2).

### Acceptance wall: a stale CLI verb fixed, and the mutation harness diagnosed

The wall catalogue was 18 failures in the sweep and is 8 now, most of the
reduction being fallout from earlier ticks rather than work aimed at it.

**Fixed: a stale verb in the ledger-exclude wall.**
`test_ledger_exclude_journey` read a single row back with
`app ledger review <transaction_id>`, and the CLI refused with "Got unexpected
extra argument(s)", exit 2. `review` is the INTERACTIVE list surface and takes
no positional id (only `--filter`); the single-subject read verb is
`app ledger view <transaction_id>`, whose id is a positional argument exactly as
`aeat-cli-contract` requires. Repointed; both tests in the file pass in the
integration lane, and the catalogue gained a passing wall.

Worth noting how it hid: the file is integration-marked, so running it in the
default unit lane reports "NOTHING RAN ... 2 deselected", which reads as green.
The lane banner naming the deselection is what prevented calling it fixed.

**Diagnosed, not patched: the gate's own anti-tautology proof.**
`test_a_regressed_wall_assertion_is_caught_by_the_gate` mutates the
ledger-exclude wall, writes the mutated module into `tmp_path`, and runs it in a
subprocess rooted there. The subprocess correctly forces `-m integration` and
`-n0`, so the lane is not the problem. The problem is location: a module written
outside the repository never picks up the conftest chain it depends on, so setup
dies on `LookupError: ContextVar 'cadrumo_profile_custody_port'` and the mutated
assertion is never reached. The wall test itself is healthy -- it passes in its
own lane -- so only the mutation harness is broken.

Not patched deliberately. The obvious fix, writing the mutated module beside the
original so conftests apply, means creating a deliberately-FAILING test file
inside `src/`. Peers commit this working tree continuously (four times this
session), so a swept mutation file would land a permanently red test in the
repo. Replicating the conftest chain into `tmp_path` is the alternative and is
fragile. This needs a design decision rather than a quick edit.

**The remaining walls are not this campaign's.** Their refusals are two: Modelo
303 external import requiring complete typed filing-instance evidence, which is
the export-fragment campaign's surface; and `requested registry revision '2024'
is not the law-determined revision for this filing target. The law-determined
revision is '2025-y-siguientes'` on the Modelo 200 micro-empresa cuota wall.

That second one is a grounded-calculation question, not a fixture typo. The wall
asserts a cuota integra against the AEAT Manual Practico rate, so which revision
applies decides which ejercicio's rate is used -- and
`aeat-registry-authority-flow` is explicit that a requested revision may only be
ASSERTED equal to the law-determined one, never injected. Choosing the pinned
value to make the refusal stop would be choosing which year's law to compute
under. Left for a tick that can ground it against the manual's ejercicio.

### Modelo 200 micro-empresa wall: the revision guard caught a real wrong-year computation

The wall refused with `requested registry revision '2024' is not the
law-determined revision for this filing target. The law-determined revision is
'2025-y-siguientes'`, and the guard was right in a way worth recording.

The test passes `filing_year=2025` and pins `revision="2024"`. Modelo 200's
`2024` revision closes at 2024-12-31; 2025 resolves to `2025-y-siguientes`. Had
the pin been honoured, ejercicio 2025 would have been computed under the 2024
flat 23 % rate -- 23.000,00 EUR instead of 21.500,00 -- which is precisely the
defect class `aeat-registry-authority-flow` describes when it says a stored or
operator-supplied revision may only be ASSERTED equal to the law-determined one,
never injected as the selector. This is that rule earning its keep on a live
case, not a hypothetical.

The file contradicted itself, which is what made the pin look defensible. The
docstring says ejercicio 2025, grounds on LIS DT 44ª (Ley 7/2024) at 21 %/22 %,
and expects 21.500,00. The comment block ABOVE it described a different
scenario entirely -- ejercicio 2024, flat 23 %, cuota 23.000,00 -- and asserted
that the two-tranche scale is 17 %/20 % for ejercicios iniciados en 2025.

Adjudicated against the registry rather than either prose block. The
`is.modelo-200.tipo-gravamen-pyme` bracket table, keyed on `filing_period` and
cited to `ley-27-2014:art-29` and `ley-27-2014:dt-44`, encodes 23 % flat for
2024, 21 %/22 % for 2025 (fixed addition 10.500 above 50.000) and 19 %/21 % for
2026, and says in terms that "The final LIS art. 29.1 17 % / 20 % scale is not
the 2025 window". So the docstring and the expected 21.500,00 are correct
(10.500 + 50.000 x 22 %), and the header comment was stale AND wrong on the
rate. It was rewritten to the grounded schedule rather than deleted: left
standing, it would have led the next reader to "correct" the expected value to a
figure no ejercicio carries.

The pin is now `2025-y-siguientes`, which NAMES the law-determined revision
rather than selecting a different one. Test passes.

The test's own name still says `_2024` while it covers ejercicio 2025. Left
alone: the acceptance-wall catalogue addresses it by node id, so a rename is its
own change, and the name is cosmetic where the pin and the comment were not.

Also fixed in the same file: `test_modelo_130_malformed_numeric_binding_refuses_`
`not_reclassified` asserted the English prose "is not a decimal" against an
envelope that comes back localized ("no es decimal"). Replaced with the
refusal's own code. The first guess at that code was wrong and the run said so
-- the real one is `REFUSED_MODELO_CALCULATE_DECIMAL_INPUT`, which names the
decimal-shape refusal more precisely than the sentence did. All 7 tests in the
file pass.

### Acceptance wall #260: a flattened payload and a blanket assertion that outlived its premise

Wall #260's guarding test, `test_prepare_shows_import_step_pending_on_fresh_`
`profile`, failed on `KeyError: 'action'` at
`work_action["action"]["action"]["action_id"]`. Probed the live payload with an
out-of-repo pytest plugin: `next_action` carries ONE `action` level
(`{"action": {"action_id", "target_command_key", "cli_path"},
"argument_bindings": [...]}`), and the very next line in the same test already
used the correct depth for `cli_path`, so the double-nesting was stale rather
than a shape disagreement.

The repo-wide sweep was checked before touching anything: 19 sites spell
`["action"]["action"]`, but only two are `next_action` payloads, both in this
file. The other 17 sit on ERROR envelopes, where `error["action"]["action"]` is
legitimately two levels deep -- an ActionRecovery wrapping an action. Rewriting
them by pattern would have broken seventeen passing tests to fix two.

The second failure in the file was more interesting.
`assert all(notice["action"] is None for notice in preparation_notices)` now
fails because one of the five preparation notices carries an action. Probing
showed which: four are null, and `overview.prepare.next_step.start_modelo_work`
carries exactly the action its own step row carries. That is coherent -- a step
that can resolve an executable action offers it, and the ones that cannot are
the ones this same test already documents as unable to ("Importing needs a
statement file and a provider this read model cannot know, so the row carries no
executable action rather than a placeholder").

So the blanket assertion was true only while no step carried an action, and
keeping it would forbid the surface from handing the operator a command it had
already resolved. Replaced with the discriminating property: the actionable
notice must carry the SAME action as its step row (not a second spelling of it),
and every other notice must carry none, named in the failure message. Five tests
in the file pass, and the wall catalogue is at 25 passing, up from 23 when this
sweep of it started.

### Two work units pinned to revisions the registry never shipped, and a wall that passed vacuously

Wall #328 (Modelo 190 reconcile) failed, and the reconcile output named the
reason: `... (snapshot_unavailable); verdict reflects receipt identity only`.

The registry was not the problem -- `authority.snapshot('190', filing_year=2024,
period='0A')` builds cleanly at both filing and calculation grade, and both M190
revisions are filing grade. The work unit was: the fixture pinned
`_M190_2024_0A_REVISION_ID = "2024-y-siguientes"`, and Modelo 190 ships `2024`
and `2025-y-siguientes`. There is no `2024-y-siguientes`. Snapshot resolution
failed on a revision id that never existed.

The consequence is the part worth recording. When the snapshot cannot resolve,
reconcile degrades to comparing receipt identity ALONE and reports a clean
match. So the SIBLING test, `..._m190_matches_when_computed_agrees`, was passing
-- and passing vacuously: it asserts a clean `matches` and got one without a
single casilla being compared. A green test was standing guard over nothing,
while its divergence twin was the only reason anyone noticed.

Modelo 390 carried the identical defect: `_M390_2022_0A_REVISION_ID =
"2010-y-siguientes"` against real revisions 2021 through 2025. Corrected to
`2022`. This touches a CLI test constant, not
`_data/registry/aeat/modelos/390/`, so it stays outside the tree the
export-fragment campaign holds; the note is here because the ownership line is
worth stating rather than assumed.

Both constants now name revisions the registry actually carries. Four tests pass
and the divergence cases assert real `diff` rows, so the comparison is genuinely
running. Wall #261 was separately repointed: the catalogue cited
`test_requires_classifies_m130_casillas_against_live_registry_no_active_profile`
while the live test had been renamed to
`test_requires_classifies_real_m130_sources_without_an_active_profile` -- a
dangling reference of exactly the kind `firmware-reference-parity` describes,
with the capability text and the test's own docstring confirming they are the
same guard.

Wall #423 was NOT repointed, deliberately. Its capability is "a late-night
filing completes in one command via aeat quickfile, all the way to an exported
fichero", and its cited test no longer exists. The surviving quickfile tests are
`..._reaches_granted_verify_before_withdrawn_export`, which stop at a REFUSED
export because no complete export layout is authored -- they prove strictly less
than the wall claims. Pointing the catalogue at one would record a capability as
walled when nothing guards it. The wall is genuinely reopened.

One transient scare: a run failed with `ImportError: cannot import name
'current_operator_surface_reconciliation' from ... _common`, which looked like a
broken tree. It was a peer mid-commit -- the package imports cleanly moments
later and the tests pass. Worth remembering before attributing a failure to a
shared worktree's momentary state.

### Systematic sweep for the vacuous-pass class: two bad ids were the whole of it

The Modelo 190 and 390 fixtures had been pinned to revisions the registry never
shipped, and the failure mode was silent -- reconcile degraded to receipt
identity and reported a clean match. A test can therefore be GREEN and prove
nothing. That is worth sweeping for rather than waiting to trip over.

Swept every `revision=` / `revision_id=` string literal under `src/cadrumo`
test packages against the 62 revision ids the registry actually ships. 75
distinct unknown ids, which sounds alarming and is not: 67 are deliberately
synthetic (`test-drift`, `wrong-revision`, `unrelated-stale-revision`,
`test-dangling`) belonging to negative tests and hand-built registries, where a
fabricated id IS the fixture.

Filtering to YEAR-SHAPED ids -- the ones that look real and so could deceive --
leaves 8. Six are transparently synthetic (`2025-clean-state-test`, `2026-v1`,
`2019-y-siguientes-successor`, `2024-01-01-a-2024-12-31`). Two were worth
checking:

- Modelo 714 `2021-y-siguientes` in `test_modelo_unsupported_work_refusal`,
  against real revisions 2021 through 2025. The test passes, and it passes for
  the RIGHT reason: its `required_groups` assert the refusal names Ley 19/1991,
  Orden HAC/1023/2021 and the Sede host, which only a genuine unsupported-modelo
  refusal carries. Corrected to `2021` anyway, and the correction doubled as the
  proof: 13 tests still pass, so the id was provably inert rather than
  load-bearing. A false constant that happens not to matter today is the same
  landmine the M190 one was before it mattered.
- Modelo 353 `2008-2025` in `test_cross_modelo_carry_taxonomy`. Genuinely inert:
  `_classify` returns on the `per_grupo_member` grouping before the revision is
  read, and that early branch is exactly what the assertion checks. Left alone.

The adjacent vacuity risk was checked too. `_DIRECT_CROSS_MODELO_CARRIES` keys
its rows by `(modelo, revision, binding)`, so a stale key would silently
classify a row as unowned and pass. Its one entry resolves: Modelo 130
`2019-y-siguientes` exists and carries
`irpf.previous_year_economic_activity_net_income`.

So the two fixtures already corrected were the whole of this defect class in the
test tree, which is the useful result -- the sweep was worth running to learn
that rather than to assume it.

### The export-layout kerfuffle: the refusal was the stale part, not the layout

Operator asked for the export-layout situation to be resolved. It inverts a
conclusion recorded two ticks earlier, so the correction comes first.

**Tick 20 recorded that acceptance wall #423 had genuinely lost its guard** --
that its capability, "quickfile all the way to an exported fichero", was
unguarded because the surviving quickfile tests stop at a REFUSED export. That
was read off those tests' docstrings rather than off the product. It is wrong.

Run today, `test_quickfile_m115_reaches_granted_verify_before_withdrawn_export`
FAILS, and it fails because the chain now SUCCEEDS: exit code 0 where it expects
1, `"completed": true` where it expects false, `stopped_at_stage: null` where it
expects `"export"`, and a populated `export` payload where it expects `None`.

The layout is present and renderable. Modelo 115's `2019-y-siguientes` revision
carries `modelo-115-fichero-boe`, fixed-width with 2 records, which is exactly
what `export_layout_renderability_reason_code` requires to return None. So does
Modelo 130 and Modelo 111. The refusal path
(`_select_export_layout` -> `subview.export_layout_ids`) is reached only when
there is nothing to select, and there is something to select.

A directory listing nearly produced a second wrong answer here. 66 revisions
ship an `export_layouts` fragment directory, which looks like proof that
exporting works -- but Modelo 115 had that directory throughout the period when
its export legitimately refused. `aeat-registry-authority-flow` says to assess
from the LOADED SNAPSHOT and never a directory listing, and this is why: the
directory says a fragment exists, not that the layout is complete.

Git confirms the shape of the drift rather than my inferring it.
`test_quickfile_runs_full_chain_to_exported_fichero` existed before
`fb5b2fc6ea S58: close immutable filing evidence lifecycle` and was replaced in
that commit by the two `..._before_withdrawn_export` variants. Wall #423 still
cites the original name, which is why it reads as REOPENED. The wall was never
wrong; the test was inverted around it while layouts were unavailable, and the
catalogue kept pointing at the capability everyone intended to restore.

So the guard was restored rather than repointed: the M115 case asserts the
completing chain again (every stage ok, export ok, payload present) and carries
the original name. It also now asserts the fichero's BYTES, not just the stage
status -- an export reported ok that wrote nothing would satisfy every other
check in the test.

**Not yet verified, and not claimed:** the run could not be completed. A peer is
mid-relocation in the working tree -- `_parity_harness.py` deleted with an
untracked `parity_harness.py` beside it, `__init__.py` already importing
`.row_set_assembly` while the file on disk is still `_row_set_assembly.py` -- so
`cadrumo.application.storage.calc_sheets` does not import and every CLI test
errors on it. That is their atomic relocation in flight and must not be touched.
The payload facts above were observed BEFORE the tree entered that state; the
two file-bytes assertions are reasoned, not run, and need a green run next tick
before this is called done.

The in-flight sweep reached 99% and may be tainted for the same reason; its
totals need reading with that in mind.

### Export-layout kerfuffle closed, and a live crash on `ledger classify`

**The export guard is restored and VERIFIED.** The earlier note flagged two
file-bytes assertions as reasoned but unrun; the peer's relocation settled and
`test_quickfile_runs_full_chain_to_exported_fichero` now passes, fichero bytes
included. Independently confirmed the product fact without the CLI:
`export_layout_renderability_reason_code` returns None for
`modelo-115-fichero-boe`, so the layout is renderable and the refusal the old
test asserted cannot occur. Acceptance wall #423 resolves against the restored
name.

**Fresh full sweep** (1h19m): 452 failed, 28107 passed, 4 errors, against the
earlier 475 failed / 27952 passed / ~70 errors. The error collapse is the
wizard `_SETUP_OPTION_INFOS` import fix -- that 80-failure cluster is gone from
the signature table entirely. The 4 remaining errors are M303 IVA-wallet
provenance, the export-fragment campaign's.

**A live production crash, found via the walls.** Three walls (#217, #223, #253)
had started failing, and it was NOT fallout from my changes:
`aeat app ledger classify` was returning an internal-error envelope because
`actions_manual.py` raised `NameError: name 'format_decimal' is not defined` at
`_event_payload`. The module used the symbol three times and imported only
`Decimal`. Its sibling `actions_common.py` in the same package shows the
canonical spelling, `from ...core.decimal import format_decimal`; added it
there. The file was mid-edit in the working tree, but no plausible intent leaves
three uses of an unimported name, and the verb was broken for every operator
meanwhile.

**The stale `review <id>` verb again, and a sweep that would have been wrong.**
19 sites call `app ledger review` with a following argument, which looks like a
systematic rename to apply everywhere. It is not: 14 pass `--filter` or
`--help`, which is exactly right for the interactive list surface. Only 5 pass a
bare positional id. Fixed the two in this file to `view`, whose help declares it
takes "Id de la transacción (o prefijo no ambiguo)" -- so prefix resolution,
which is what those two tests are named for, is preserved. Their assertions then
needed the uniform single-transaction key: `LedgerViewResult` carries
`transaction_id`, not the list row's bare `id`. 14 tests in the file pass.

Three remaining positional-id sites live in `test_cli_surface.py`, one of which
mixes an id AND `--filter` flags -- an intent that neither verb has, so it needs
reading rather than mechanical replacement. Left for its own pass.

Acceptance wall catalogue: **28 passing, up from 23** when this sweep of it
began. Of the 4 remaining, #419 is the export campaign's M303 rectificativa, the
gate's own mutation harness needs the design decision already recorded, and two
are the persona walls that did not reproduce across the first sweep's two
concurrent runs -- flaky-under-load rather than newly broken, and worth
confirming sequentially before treating as defects.

### A crash, not a refusal: the optional `pais` validator called `.upper()` on None

The fresh sweep surfaced a signature the earlier one did not have in its top
clusters: 25 failures reading
`AttributeError: 'NoneType' object has no attribute 'upper'`. Every one of them
lands on the same line -- `domain/modelos/_row_models.py:165`, in
`Modelo184MemberRow._pais_uppercase_alpha` -- across 21 distinct tests spanning
row models, the M184 socio handoff, multi-clave export parity, secure-envelope
decoding and the M210 agrupación e2e.

The field is `pais: _IsoCountryCode | None = None` and the validator was typed
`(value: str) -> str`, so the absent case reached `value.upper()` and raised.
Its immediate sibling, `_porcentaje_titularidad_within_bounds`, guards
`value is not None` correctly -- the inconsistency was within one class.

Whether `None` is legitimate had to be settled before guarding it, because a
guard on a genuinely required field would silently accept a missing country
rather than refuse it. Two pieces of the model's own prose disagree at first
reading: the docstring maps `pais -> country_code (required; never inferred)`,
which describes the DISEÑO's requirement, while the comment on the field itself
records the model's position explicitly -- "Absent rather than required because
the profile-driven producer has no country to supply ... Recording the socio's
country on the profile is the fix that would let this be required."

So the absent case is a declared, reasoned state with its own future remedy, and
the validator's job is to check the SHAPE of a value that is present. Guarded on
that basis, with the reason recorded at the validator so the next reader does
not re-litigate the same apparent contradiction. Nothing changes for a present
value; the same refusal fires on a malformed code.

A crash is also not a refusal in the sense this repo cares about: an
AttributeError carries no typed error, no translated message and no precondition
verdict, so an operator hitting it got an internal-error envelope where the
model intended either acceptance or a named validation failure.

Verified across the affected areas rather than the one file: 39 row-model tests,
3 M184 handoff-notice tests, 12 M184 multi-clave export-parity tests and 7
Modelo 210 agrupación e2e tests all pass.

### The stale-revision class had a second shape, and my first sweep was blind to it

The `KeyError: '...-y-siguientes'` cluster is the same defect already fixed for
Modelos 190 and 390 -- a fixture naming a revision the registry does not ship --
but reached through a DICT SUBSCRIPT rather than a `revision=` argument. The
earlier sweep only matched the argument form, so it reported the class closed
when it was not.

Modelo 151: `validate_modelo("151").revisions["2015-y-siguientes"]`. That window
was split into `2015-2022` and `2025-y-siguientes`, so the subscript raised
before the test reached any assertion. Both surviving revisions carry the
predicate under test with an identical expression, so the choice was not forced
by content -- it was resolved by LAW instead: the helper now reads the master
`supported-filing-years` declaration, takes its latest year, and asks the
authority for the governing revision. A future split moves it automatically. (Its
successor's name understates its reach: `2025-y-siguientes` opens on 2023-01-01.)

**The sweep's own flaw, worth recording.** The modelo-blind version compared
each literal against the UNION of every modelo's revision ids, so Modelo 390's
`2010-y-siguientes` passed silently -- because Modelo 360 genuinely ships a
revision by that name. A detector that pools identifiers across owners cannot
see a valid id used against the wrong owner. Re-run modelo-aware, matching
`validate_modelo("X").revisions["Y"]` and checking Y against X's own set, it
found exactly that one.

Modelo 390 ships 2021 through 2025 and the helper named `2010-y-siguientes`, so
every test routed through it died on a KeyError. The file carries no ejercicio
of its own -- it asserts shipped predicate definitions -- so the helper now
selects the modelo's current revision by `max(valid_from)` rather than any
literal. Same ownership reasoning as the earlier Modelo 390 constant: this is a
test helper, not `_data/registry/aeat/modelos/390/`, so it is outside the tree
the export-fragment campaign holds.

The only other subscript the sweep flags is a synthetic modelo-999 registry
built in `tmp_path` by `test_catalogue_verification`, where a fabricated
revision id is the fixture. Correctly flagged, correctly left alone.

M151: 4 tests pass. M390: 3 tests pass.

### An invalid NIE refused for the wrong reason, and a sweep that must NOT be run

The `Justificante` validation cluster resolved into three unrelated fixture
defects rather than one class. One was mine.

`Y7654321Z` is the "wrong taxpayer" fixture in the overview calendar evidence
tests -- the value that is supposed to differ from the filer's own `X1234567L`
so the evidence is rejected as belonging to someone else. It never got that far:
the NIE control letter is wrong, so `validate_spanish_tax_id` refused it as
MALFORMED before any identity comparison happened. The test passed or failed on
the wrong question entirely.

The validator names the remedy in its own message -- "expected check letter 'G'"
-- and `Y7654321G` validates cleanly while remaining obviously a different
taxpayer from `X1234567L`. Corrected at all three sites across two files; 8
tests pass, and the refusal under test is now an identity mismatch rather than a
checksum failure.

**The sweep that follows must not be applied.** Scanning test fixtures for
Spanish-tax-id-shaped literals that fail the real validator returns 63 distinct
ids. That looks like a systematic defect and is the opposite: the great majority
live in `test_nif_data_type`, `test_validators`, `test_unsecured_nif_canary`,
`test_censal_datos` and similar, where an INVALID identifier is the fixture --
these tests exist to prove the validator refuses. Mass-correcting them would
delete the coverage they provide.

Scoped instead to what actually fails: the whole sweep log contains exactly two
tax-id failures. The NIE above, and `'TAXPAYERDEFAULT' must be exactly 9
characters, got 15` from the `taxpayer_tax_id` default in
`_export_modelo_303_support.py`.

That second one is left alone, and the reason is a distinction worth keeping.
Earlier ticks DID correct Modelo 390 test helpers that named revisions the
registry never shipped, on the ground that a test helper is not
`_data/registry/aeat/modelos/390/`. This is different in kind: a NIF is not a
non-existent identifier being corrected to an existing one, it is a VALUE that
flows into the fichero bytes their export e2e tests assert. Changing it edits
the expected output of another campaign's suite. Correcting a dangling reference
is safe; changing a value under someone else's assertions is not.

### One synthetic registry, four stacked defects, and a 553-site sweep declined

`test_binding_readiness` builds a synthetic modelo-999 registry to make two
revisions cover one year, so a year-only readiness query meets an ambiguous
boundary. Its two failures were four defects stacked, each only visible once the
one above it cleared.

**1. `review_status = "reviewed"` on a legal entry.** The registry has TWO
review vocabularies: `LegalReviewStatus` (`pending_review`, `agent_reviewed`,
`operator_reviewed`) for legal references, and a separate
`ReviewStatus = Literal["reviewed"]` "retained for official sources and legal
parameters". The fixture used the source token inside a `[legal."..."]` block.

This is where the tick nearly went wrong. `review_status = "reviewed"` appears
**553 times across 64 files**, including the shipped registry legal catalogue,
which loads fine -- because in almost every one of those it sits in a
`[sources...]` or parameters block where it is the CORRECT token. Within this
one fixture, three occurrences: line 30 in a legal block (wrong), lines 44 and
55 in source blocks (right). A pattern sweep would have corrupted 551 valid
declarations to fix one. Corrected to `agent_reviewed`, which is also the honest
stamp for machine-authored fixture data -- `operator_reviewed` would assert a
human review nobody performed.

**2. No `supported_filing_years` declaration.** The loader now requires the
registry-wide declaration this campaign's opening brief established. Added,
admitting 2025 (the fixture's selectors) and 2026 (the year its readiness call
asks about).

**3. No `authority_grade`.** The validator's refusal is unusually explicit that
the rung must be declared by INTENT and "DO NOT pick the rung by looking at
which families this revision currently has", because a grade read off content
agrees with the content by construction and the check goes inert. The fixture
carries casillas and workbook-parity refs, which would have suggested a higher
rung; its INTENT is only ever to answer which revision applies, so
`applicability` is what it declares.

**4. A caller asking for more than the fixture claims.** With the grade declared
honestly, `authority.snapshot(...)` refused -- it defaults to `FILING`. Raising
the fixture's declared grade would have silenced that, and would have been
exactly the move the validator forbids: picking the rung to match a caller
instead of the revision's purpose. The two assertions are about which revision
SELECTION lands on, so they now request
`grade=RegistryAuthorityGrade.APPLICABILITY` -- the rung they actually need.

5 tests in the file pass.

### Inventory ownership: a selector shape left behind, and a branch that asserted its own opposite

The `DataBindingDefinition` selector cluster is `test_inventory_source_ownership`,
and it held two defects of different kinds.

**The selector shape.** The fixture built inventory bindings with
`actividad_id` + `operation`, a shape `_InventorySelector` no longer accepts: it
now requires `fact`, `record`, `grouping` and `row_field`, and forbids
`actividad_id` outright -- six validation errors per binding. Rather than infer
the new envelope, it was copied from the shipped
`renta-2025-inventory-activity-*` selectors, which state it exactly:
`fact = "row_field"`, `record = "inventory_activity"`,
`grouping = "per_inventory_activity"`. The fixture's own operation tokens
(`complete_acquisition_cost`, `closing_minus_opening_positive`,
`opening_minus_closing_positive`) already matched the registry's `row_field`
values verbatim, so only the envelope moved and no value was invented.

**The branch that asserted its own opposite.**
`test_undeclared_inventory_leaves_manual_casilla_available_and_policy_is_replay_stable`
then still failed, and not for a fixable-by-shape reason. `_revision(declared=False)`
returned the bundled Modelo 100/2025 revision UNCHANGED -- and that revision now
ships three real inventory bindings, casilla 0181 among them. So the
"undeclared" branch handed the test a revision where inventory IS declared, 0181
arrived `input_kind=bound` owned by
`renta-2025-inventory-activity-acquisition-cost-0181`, and the caller-override
lock refused it. The lock was right; the fixture's name was the lie.

That branch was correct when written -- before `4b031370bb feat(inventory):
enforce source-owned calculation inputs` put those bindings in the registry,
"return the base revision" genuinely meant "no inventory declared". The registry
moved underneath it and the phrase stopped being true.

So the undeclared state is now BUILT rather than assumed: inventory-source
bindings are stripped and their three casillas handed back to `InputKind.MANUAL`
with no binding. That is the state the branch's name claims, and the tests about
manual availability now exercise it. The declared branch is untouched.

8 tests pass. Worth keeping in view: this is the third fixture this campaign has
found whose premise silently inverted when the registry gained content --
alongside the Modelo 190 reconcile that reported a clean match without comparing
a casilla, and the quickfile export that asserted a refusal the product had
stopped issuing.

### M184 socios were missing a required clave, and two clusters resolved as another campaign's

The remaining `ModeloExportError` (7) and `CalculationRevisionCatalogue` (4)
clusters both read `Modelo 303 export requires an explicit prior-domiciliation
election` and `rectificativa calculation revision requires context-bound
aggregate validation` -- the export-fragment campaign's M303 rectificativa
surface, already attributed in an earlier note. Left with their owner.

The residual `ModeloProfileReadiness` failures were a DIFFERENT requirement from
the colegio-concertado one fixed earlier, which is why they survived it. Probed
the refusal: `Clave del rendimiento (Modelo 184)`, grounded in LIRPF arts. 86
and 87 and Orden HAP/2250/2015 art. 3.

`attribution_entity_socios.<n>.clave` is `required = true` in the profile schema
with enum `A, C, D, E, F, G, I, J, K`, and the fixture's two socios carried nif,
name, share, assigned base, participe_clave and role -- but no clave. So the
readiness gate refused before any M184 row resolved.

The value was chosen from what the fixture itself declares rather than picked
for convenience: the entity is a `comunidad_bienes` with
`activities.description` set and IVA regimen general, so its socios receive
rendimientos de ACTIVIDADES ECONOMICAS -- clave `D` in the schema's own
vocabulary. Clave `C` (capital inmobiliario) would have been the wrong claim and
would additionally have dragged in the inmueble sub-block the row model gates on
that branch.

The tests assert nif and importe rather than clave, so any enum member would
have turned them green; that is exactly why the choice had to be grounded in the
profile rather than in what passes.

11 tests in the file pass, up from 9 passed 2 failed. The one remaining
readiness failure, `test_local_filed_303_compensation_updates_wallet_balance...`,
is M303 wallet and stays with the export-fragment campaign.

### A test guarding a registry that no longer exists, and where the guard actually lives

`test_emit_operator_json_success_refuses_an_unregistered_command` asserted that
the operator funnel refuses a command key with no registered schema, matching
"has no registered output schema". That string appears NOWHERE in production --
only in the test asserting it.

`validate_registered_result` consults no registry at all. It checks the result
is an `OutputSchema`/`OutputRootSchema` instance and revalidates it against
`type(result)` -- its OWN class. The `command` argument reaches only the error
messages. So a well-formed result emits under any key whatsoever.

The removal was structural, not an oversight, and the evidence is explicit:
commit `4b78f996de` retired the `SCHEMA_REGISTRY` mapping in
`core.json_contract`, and `test_json_schema_conformance`'s own docstring records
that "registry was retired and schema identity now lives on the command specs".
The binding cannot be re-checked at emit time without inverting the hexagonal
direction: `emit_operator_json_success` is in the application layer,
`COMMAND_SPECS` and `ResultSchemaSpec` are in `entrypoints`.

This is where the blast-radius rule mattered in the other direction. The
tempting reading was "a guard was lost, restore it" -- and restoring it means a
core or application module importing entrypoints, which the architecture
forbids and which no amount of test-greenness would justify. Measuring where the
binding is enforced BEFORE writing anything found it already enforced, statically,
by the conformance gate walking `COMMAND_SPECS`.

So the test now records the boundary as it actually stands: an unregistered key
with a well-formed result emits, the envelope carries that key, and the
command-to-schema binding is named as the static gate's responsibility. Written
down rather than deleted, so the stale expectation is not re-added by someone
reading the funnel and assuming it validates more than it does.

Also in this pass: `test_secure_objects_for_application_filing_bucket_refuses_`
`unready_runtime` carried the same three-way prose alternation
(`storage runtime is not ready|no active bucket session|route does not match`)
fixed earlier in a sibling file, and now asserts
`errors.storage.runtime.not_ready`. And the operator-output schema case matches
the live wording plus the command it names, since `OutputSchemaError` carries no
key or context to assert instead.

`test_operator_output` 8 pass; `test_runtime_repository` 5 pass.

The tree was unrunnable for part of this tick -- a peer had added a
`BUSINESS_BEARING_STATES` re-export to `domain/transactions/__init__.py` before
the constant existed, which broke every import of that package and with it the
whole suite. HEAD was healthy throughout; it was two uncommitted lines, and it
settled on its own.

### Text-casilla routing: one key for many rejections, and a casilla the registry deleted on purpose

**Two period_code cases.** Both matched prose (`period_code value 'T1'`,
`period_code value '1' does not match`) that is now the shared key
`application.filing.build_draft.errors.text_casilla_invalid`. Asserting the key
alone would have been a real loss: ONE key serves every text-casilla rejection,
so it cannot tell a malformed period token from any other bad scalar. Probed the
live refusal instead -- the context carries `casilla_id` and `data_type`, and
the wrapped registry error still carries the value verbatim
(`period_code value 'T1' does not match a supported filing-period form`). Both
cases now assert key, casilla, declared data_type AND the cause's value, which
is strictly more than the prose match they replace.

**A casilla deleted for a documented reason.** The third failure was
`input_key_unknown` on `tipo2.miembro-nif`, and the registry explains its own
deletion in a comment beside the replacement: "no such field exists at those
positions in any record of either bundled design epoch... Left in place it bound
a casilla named for the member to the bytes carrying the DECLARANTE's NIF." The
casilla was not renamed, it was WRONG -- it read the declarante's identifier
under a member's name.

The obvious repair, pointing the test at `tipo3.miembro-nif` (the member's real
NIF), was measured and rejected. That casilla is declared `text`, not `nif`, so
an invalid identifier passes it and the test's second half -- the whole point of
the case -- would have stopped asserting anything while looking green. The
`text` typing also looks deliberate rather than a gap: an atribución member may
be non-resident and carry a foreign identifier, which Spanish NIF validation
would wrongly refuse, and the row model carries `country_of_residence` for
exactly that population.

So the case was retargeted to `decl.representante-nif`, the casilla the registry
DOES declare as `nif`, which preserves the property it exists to prove -- a
nif-typed casilla reaches its scalar validator rather than Decimal parsing.
Verified by probe before editing: `12345678Z` is accepted and `12345678A` is
refused with `invalid NIF / NIE / CIF identifier:
errors.identity.nif_check_letter_mismatch`.

4 tests in the file pass.

### Long-tail triage: where the remaining failures actually live

A third full sweep is in flight. While it ran, the previous log was triaged
read-only rather than editing under a measurement, since several gates AST-scan
source from disk.

By area, the 452 failures concentrate hard: `application/modelo` 157,
`application/filing` 38, `domain/calculations/registry` 22, `entrypoints/cli`
20, `application/calculations` 19, then a long thin tail. Within
`application/modelo` the largest files are `test_prior_domiciliation_election`
(12), `test_export_output_paths` (10), `test_inventory_source_ownership` (7),
`test_m303_filing_evidence_validation` (6), `test_m184_multi_clave_export_parity`
(6), `test_export_iva_wallet` (6), `test_amend_kind_resolution` (6). Three of
those are already fixed in later ticks and several of the rest are M303 wallet
and domiciliation, the export-fragment campaign's.

Diagnosed ahead of the fixes, so the next passes are one edit each:

- `test_verification_m123_advisory` (4 failures) is NOT the stale-revision class
  -- `2024-y-siguientes` genuinely exists for Modelo 123. The predicate ID was
  renamed: the test looks for
  `modelo-123-2024-base-total-implica-retenciones-total` while the revision
  ships `modelo-123-2024-y-siguientes-base-total-implica-retenciones-total`.
  `next()` carries no default, so the miss surfaces as a bare `StopIteration`
  naming nothing -- worth giving a real message while fixing the id.
- `test_profile_export_values` fails on `KeyError: 'DP_APENOM_D'`, a missing
  export field key, plus a readiness refusal that may already be closed by the
  colegio-concertado and clave fixes.
- `test_amend_kind_resolution` mixes an M303-side amendment-evidence refusal
  with a real domain assertion --
  `Art109ActivityIncomeCoverageStatus.INSUFFICIENT is not PROVEN` -- which is a
  substantive coverage verdict rather than message drift.
- `test_export_output_paths` is half M303 prior-domiciliation (theirs) and half
  the `NoneType ... upper` crash already fixed in the Modelo 184 row validator,
  so its count should fall on its own.
- `test_modelo_202_modality_lifecycle` mixes a Modelo 202 required-bindings
  refusal with a Modelo 303 2020 revision miss.

The honest read: the clusters still standing that this campaign can touch are
now small and specific, and the bulk of what remains is either the
export-fragment campaign's M303/M390 surface or the Modelo 200 authority-grade
block already evidenced three times.

### A renamed predicate id, and a lookup that reported nothing when it missed

The Modelo 123 advisory tests failed with a bare `StopIteration` -- four of
them, naming neither what was sought nor what exists. The cause was a rename:
the test sought `modelo-123-2024-base-total-implica-retenciones-total` while the
revision ships `modelo-123-2024-y-siguientes-base-total-implica-retenciones-total`,
the id carrying the full revision stem.

The id was corrected against what the revision actually declares. The more
useful change is the second one: `next(...)` carried no default, so a missed
lookup raised `StopIteration` with no message at all. It now takes a default and
asserts, naming the revision, the id it wanted and the ids the revision declares
-- which is the difference between a diagnosis and a puzzle. Had that message
existed, this would have been a one-line read rather than an investigation.

The pattern was then measured rather than swept. Eleven test files use the same
defaultless `next(... verification_predicates ...)` lookup. Of those, the only
ones that had actually drifted are the three already fixed in this campaign
(Modelos 123, 151, 390); the remaining eight pass, meaning their ids are correct
today. Hardening all eleven would be defensive churn across passing files with
no failing gate to prove the change, so it was not done -- the two files this
campaign had already opened (M151, M390) were brought into line with M123 for
consistency, and the rest were left alone.

M123 4 pass; M151 and M390 7 pass together.

Measurement note: the third sweep was running during these edits. Its totals
therefore reflect a mixed tree and should be read as a floor, not a snapshot;
every fix in this campaign is established by running its own file, which is what
the per-fix runs above record.

### Hand-rolled stubs hid a resolver returning nothing, and sweep 3 is not a measurement

`test_profile_export_values` failed five ways on missing dictionary fields
(`DP_APENOM_D`, `DPNIF_C`, `DPFNAC_D`). None of those was the defect.

The file declared its own `_Fact` and `_Record` dataclasses standing in for the
domain models. `profile_fact_index` guards with
`isinstance(record, UserProfileRecord)` and returns an EMPTY index for anything
else, so the resolver produced `{}` and every assertion died on a KeyError
naming a field that was never missing. Measured before editing: 30 export-addressed
bindings resolve, `DP_APENOM_D` among them, yet the resolved mapping was empty.

Replacing the stubs with real `UserProfileFact` / `UserProfileRecord` is also
what `aeat-quality-gates` asks for -- stubs standing in for domain models are
exactly what it forbids -- and it immediately exposed two more fixture lies the
stub had been absorbing:

- `tax_residence.ccaa = "10"`. The schema declares that enum over community
  NAMES (`madrid`, `andalucia`, ...), never numeric codes, so `"10"` was a value
  the field cannot hold. With `madrid` the resolver returns `'madrid'` cleanly.
- `renta_filing.declaration_type = "1"` resolving to `Decimal('1')`. This one is
  DELIBERATE and documented: `_coerce_profile_fact_value` restores the Decimal
  and date types JSON drops on persistence, because a stored `"1"` is
  indistinguishable from a round-tripped `Decimal(1)`; values with an
  insignificant leading zero (postcodes) are carved out and stay `str`. The
  assertion now records that contract with its rationale rather than fighting
  it.

A related measurement worth keeping: six enum fields carry codes that become
Decimal under the same coercion (`codigo_provincia`, `marital_status`,
`participe_clave`, `naturaleza_inmueble`, `situacion_inmueble`,
`elected_withholding_pct`), so `"10"` and `"01"` take different Python types and
the renderer branches on type. That is a consequence of the documented design
rather than a fresh defect, and it is recorded here rather than acted on.

9 tests in the file pass, up from 4.

**Sweep 3 must not be read as a result.** It reports 571 failed / 121 errors
against sweep 2's 452 / 4, which looks like a large regression and is not one.
The errors are collection failures from a peer's IN-FLIGHT work:
`src/cadrumo/core/aggregation.py` is modified in the working tree adding
`BindingSourceKind.DESIGN_CONSTANT`, and it is not yet enrolled in the
source-kind-to-`OperatorActionAxis` map, so `application/state_projection`
raises at import and takes collection down tree-wide. Edits from this campaign
also landed mid-run. Both make the totals a mixed reading; every fix here is
established by running its own file.

The missing enrolment was deliberately NOT completed. Every `OperatorActionAxis`
member names something the operator must DO, and a design constant's value rides
on the binding selector -- the operator does nothing. Enrolling it under any
existing axis would hand operators a false instruction to satisfy a gate, so the
choice belongs to whoever is adding the kind.

### A blocked tree, a corrected over-claim, and a vocabulary gate honoured properly

**The tree is blocked by a peer's in-flight work, and completing it would be
wrong.** `src/cadrumo/core/aggregation.py` is modified in the working tree
adding `BindingSourceKind.DESIGN_CONSTANT`, unenrolled in the
source-kind-to-`OperatorActionAxis` map, so `application/state_projection`
raises at import and takes collection down across much of the suite.

The temptation is a one-line enrolment. The family's own docstring forbids it:
a record-design constant is "fixed by AEAT's own diseño de registro rather than
supplied by the taxpayer", and routing such a run through `manual_input`
"asked the operator to type AEAT's record format" and could "emit blanks behind
a valid digest, producing a file AEAT cannot parse" -- the exact defect this
family was created to remove. Every `OperatorActionAxis` member names something
the operator must DO, so ANY enrolment reintroduces that defect to satisfy a
gate. The kind needs either a no-action axis or an exemption, which is the
author's design call.

**An over-claim caught before it was made.** Three candidates in a row resolved
as owned or blocked -- `test_amend_kind_resolution` refuses only
`if work_unit.modelo == Modelo.M303.value`, and
`test_modelo_202_modality_lifecycle` fails on the Modelo 200 authority-grade
block already evidenced three times -- and the shape of that suggested the
accessible work was exhausted. Measured instead of asserted: 238 distinct files
fail in the last clean sweep and only 27 carry an M303/M390/wallet name. The
filename heuristic is weak in both directions, but the conclusion is not:
substantial accessible work remains, and sampling untouched files immediately
found some.

**Fixed from that sample.** `test_session_vocabulary_custody_split` declared
`application/auth/_sessions.py` in its custody inventory; a relocation promoted
that module to the public `sessions.py` and the declaration was not swept, so
the inventory named a file the tree does not carry. Every other declared path
was verified present before repointing it.

The file's second failure was the vocabulary gate proper: `_login_sessions` in
`login_session.py` is a bare session noun on the acceleration-receipt side,
where "session" means the live bucket session and nothing else. The gate accepts
qualifiers `profile, bucket, auth, browser, aeat, provider`, and the function
returns a `ProfileLoginSessionPort` -- so `profile` is both the accurate word
and an accepted one. Renamed to `_profile_login_sessions` across its 33
file-local references rather than widening the qualifier list, which would have
weakened the gate to fit the name instead of fixing the ambiguity. 10 tests
pass.

A lead for the next pass, surfaced while verifying: the `user_profile` suite
carries 16 failures asserting that fields "required by the profile schema but
not by the wizard key space" are unpinned, naming `attribution_entity_socios.*`
among them -- a required schema field with no wizard question is one an operator
cannot satisfy.

### Measured: the worktree is under continuous concurrent modification

Four separate peer relocations broke imports across the last few ticks --
`BUSINESS_BEARING_STATES` re-exported before it existed, `row_set_assembly`
promoted in `__init__` before the file was renamed, `DESIGN_CONSTANT` added
without its `OperatorActionAxis` enrolment, and now `KEY_SIZE` moved into
`crypto/aead.py` and `crypto/_crypto.py` while the package stopped re-exporting
it. Each took collection down across a wide slice of the suite.

Quantified rather than complained about: **59 files under `src` and `dev` are
modified and uncommitted right now**, and commits are landing every one to eight
minutes (16:01, 16:03, 16:04, 16:04, 16:04, 16:09). This is not a quiet tree
being hardened; it is a tree being actively rebuilt by several workers at once.

That bears directly on what "everything green" can mean here. A meaningful share
of any sweep's redness at a given instant is another worker's half-landed
relocation, not a standing defect -- which is why every fix in this campaign is
established by running its own file, and why the three whole-suite sweeps have
been read as floors rather than snapshots.

**The restraint was vindicated.** Last tick declined to enrol
`BindingSourceKind.DESIGN_CONSTANT` under an `OperatorActionAxis`, on the ground
that every axis names an operator action while a design constant is fixed by
AEAT's diseño and asks the operator for nothing -- so any enrolment would have
reintroduced the precise defect that family was created to remove. Commit
`ce7ed9c74e feat(registry): add the design_constant binding source and its
narrow mechanism` landed about thirty minutes later and the import now resolves.
The author completed their own design decision; guessing it would have written a
false operator instruction into the tree and then had to be unpicked.

Work this tick was blocked rather than productive: the schema-versus-wizard
parity gate (`test_profile_key_schema_required_parity`, which reports fields
"required by the profile schema but not by the wizard key space", naming
`attribution_entity_socios.*`) cannot currently be run -- it imports through the
storage package mid-relocation. It stays the next lead, and the registry domain
suite was left running to characterise its own failures.


### A real operator-facing defect: cold readers could not read the profile-key registry

Two fixes, one of them a genuine product break rather than test drift.

**The schema/wizard parity pin.** `test_profile_key_schema_required_parity`
named exactly one unpinned field: `attribution_entity_socios.clave`, declared
required by `a73d644d99 registry(modelo-184): declare the socio clave and
subclave schema fields`. Checked first that this predated the fixture work of an
earlier tick -- it fails in the last clean sweep too, so it is not fallout from
adding a clave fact to a test profile.

The gate offers two remedies, wire it into the wizard or pin it with a cause,
and its causes are machine-checked rather than asserted in prose. Every sibling
column of the same section (`nif`, `name`, `share_pct`,
`base_imponible_assigned`, `participe_clave`) is pinned `REPEATABLE_ROW` -- "one
column of a declared socio row" -- and that cause is verified against the
schema's own `repeatable` flag, which this section carries. `clave` is the same
kind of thing, so it is pinned the same way rather than given a bespoke excuse.
7 tests pass.

**The cold-reader break.** `test_cold_readers_agree_on_the_registered_key_count`
ran a fresh interpreter and died on
`ProfileKeysRegistrationError: profile keys are not registered`. This is not a
test artefact: reproduced directly in a cold process, both
`list_profile_key_records()` and `validate_profile_values({})` raised.

`keys_validation._ensure_profile_keys_registered()` imported
`..wizard.catalogue` for its registration side effect. That side effect has
moved: `wizard/compiler.py` defines `ensure_profile_keys_registered()` and calls
it at ITS own import, so importing the catalogue now registers nothing and left
the registry empty.

The repair is the compiler's own documented entry rather than another import for
its side effect -- it states it exists for "entrypoint calls at its own
initialisation" and that "an entrypoint may call this unconditionally without
ordering knowledge", and it returns early when the compiled tuple already
matches. The import stays function-local, as the surrounding docstring requires
for the cycle it breaks.

What makes this worth the words is the failure's shape, which that same
docstring predicted: "any module that touches the wizard catalogue first repairs
the import order for everything after it, so the failure only reaches an
operator through a cold entry point (workflow profile health) that does not."
In a warm suite it hides; the operator meets it. A cold reader now returns 81
keys, and the four registration-order tests pass.

