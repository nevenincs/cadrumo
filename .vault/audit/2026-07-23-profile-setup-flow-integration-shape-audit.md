---
tags:
  - '#audit'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-07-23-tui-wizard-substrate-adr]]"
  - "[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]"
  - "[[2026-07-23-tui-wizard-substrate-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-setup-flow` audit: `taxpayer profile integration shape and ADR grounding audit`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### taxpayer profile integration shape and ADR grounding audit | {level} | {summary}

     followed by a paragraph carrying the detail. taxpayer profile integration shape and ADR grounding audit is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

## Context

## Provenance and method

Produced by a 96-agent discovery pass (83 haiku Explore agents across 12 profile-integration domains, multi-vector; 12 sonnet per-domain syntheses; one high-effort global synthesis) over the worktree, run because both profile-wizard ADRs were authored while vaultspec-rag was down and therefore ungrounded. All findings are rg/direct-read evidence, NOT semantic-search-verified. A rag confirmation pass is required before either ADR is finalized. Full raw map retained as the workflow artifact (run wf_0d15a538-7d0). ~10.2M subagent tokens, 0 agent errors, 2 empty results absorbed.

## 1. Executive shape

The taxpayer profile is a layered fact system with three representations that must stay in lockstep: (a) the persisted shape `UserProfileRecord`/`UserProfileFact` (`domain/user_profile/_values.py`) - an ordered tuple of effective-dated facts, encrypted per bucket, governed by one schema authority compiled from `_data/registry/cadrumo/user_profile/schema.toml` (~14-15 sections); (b) the calc/deadline-facing typed model `TaxpayerProfile` (`domain/deadlines/_models.py`), built only by `taxpayer_profile_from_mapping` and carrying cross-field legal validators; (c) the narrower `domain/contribuyente` projections (`TaxResidenceProfile`/`RentaFamilyProfile`, `family.py` minimo math) whose composition boundary against `TaxpayerProfile` is UNRECONCILED (top open question). Every write funnels through one authority (`ProfileLifecycleService`, sequenced by `ProfileRepository`, co-emitting `BucketEventType.PROFILE_*`). The wizard (`application/wizard/_catalogue.py` `SETUP_FLOW`/`WIZARD_FLOWS`, ~70-76 `profile_key` questions) is the sole interactive authoring surface and the direct redesign target - and was the least-traced surface in this pass.

**True blast radius:** the profile schema field PATH is a load-bearing string contract read by exact dotted-path lookup from 100-150+ `source="profile"` registry TOMLs, the wizard catalogue, four locale catalogues, the applicability/schedule engine, the derived-fact injectors, and the MCP harness. Renaming/restructuring one field without an atomic registry-contract-validated sweep silently blanks a calculation, deduction, or gate. The octopus is one nervous system (the schema-path string), not many independent tentacles.

## 3. Canonical authorities (route through and extend, never fork)

- Persisted shape: `UserProfileRecord`/`UserProfileFact` (`domain/user_profile/_values.py`)
- Schema authority: `ProfileSchemaDefinition`/`ProfileFieldDefinition` from `schema.toml`
- Calc-facing model: `TaxpayerProfile` (`domain/deadlines/_models.py`, re-exported `taxpayer_model.py`)
- Fact->model constructor: `taxpayer_profile_from_mapping` (`domain/deadlines/_profiles.py`)
- Fact<->consumer projection: `projection_for_taxpayer`/`record_to_path_values`/`facts_to_values` (`application/user_profile/_projections.py`)
- Mutation authority: `ProfileLifecycleService` (`application/user_profile/_lifecycle.py`), sequenced by `ProfileRepository`
- Active-profile identity: `resolve_active_bucket_id`/`BucketPointer`, via `active_profile_pointer_transaction`
- Wizard catalogue: `SETUP_FLOW`/`WIZARD_FLOWS` + `WizardQuestion.profile_key` (`application/wizard/_catalogue.py`)
- Wizard key registry: `compile_profile_keys`/`register_profile_keys`/`ProfileKey` (`domain/contribuyente/_keys.py`)
- Registry binding resolver: `resolve_profile_sourced_bindings` (`application/modelo/_profile_binding.py`), enrolled via `ProfileSourceResolver`
- Applicability: `derive_modelo_applicability`/`ModeloApplicabilityRule.evaluate` (`domain/calculations/registry/_applicability.py`)
- Readiness gate: `require_profile_ready_for_modelo_work` (`application/modelo/_profile_readiness_gate.py`)
- Registry contract validator: `validate_user_profile_registry_contract` (`domain/user_profile/_registry_contract.py`)
- Identity checksum: `validate_spanish_tax_id`/`validate_identity`/`nif_check_letter`/`SubjectTaxId` (`core/identity/`)
- Descendant round-trip: `descendant_facts_from_list`/`descendant_list_from_facts` (`domain/contribuyente/_descendant_facts.py`)
- Censo derivation: `CensoSyncService.bound_raw_afectacion_ratio` (`application/user_profile/_censo_sync.py`)
- Event taxonomy: `BucketEventType.PROFILE_*`/`CENSO_*` (`domain/buckets/_event.py`)
- Portable export: `serialize_profile_bundle`/`deserialize_profile_bundle` + `UserProfilePortableExport`
- Representation (SEPARATE, not a profile fact): `ApoderadoService`/`ApoderadoConfiguration` (`application/auth/_apoderado.py`) - own encrypted namespace

## 4. Redesign-impact invariants (ranked)

