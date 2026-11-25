---
tags:
  - '#reference'
  - '#per-activity-estimation-regime'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:593b2b53dd4d32606cbe26b02ee7ad070bd26593fc354865902f5e5c434a4f0e'
related: []
---

# `per-activity-estimation-regime` reference: `Readers of the taxpayer-wide IRPF estimation regime`

This is an inventory of everything that reads `irpf.estimation_regime` at tree 7b83940f05: the declaration, the governed vocabulary, the typed carriers, the registry predicates and the consumers. It was built with a targeted grep (`irpf.estimation_regime`, `irpf_estimation_regime`, `"estimation_regime"`) over `src/` without tests, plus `src/cadrumo/_data`. Semantic search was unavailable (the vaultspec-rag MCP failed to connect), so this inventory is exhaustive for those spellings only.

## Summary

### Declaration and vocabulary

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:913` declares `irpf.estimation_regime`. It is a single enum on the `irpf` section, `effective_dated = true`, with values `directa_normal`, `directa_simplificada` and `objetiva`, `model_selectors` and `schedule_predicates` set, and legal refs LIRPF 28/30/31 and RIRPF 30/31.
- `schema.toml:870` holds the `activities` section, `repeatable = true` and `effective_dated = true`. Its fields are `description` (required) and `iae_epigraph` only. It has no regime, start date or principal marker. The censal alta date is a single scalar, `censo.activity_start_date` (`schema.toml:357`).
- `src/cadrumo/domain/calculations/registry/irpf_regimes.py:218-300` resolves the vocabulary from the governed fact `src/cadrumo/_data/registry/aeat/facts/0125-irpf-regime-vocabulary.toml` (`require_irpf_estimation_regime`, `irpf_estimation_regime_tokens` and the three single-token accessors). It needs no change; per-activity values reuse it.

### Typed carriers (taxpayer-wide scalar)

- `src/cadrumo/domain/user_profile/setup_answers.py:257,433-442`: the setup answer `irpf_estimation_regime`, validated against the vocabulary.
- `src/cadrumo/domain/deadlines/profiles.py:173,285,302` and `src/cadrumo/domain/deadlines/models.py:324-333,586,633`: the deadline profile carries one `irpf_estimation_regime`.
- `src/cadrumo/domain/calculations/registry/schedules.py:29-33` maps the profile path onto that carrier attribute for schedule predicates.

### Registry predicates

- `src/cadrumo/_data/registry/aeat/modelos/131/revisions/{2024,2025,2026}/deadline_windows/0001-declarations.toml`: each quarterly window applies when `irpf.estimation_regime equals objetiva`. In a mixed year this is true only if the scalar says objetiva, so either 130 or 131 is lost.
- `src/cadrumo/_data/registry/aeat/modelos/130/revisions/*` and `src/cadrumo/_data/registry/aeat/facts/0149-m347-estimacion-objetiva-operation-scope.toml` also name the path or token.
- `src/cadrumo/domain/calculations/registry/applicability.py:187` and `applicability_models.py:450` hold `required_estimation_regimes`. **An absent regime is read as `directa_normal`** (`applicability_models.py:450`), which is a default that states a fact. It is out of this decision's scope but is noted, because a per-activity reader must not copy it.

### Consumers (14 application/domain modules)

| Module | What the regime decides | Mixed-year behaviour today |
| --- | --- | --- |
| `src/cadrumo/application/aggregation/inventory.py:100-160` | which activities count as direct for Anexo D inventory rows | refuses (`activity_books_do_not_match_activities` / `estimation_regime_undeclared`) |
| `src/cadrumo/application/modelo/profile_derived_facts.py:161` | whether casilla 0169 (cash criterion) is stated | taxpayer-wide; wrong when only some activities are direct |
| `src/cadrumo/application/aggregation/renta_imputation.py:165,224` | whether a regime is declared for the year (imputation gate) | refuses on two dated values in one year |
| `src/cadrumo/application/calculations/relation_prefill.py:324-331` | prefill excludes 131 when direct and 130 when objetiva | drops one modelo that is genuinely due |
| `src/cadrumo/application/overview/calendar_warnings.py:74-84` | objetiva-unset calendar warning | taxpayer-wide |
| `src/cadrumo/application/overview/explain.py:163,187` | explanation key | taxpayer-wide |
| `src/cadrumo/application/wizard/catalogue.py:137-182` and `wizard/setup_tax_sections.py:143-210` | setup question and its choices | asks once per taxpayer |
| `src/cadrumo/application/aggregation/_retencion_rate_advisory.py:307-322` | withholding-rate advisory branch | taxpayer-wide |
| `src/cadrumo/application/modelo/_objective_estimation_advisory.py:194` | objetiva exclusion-magnitude advisory | taxpayer-wide |
| `src/cadrumo/application/aggregation/activity_asset_disposal_projection.py:446,485` | asset disposal route (excess under directa vs agrarian módulos) | reads the scalar on the period end; the asset's own activity is already known at `:449` |
| `src/cadrumo/application/actividad_asset/activity_asset_executors.py:167` and `actividad_asset/modality.py:24-25` | normal vs simplificada amortisation modality | taxpayer-wide |
| `src/cadrumo/application/invoices/source_observations.py:352-363` with `domain/calculations/registry/m347_operation_scope.py:56-107` | Modelo 347 scope for objetiva filers (art. 32.b RD 1065/2007) | taxpayer-wide |
| `src/cadrumo/domain/deadlines/profiles.py` / `models.py` | obligation applicability (130/131) | one of the two quarterly modelos |
| `src/cadrumo/domain/calculations/registry/applicability_models.py:450` | modelo applicability by regime | absent regime defaults to normal |

### Row machinery already available

- `src/cadrumo/application/user_profile/completeness.py:304` `profile_section_rows` groups indexed `activities.<n>.<field>` paths into rows, including an implicit unindexed row `""`. Any per-activity reader should use it rather than a new row walker.
- `src/cadrumo/application/user_profile/projections.py` `record_to_path_values(record, as_of=day)` yields the dated values on one day. `inventory.py:126-140` already samples a year on fact boundaries with it.
- No writer for indexed repeatable rows is established beyond what `2026-07-26-multi-activity-profile-adr` (proposed) describes. This record did not re-verify that gap.
