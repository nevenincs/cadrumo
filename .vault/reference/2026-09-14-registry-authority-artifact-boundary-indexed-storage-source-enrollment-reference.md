---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:27819f69598e2d882a01a3b798274bdf9342d00d22ee17456797f2ae0544b0af'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-remediation-result-reference]]"
  - "[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]"
  - "[[2026-08-04-profile-derived-selectors-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
---

# Authority source enrollment and runtime access map

## Summary

This reference grounds the next authority storage decision in live code as of 2026-09-14. The related remediation result owns historical performance values; this audit did not rerun those benchmarks. The working tree contains concurrent corpus/tooling changes, so locators describe inspected source rather than a clean release claim.

### The missing schema is the profile facts schema

The on-disk `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1` declares `cadrumo.user_profile`, version 6, sections, fields and derived selectors with legal references. `src/cadrumo/domain/user_profile/loader.py:39` loads it directly from bundled TOML, using a path/size/mtime cache at lines 52-66. `ProfileSchemaDefinition` remains the canonical typed contract at `src/cadrumo/domain/user_profile/schema.py:351`. These are declarations about profile facts, not taxpayer records.

Compilation already uses that schema indirectly: `dev/registry/compiler/validator.py:422` defaults to `load_user_profile_schema()` to validate model bindings, while `dev/registry/compiler/authority.py:110` does not inject a schema captured with the candidate. The input fingerprint collector checks an obsolete location under the AEAT root at `dev/registry/compiler/loader_fingerprints.py:232`. The actual schema is a sibling outside that root. Publication hashes AEAT files and evidence under corpus/manual roots at `dev/registry/pipeline/authority_publication.py:367` and `dev/registry/compiler/source_evidence_fingerprint.py:110`. It neither captures this sibling schema nor includes it in the compiled catalogues.

A read-only live Python probe imported the real fingerprint collectors and profile loader and inspected the published JSON. It exited 0: schema exists and loads as version 6; it is absent from registry fingerprints, outside the registry content root and absent from the evidence receipt; published catalogue keys contain no profile schema. This proves source enrollment is incomplete even though validation consumes the schema. It does not prove that all facts are missing.

### Governed tax facts are already enrolled

`dev/registry/compiler/fact_loader.py:34` strictly parses one governed fact with `GovernedFact.model_validate`, rejecting unknown top-level tables and authored provider identity. `dev/registry/compiler/fact_providers.py:84` owns provider compilation/fingerprints/reset/directories; registrations at line 380 include authored facts and model projections. `dev/registry/compiler/authority.py:174` loads authored facts before model validation and attaches the final provider catalogue at line 222. The Python schema participates in domain-code build identity through `dev/registry/compiler/build_identity.py:14`.

`src/cadrumo/domain/calculations/registry/authority_artifact.py:568` reconstructs governed facts from the published payload. The read-only artifact probe found 158 compiled governed facts; this observation is not an acceptance count. `uv run --no-sync pytest dev/registry/tests/test_fact_loader.py dev/registry/tests/test_fact_providers.py -q` exited 0 with 23 passing tests. These tests prove existing parser/provider behavior, not profile schema enrollment or a new backend.

### Hydration currently requires the entire graph

`src/cadrumo/domain/calculations/registry/authority_artifact.py:287` represents the full graph; decoding at line 528 constructs all facts, models, catalogues and evidence. `src/cadrumo/domain/calculations/registry/authority.py:132` stores those complete public fields and model indexes. Returning a full `ModeloDefinition` also exposes all its revisions. The next access contract must distinguish metadata, selected revision, selected fact and explicit full enumeration; a codec-only change would preserve eager reconstruction.

`src/cadrumo/domain/calculations/registry/governed_fact_scope.py:50` scopes candidate facts during validation. Artifact decoding loads facts and tax-ID vocabulary before model validation at `authority_artifact.py:564`. This establishes a dependency-order requirement for lazy decoding: required vocabulary must come from the same pinned generation, without recursive bundled loading.

### Publication and admission are distinct boundaries

`dev/registry/pipeline/authority_publication.py:162` captures receipts before and after full validation; line 351 rechecks immediately before publication. `src/cadrumo/domain/calculations/registry/authority_artifact.py:340` encodes and fully decodes before staging, fsync and replacement. `src/cadrumo/core/atomic_write.py:491` owns hardened sibling staging and replacement.

