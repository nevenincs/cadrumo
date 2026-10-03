# Prorrata settlement, relation prefill, and row-set reconstruction

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-043` · **Topic:** [Aggregation and calculation services](../topics/aggregation-and-calculation-services.md)

<!-- preserved:article -->
## Scope

This chunk covers seven calculation-application modules (3,949 lines; 36,063 measured proxy tokens). I read the complete assigned ranges across seven bounded pages. This is static inspection; no calculation, filing, persistence write, registry load, or external contact was executed. Legal descriptions in comments and message keys are implementation context, not independent legal conclusions.

## Annual prorrata regularization

`ProrrataRegularizacionSourceResolver` constructs Modelo 303/390 regularization inputs from the selected revision’s registry bindings, current-year values, and prior observations. It re-confirms the revision stamp on each carried observation using the caller’s pinned authority operation. For multi-period feeds it sums deductible input IVA across all source periods except the last, then takes the settlement-only source facts from that final period. Missing observations or casillas leave required inputs unresolved. A register provisional percentage takes precedence; absent that, a stamped prior-year definitive percentage can supply the carry. If prorrata is applicable but no percentage is available, the resolver returns binding diagnostics rather than inventing a percentage. Observation-period projection (`src/cadrumo/application/calculations/prorrata_regularizacion.py`) Carry resolution (`src/cadrumo/application/calculations/prorrata_regularizacion.py`)

Applicability is visible when the current year’s declared volume without deduction is positive or an active register entry apportions deduction. The pure projection also accepts a ledger-volume rollup as advisory evidence, but the resolver’s own applicability call uses the merged current-year registry casillas and register entries. No-applicability resolves the declared regularization bindings to zero; otherwise the pure domain computation feeds the proposed amount only when exempt-without-right activity is positive and the provisional and definitive percentages imply a direction. The separate special-prorrata advisory compares the two supplied annual deductions against registry-resolved, year-effective parameters and returns a warning with the margin and legal reference. It does not alter the filing or block calculation. Applicability projection (`src/cadrumo/application/calculations/prorrata_regularizacion.py`) Special-regime advisory (`src/cadrumo/application/calculations/prorrata_regularizacion.py`)

The current-year observation feed is revision-gated and provenance-carrying, and the resolver accepts a preselected registry snapshot to avoid reselecting across authority generations. The main trace to verify is the caller’s treatment of caller-supplied current-year values and ledger rollup evidence: confirm they originate from the selected calculation’s resolved registry casillas and the intended ledger classification rather than an untrusted override. The implementation separates advisory ledger divergence from filing authority, but this chunk alone does not establish the upstream input admission contract.

## Relation-prefill and revision carry gate

The relation-prefill source resolver enumerates needs from the target revision’s declared relations, gathers matching local observations, and drops any observation whose stored revision cannot be reconfirmed through the pinned operation. It returns values with source coordinates and provenance. Missing local inputs remain unresolved, while several no-obligation paths are explicit: periods strictly before the profile’s activity-start date, the specifically scoped first-year Modelo 202 cuota case, M111 periods explicitly attested as having no relevant withholding, and a profile-derived inapplicable leg of the mutually exclusive M130/M131 pair. Missing or malformed profile data generally leaves requirements in scope. Requirement scoping (`src/cadrumo/application/calculations/relation_prefill.py`) Local-store resolution (`src/cadrumo/application/calculations/relation_prefill.py`) Resolver boundary (`src/cadrumo/application/calculations/relation_prefill.py`)

Unresolved relations are separated according to their declared consumption: formula-fed, orphaned, or bound. The actionable bound-carry diagnostic narrows further to in-scope dateable requirements filed by the taxpayer and excludes formula inputs and the IVA-wallet-owned carry. Diagnostics group multiple facts from one absent filing so one root cause is not repeated per relation. The “absent bound carry declares zero” text describes the downstream slot semantics assumed by that advisory; this function itself leaves unresolved relation values without a resolved value. Follow-up should trace the consumer/materializer to confirm that the described zero behavior and corresponding warning remain aligned. Consumption partition (`src/cadrumo/application/calculations/relation_prefill.py`) Result assembly and diagnostics (`src/cadrumo/application/calculations/relation_prefill.py`)

The shared carry gate independently reselects the law-determined revision for the persisted source coordinates. Matching stamps pass; divergent or indeterminate selection refuses the carry. A broad exception is caught and reduced to the exception type in the outcome, which preserves fail-closed behavior but limits diagnosis. That is an observability consideration rather than evidence that a stale carry is accepted. The separate Modelo 202 helper selects the applicable revision by filing context, compares it with the supplied snapshot, then chooses only inactive-period relation bindings with the expected source model and relation kind. Shared revision gate (`src/cadrumo/application/calculations/revision_carry_gate.py`) Modelo 202 relation defaults (`src/cadrumo/application/calculations/relation_prefill_m202.py`)

Registry failure facts are mapped into typed operator preconditions. Declared taxpayer/model failures produce a profile-edit action; filing-year-scoped query failures produce a model-description action; other listed query, snapshot, and tree conditions map to a no-recovery safety outcome. This keeps action policy in the application layer and does not fabricate command strings. Typed failure mapping (`src/cadrumo/application/calculations/registry_preconditions.py`)

## Row-set assembly and verification coordinates

The row-set assembler is a typed bridge from binding-indexed Detalle cells to observations for withholding, foreign assets, attribution, Modelo 193 expenses, and Modelo 296. It takes a selected snapshot at the application boundary, dispatches only a closed set of grouping kinds, looks up each binding’s typed row selector, groups cells by positive row index, and validates each constructed observation. Unknown binding IDs are ignored so a stale cell from another revision is not silently projected into the current observation. The module explicitly does not decide source ownership or persist the resulting records. Snapshot assembly entry point (`src/cadrumo/application/calculations/row_set_assembly.py`) Grouping and cell projection (`src/cadrumo/application/calculations/row_set_assembly.py`)

The per-source mappings preserve material distinctions such as an absent integer fact versus an explicitly declared zero, and Modelo 190/193 withholding refuses a missing or unsupported clave. Modelo 720 does not invent Spain as the foreign-asset country; its typed observation must receive a country. Other fields have deliberate design defaults, including filing-year-end dates and some classification/currency codes. Row validation errors become a typed refusal with row index and validation detail. Withholding row validation (`src/cadrumo/application/calculations/row_set_assembly.py`) Withholding and foreign-asset assemblers (`src/cadrumo/application/calculations/row_set_assembly.py`)

Two coercion details merit upstream contract checks. `_coerce_optional_int` converts through `int(Decimal(text))`, so a fractional numeric cell can be truncated before typed-model validation; `_coerce_iso_date` falls back to the filing-year-end default when a string is malformed. In addition, `_cells_by_row` overwrites an earlier value when the same row contains a duplicate binding cell. These are concrete local behaviors, but the assigned modules do not establish whether inbound adapters or registry/layout validators exclude those inputs. Confirm those admission invariants or prefer explicit refusal where they do not. Integer/date coercion (`src/cadrumo/application/calculations/row_set_assembly.py`) Row grouping (`src/cadrumo/application/calculations/row_set_assembly.py`)

Persisted verification-report catalogues use the same revision-carry check for every report and raise a model validation error if any producing coordinate cannot be reconfirmed. Verification-report coordinate gate (`src/cadrumo/application/calculations/verification_report_gate.py`)

## Implementation assessment

The strongest controls in this scope are the use of a generation-pinned operation for cross-period authority, explicit refusal of missing annual prorrata inputs, source-provenance-bearing relation folds, registry-declared consumption analysis, typed row-set reconstruction, and fail-closed revision checks. The principal follow-ups are verifying caller admission for prorrata evidence and relation suppression facts; aligning the absent-bound-carry warning with its downstream zero materializer; and confirming inbound row contracts reject fractional integer facts, malformed dates, and duplicate binding cells. No tests are included in the assigned files, and no runtime behavior is inferred from this static pass.

## Complete assigned-file coverage

- prorrata_regularizacion.py (1,297 lines) (`src/cadrumo/application/calculations/prorrata_regularizacion.py`)
- registry_preconditions.py (112 lines) (`src/cadrumo/application/calculations/registry_preconditions.py`)
- relation_prefill.py (1,389 lines) (`src/cadrumo/application/calculations/relation_prefill.py`)
- relation_prefill_m202.py (108 lines) (`src/cadrumo/application/calculations/relation_prefill_m202.py`)
- revision_carry_gate.py (106 lines) (`src/cadrumo/application/calculations/revision_carry_gate.py`)
- row_set_assembly.py (910 lines) (`src/cadrumo/application/calculations/row_set_assembly.py`)
- verification_report_gate.py (27 lines) (`src/cadrumo/application/calculations/verification_report_gate.py`)
<!-- /preserved:article -->