1. Registry binding selector paths (100-150+ `source="profile"` TOML) - a field-path rename needs an atomic registry-contract-validated sweep of every binding in one commit.
2. Derived-fact injectors in `_profile_binding.py` (`_inject_derived_marriage_facts`, `_family_facts`, `_minimo_descendientes_facts`, `_anualidades_eligibility_facts`, `_autonomic_deduccion_facts`, `_state_attribution_facts`) encode LIRPF art 58/61/64/75/81/81bis/82, Madrid DL 1/2010, M303 state-attribution from raw fact shapes - wizard restructuring must keep the exact input shapes or update injectors atomically, else a mandated deduction silently blanks.
3. Parallel profile representations - exactly one derivation path per fact; reconcile the `domain/contribuyente` vs `domain/deadlines` boundary before touching descendant/family/CCAA fields.
4. Four-way wizard `profile_key` <-> `schema.toml` path <-> `wizard.setup.profile.*` in all four locales <-> registry selector must move together; gates: `python -m cadrumo.locales scaffold --check` and `validate_user_profile_registry_contract`.
5. Sole-mutation-writer discipline (`ProfileLifecycleService` + `PROFILE_*` co-emission, pinned by `test_event_emission_contract.py`) - any new write path routes through it and emits the event.
6. Cross-field legal validators on `TaxpayerProfile` fire at MODEL CONSTRUCTION - a checkpoint/staged flow must never construct an invalid intermediate model nor relax the checks (sharpest checkpoint-UX tension).
7. Duplicated applicability gating - `derive_modelo_applicability` called from both `_work_create_policy.py` and `_profile_readiness_gate.py`; do not add a third; confirm redundancy before consolidating.
8-14. Active-profile pointer single writer; censo->vivienda_office->ledger ratio guard chain; identity checksum boundary; cross-profile tax-id uniqueness (`_refuse_duplicate_tax_id`); portable-export versioning; MCP `TAX_ID_FACT_PATH` constant; `tema-profile.toml` still `draft` (no taxpayer-facing profile glossary ships).

## 5. ADR reconciliation verdicts

### Substrate ADR (tui-wizard-substrate)
- Extend the single wizard authority - CONFIRMED (one catalogue, one key registry; no second prompter).
- Dynamic copy assembly - PARTIALLY CONFIRMED. schema<->locale leg real and gate-enforced; the BOE/AEAT legal-CORPUS leg is UNSUPPORTED for wizard copy (corpus feeds registry calculation legal_refs, not question text). Narrow to schema + locales (+ terminology concepts) or design corpus-per-question fresh.
- Encrypted checkpoint (D4) - UNCONFIRMED/gap. No canonical partial-state checkpoint exists; closest is `persist_patch`/`set_active_fields` writing directly to the live encrypted `UserProfileRecord`. Collides with invariant #6. Scope to incremental `UserProfileFact` writes via `set_active_fields` (recommended) or design a separate draft object reconciled with the validator/readiness boundary.

### Flow ADR (profile-setup-flow)
- Extend-and-resequence - CONFIRMED (`run_flow` `visible_when`/`_condition_satisfied`).
- Cotejo against censo + G313 - CHALLENGED (the one assumption the map cannot support as written). Live compare/apply against an AEAT censo snapshot was RETIRED (2026-07-11 censo-operator-manual-enrolment ADR); no live snapshot/compare/apply in production; `CENSO_REFRESHED`/`CENSO_APPLIED` may be dormant; `CensoSnapshot`/`CensoSnapshotService`/`CensoFactSet` NOT corroborated as live code. Real authority is `CensoSyncService.bound_raw_afectacion_ratio`. Scope cotejo to reconciliation against an operator-supplied G313 FILE via `file --file`, not a live pull; confirm CensoSnapshot existence and read the 2026-07-11 ADR before finalizing.
- Reuse core.identity - CONFIRMED (single checksum authority, ~15+ sites).

## 6. Coverage gaps / manual-verification list (before planning)

High priority: read the wizard internals in full (`_catalogue.py`, `_persistence.py::persist_answers`/`save_answers_to_profile`, `_prompter.py`, `_widgets.py`, `_status.py`) - least-traced surface; reconcile `domain/contribuyente` `family.py` minimo math vs `_profile_binding.py` injectors (possible duplication); read the 2026-07-11 censo ADR text directly; confirm whether `CensoSnapshot`/`CensoSnapshotService`/`CensoFactSet` still exist as live code.

Medium: full enumeration of the `source="profile"` TOML set before any rename; apoderamiento surface completeness; collaborator records; sandbox CLI cluster liveness; `ca.yml`/`hu.yml` full parity via `scaffold --check` + a green `test_parity.py`/`test_locale_translation_honesty.py` baseline; CENSO_DECLARATION_* emission wiring; the vivienda_office<->ledger ratio-mismatch exception; precedence order inside `require_profile_ready_for_modelo_work`; the two applicability call sites' relationship.

Lower/background: workflow `TaxpayerProfile` protocol; output-language consuming site; effective-dated fact validity-window consumer; descendant NIF validate-at-write; full profile-domain terminology concept sweep; secure-storage internals; command-by-command CLI field-edit enumeration; a grimp runtime import-graph pass over profile-touching modules.

**Process gap:** produced with vaultspec-rag unavailable (rg/direct-read only); run the semantic-search confirmation pass before finalizing either ADR.

## Follow-up actions

- tui_substrate: amend D2 (narrow copy sources) and D4 (map checkpoint onto UserProfileFact/set_active_fields or a reconciled draft); name the canonical authorities as binding constraints; read wizard internals in full.
- profile_flow: rescope cotejo to G313-file reconciliation (no live pull, no CensoSnapshot compare/apply); cite the two mechanical gates as the rename-sweep enforcement; preserve the derived-fact injector input shapes; narrow the legal zone to legal_refs + terminology (not corpus prose); route apoderado to ApoderadoService.
- Both: run the RAG confirmation pass once the service is up; do not advance to planning until the high-priority manual-verification items are closed.