The current fixed artifact locator is `src/cadrumo/domain/calculations/registry/authority.py:583`. Shared runtime admission at `authority_artifact.py:386` checks file identity, retries changing reads and caches only successful immutable graphs. Capture identity is process-incarnation sensitive as well as generation-sensitive; preserve that distinction when handles become lazy.

Current `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py:264` rejects a digest-consistent malformed typed payload during open, because every component is decoded. Lazy loading necessarily changes this timing for unrequested typed payloads if all unsigned digests have been deliberately recomputed. Ordinary raw-byte corruption can still be rejected anywhere in the file at admission by a full-file digest. Full typed traversal before publication remains independently necessary; SQLite structural integrity is not semantic conformance or authentication.

### Package and resource obligations

`pyproject.toml:243` and line 345 pin the JSON artifact; exclusions cover AEAT authoring, not the sibling profile schema. `src/cadrumo/tests/test_wheel_content_boundary.py:309` checks archive contents. `dev/packaging/tests/test_installed_oracles.py:450` exercises artifact-only runtime, and line 579 exercises installed CLI/MCP corruption refusal.

`src/cadrumo/core/resources/bundled_data.py:51` retains an extraction ExitStack for the process. `bundled_path` at line 77 yields filesystem resources, while scoped `as_path` at line 98 has a shorter lease. SQLite connections require an authority-directory resource lifetime covering both the descriptor and referenced database. Normal filesystem wheel installs are the initial supported target; zip-import must not be claimed without a real resource-lifetime test.

`dev/registry/benchmark_authority.py:14` measures imports, authority hydration, first and repeated snapshots, public queries, enumeration and process memory. Its fresh-interpreter driver is at line 74. Command: `uv run --no-sync python -m dev.registry.benchmark_authority --runs 3`. It is currently observational rather than an authority performance acceptance gate.

### Consumer migration inventory

The exact-text production inventory identifies direct model traversal in these cohesive areas. Paths below are relative to `src/cadrumo/`; this is a code-search inventory, not a proof that no dynamic consumer exists.

| Area | Inspected files |
| --- | --- |
| Registry queries and metadata | `domain/calculations/registry/queries.py`, `profile_grounding.py`, `support_matrix.py`, `censo_modelos.py` in the same directory |
| Calculation and aggregation | `application/aggregation/service.py`; `application/calculations/binding_prefill.py`, `cross_period_clean_state.py`, `iva_compensation_annual_partition.py`, `iva_compensation_history.py`, `m303_carry_ingress.py`, `m303_regimen_simplificado_annual_summary.py`, `observations_repository.py` |
| Modelo operations | `application/modelo/_m210_agrupacion_renta.py`, `_m303_m349_reconcile.py`, `_required_binding_gate.py`, `calculate_input.py`, `data_inventory.py`, `local_observation_actions.py`, `m145_communication.py`, `projection.py`, `_registry_resources.py`, `registry_discovery.py`, `verification_cross_period.py`; `application/foreign_asset_thresholds.py` |
| Discovery | `application/live/expedientes.py`, `filed_data_capture.py`; `application/overview/calendar_warnings.py`; `entrypoints/cli/common.py`, `modelo_spreadsheet_cli.py` |
| Governed catalogues | `domain/categories/registry.py`; `domain/deadlines/festivos.py`, `recargo.py`; `domain/iva/_grounding.py`, `catalogue.py`, `country_vocabulary.py`, `establishment.py`, `lookup.py`, `place_of_supply.py`, `rates.py`, `recargo_equivalencia.py`, `verify.py`; `domain/auth/apoderamientos/catalogue.py`; `domain/calculations/registry/convenio.py` |
| Filing and evidence | `application/filing/runtime.py`, `draft_construction.py`; `application/corpus_search/citation_lookup.py`; `application/modelo/_work_review_assembly.py`; `adapters/outbound/aeat/sede/declarations_observations.py` |
| Revision-oriented semantics | `domain/calculations/registry/applicability.py`, `casilla_legal_citation_period.py`, `casilla_lineage_totality.py`, `cross_revision_divergence.py`, `formula_runtime_ops.py`, `revision_order.py`, `temporal.py`; `domain/portals/registry.py`; `domain/transactions/m210_income_classification.py`; `domain/user_profile/registry_contract.py` |

Every application-plan row must name one file or genuinely cohesive area; this inventory supplies the caller denominator and must be refreshed at implementation entry. Schema model validators that iterate their own revision members remain compiler/typed-validation obligations rather than lazy runtime consumers.

### Filing defaults omit the draft context

`src/cadrumo/application/filing/export.py:232` and `src/cadrumo/application/filing/export_verification.py:201` build a default provider with only the model ID. `src/cadrumo/application/filing/runtime.py:684` consequently chooses the latest open revision and invents its first supported year/period. Historical drafts can be compared with the wrong schema and refused as stale. This trace establishes a selection defect, not proof that an incorrect filing has been emitted. The contextful path at `src/cadrumo/application/modelo/export.py:1238` is the existing analogue to preserve. The next API must require the draft/capture coordinate for filing; unscoped latest inspection must not grant filing grade.

### Reproduced enrollment and parser gaps

`dev/registry/compiler/fact_providers.py:303` inspects only immediate TOMLs under top-level directories; the subsequent recursive walk is limited to registered roots. An isolated temporary `rogue/nested/0001-omitted.toml` was accepted by the real directory-ownership validator (probe exit 0). Its filename declares a fact fragment but no provider owns it. By contrast, descendants of the registered facts root are intentionally loaded recursively. `dev/registry/tests/test_authority_enrollment.py:101` still expects a child under the owned facts root to require separate registration. Running `uv run --no-sync pytest dev/registry/tests/test_authority_enrollment.py -q` exited 1 with 1 failed, 4 passed; the sole failure is `test_top_level_sibling_under_the_governed_root_requires_an_exact_provider_owner`, DID NOT RAISE. This is a current pre-existing contract contradiction, not a regression from documentation work.

The profile loader projects only three root members before strict model validation at `src/cadrumo/domain/user_profile/loader.py:86`. A temporary copy of the real schema with an added unknown top-level table loaded successfully through the real parser (probe exit 0). Strict Pydantic validation therefore does not currently make the TOML envelope strict.

Provider `lifecycle_components` is not consumed, and `inherited_identity_domains` is checked for nonemptiness rather than resolved into executable dependency receipts at `dev/registry/compiler/fact_providers.py:88` and line 196. Current full-source hashing protects model projections conservatively; these fields do not establish selective dependency correctness. The seven implemented family types are repeated across schema, query and result unions at `src/cadrumo/domain/calculations/registry/facts/schema.py:143`, line 390, and `facts/resolution.py:85`, line 191. No matching family-enrollment parity gate was found in the focused audit; that is an inventory finding, not proof that no indirect test exists.

`src/cadrumo/domain/user_profile/schema.py:143` and line 309 store legal references as descriptions. The existing `registry_contract.py` checks selector reachability, not complete profile legal-reference closure. The compiler input extension must validate declared references without inventing new legal applicability or changing profile requiredness policy. `src/cadrumo/domain/user_profile/values.py:236` ties stored profile acceptance to schema version; publication must preserve explicit schema version and existing secure migration/refusal behavior rather than silently upgrading user records.

### Profile-record construction has hidden schema access

`src/cadrumo/domain/user_profile/values.py:236` obtains the default schema version through the raw loader; record/snapshot validators at lines 248-276 also load it implicitly. Moving only the visible profile service calls would leave schema access during secure record deserialization. The new contract must supply the pinned schema explicitly through validated factories/context and retain schema-version mismatch refusal. It must not serialize taxpayer records into the public authority. `src/cadrumo/application/user_profile/projections.py:42` separately caches the default schema for process lifetime; this cache is not keyed by authority generation.

The raw loader has 22 production consumer/definition files in the exact-text inventory. Paths relative to `src/cadrumo/`: `domain/user_profile/loader.py`, `domain/user_profile/values.py`, `domain/renta/maritime_exemption.py`; `application/user_profile/overview.py`, `projections.py`, `section_rows.py`, `validation.py`; `application/modelo/_autonomic_deduccion_advisory.py`, `_required_binding_gate.py`, `profile_binding.py`, `profile_export_binding.py`, `profile_readiness_gate.py`; `application/auth/sessions.py`; `application/aggregation/atribucion_member.py`, `renta_ledger.py`; `application/wizard/status.py`; `application/diagnostics.py`; `entrypoints/cli/_modelo_discovery_rendering.py`, `_overview.py`, `common.py`, `config/_complete_setup_cli.py`, `config/_profile_inspect.py`. Development consumers are `dev/registry/compiler/validator.py` and `dev/locales/_registry_scanner.py`. The parser should move to development; semantic tests remain with the canonical profile schema. Existing test/support migration spans domain profile, profile application, modelo, auth, aggregation, wizard, secure persistence, CLI/TUI and development fixtures.
