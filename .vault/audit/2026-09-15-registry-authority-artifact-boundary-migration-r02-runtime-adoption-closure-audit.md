---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-15'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:4535119574003bb2884677e98c8ce81cfe2250349b4d17e0971e0b438561d02e'
related:
  - "[[2026-09-15-registry-authority-artifact-boundary-lane3-integration-review-audit]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `migration r02 runtime adoption closure`

## Scope

Session `migration-r02-runtime-adoption-closure`. Closure of the published-authority adoption migration: `src` tests moved off the dev-compiled authority onto the published generation, which exposed runtime defects, stale product declarations for retired dev caches, a broken import-gate harness, and moved-test ratchet entries. Product fixes are authorized within this migration boundary. Published generation at audit start: `21a1e0bdd5d410d1df0f6e0df67226c6af72cfe6a5f488347fa8d324e9867f1c` (previous `2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66`). A read-only diagnosis compared authored source, the dev-compiled candidate, and both generations: publication preserved content; the newly exposed failures are runtime findings.

## Findings

### f-303-settlement-period | critical | Modelo 303 settlement check selects undeclared period 0A, refusing every 303 calculation

Affected operation: every Modelo 303 calculation via `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` (reached from `src/cadrumo/application/modelo/calculate_input.py:355` and `_edit_execution.py:311`), plus `prorrata_regularizacion_advisory.py:361`, `revision_persistence.py:843`, `prorrata_register/seed.py:357`. Source: `src/cadrumo/domain/iva/m303_settlement.py:34-39`. Observed: `is_m303_annual_settlement_period` raises for 2026/1T and 2026/4T on both generations; `test_first_active_m303_period_allows_create_and_calculate` fails. Expected: 303 declares only quarterly/monthly periods (authored since commit a8f31b43be, RD 1624/1992 art. 71.3; `0A` belongs to Modelo 390); settlement must be derived from the period being calculated. Filing consequence: 303 cannot be calculated. Smallest repair: select the covering revision for the calculated period and derive the terminal settlement period from its declared periods; monthly period 12 only if grounded. Disposition: in progress.

### f-145-communication-period | critical | Modelo 145 communication creation always refuses

Affected command: `m145_create` (`src/cadrumo/entrypoints/cli/_modelo_m145_cli.py:61`) via `create_m145_communication_record`. Sources: `src/cadrumo/application/modelo/m145_communication.py:112` requires exactly one period token and ignores the requested `M145CommunicationPeriod`; `src/cadrumo/core/period.py:386` rejects `comunicacion`, so snapshot scope refuses at `src/cadrumo/domain/calculations/registry/snapshot.py:271`. Observed on the published generation; the same `comunicacion` PeriodError also breaks the cross-period dependency inventory for declared 2026 target modelos. Expected: 145 revision `2012-01-31-y-siguientes` declares `comunicacion` and `variacion` (RD 439/2007 art. 88); creation for a declared requested token succeeds. Filing consequence: 145 communications cannot be created. Smallest repair: contract uses the requested declared token; period typing reuses an existing typed non-periodic mechanism if one exists, else precise refusal and a design blocker. Disposition: in progress.

### f-dana-projection-window | high | DANA cuota reduction resolves outside its legal window

Fact `rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada` (valid 2024-11-13 to 2024-12-31, no support boundary) is projected beyond `valid_to` by `src/cadrumo/domain/calculations/registry/facts/resolution.py:390-396`, resolving 0.25 for 2025-12-31 and 2026-12-31 in compiled and published generations; `_dana_reduction_is_available` (`src/cadrumo/domain/iva/m303_regimen_simplificado.py:122-143`) returns True for 2025+. Expected: RDL 7/2024 art. 11.2 applies only in 2024. Filing consequence: simplified-regime year-end calculations demand DANA evidence outside the window and, if supplied, apply a 25% cuota devengada reduction outside the law (under-declaration). Smallest repair: determined by the governing projection contract (shared rule respecting authored `valid_to`, or a grounded support boundary with consumer refusal meanwhile). Disposition: in progress.

### f-carry-mapping-revision | high | Modelo 303 carry ingress refuses 2026 because the mapping fact names revision 2025

`src/cadrumo/domain/.../m303_carry_ingress.py:140` raises `registry.registry_resolution_unavailable`: for 303/2026 the selected revision is `2026-y-siguientes` while fact `modelo-303-carry-disposition-verification-mapping` declares revision `2025` (303/2025/4T is consistent). Observed in `test_filed_observation_capture_promotes_previous_303_into_recurrence_history` and about 36 related ingress refusals. Filing consequence: prior-period carry cannot be ingested for 2026. Smallest repair: to be determined between authored mapping data and resolving the mapping through the temporal projection contract. Disposition: in progress.

### f-test-support-empty-facts | high | Test support validated snapshots against an empty governed-fact catalogue

`src/cadrumo/domain/calculations/registry/tests/snapshot_support.py` built a fixture authority from a published-tree view with no facts, which `ValidatedRegistryAuthority._cached_snapshot` registered as the fact scope, producing 67 "governed fact 'm130-retenciones-output-routing' is not registered" failures. No runtime impact. Disposition: fixed in test support (published-tree views validate inside the leased operation; profile supports use `published_snapshot`); ledger C001 shows the error gone.

### f-test-invented-category | low | Tests use a spending category the registry never declared

`test_iva_operation` is used as `category_id` in `_verify_ledger_drift_gate_support.py:158`, `test_modelo_303_deductible_evidence_gate.py` and bucket-aggregation tests; it was never authored. Preflight refusal at `preflight.py:375` is correct. Disposition: open (tests must use a declared category).

### f-retired-dev-caches | medium | Product settings and storage declarations describe dev-compiler caches

`VALIDATION_VERDICT_CACHE` / `Settings.cadrumo_validation_verdict_cache_dir` removed from the product with the dev compiler owning its directory (`dev/registry/compiler/verdict_cache.py`). `REGISTRY_DISK_CACHE` / `Settings.cadrumo_registry_disk_cache_dir` pending the same retirement after reader confirmation. Storage-liveness gate also reports corpus-text-cache and registry-disk-cache without consumers and live-state.iva-wallet, root-fallback-database, bucket.db-file as unbacked; `.env.example` carries unread keys `CADRUMO_IVA_CATALOGUE_FILE`, `CADRUMO_M210_ENGINE_LIVE`, `CADRUMO_MANUALS_REVIEW_REQUIRED`. Disposition: in progress.

### f-import-harness-pythonpath | high | Import-gate loadability probe shadows harness support, so planted-defect tests cannot detect

Real-recipe planted-defect tests in `dev/tests/test_import_quality_gate.py` fail with `ModuleNotFoundError: cadrumo.tests.module_target_inventory` because the probe subprocess places the fixture's empty `src/cadrumo` first on PYTHONPATH (`dev/quality/import_load_probe.py`). Disposition: in progress.

### f-prorrata-casilla-44-binding-key | medium | Prorrata regularizacion tests cannot find the casilla-44 binding key

`test_prorrata_regularizacion.py:250`, `:283`, `:315` raise `KeyError 'modelo-303-prorrata-regularizacion-casilla-44'` and `:630` expects "casilla 44" in the advisory message. Probe: the binding exists in published 303/2026/4T, but `casillas_by_binding` (`src/cadrumo/domain/calculations/registry/binding_targets.py:42-50`) keys only bindings named by a bound casilla, and this binding writes through `regularizacion_output`; the advisory message now reads "destino declarado por registry". Not caused by the settlement repair. Owner of 303 binding/casilla wiring or the prorrata advisory message must decide whether the test expectation or the wiring is stale. Disposition: open.

### f-prorrata-ledger-rollup-empty | medium | Declared-volume ledger rollup includes no ledger entries

`test_prorrata_regularizacion.py:368`, `:417`, `:463`, `:502`, `:542`: `ProrrataDeclaredVolumeLedgerRollup` returns `included_ledger_ids=()` and ledger volume 0 (built at `src/cadrumo/application/calculations/prorrata_regularizacion.py:426`). Not caused by the settlement repair. Owner: prorrata rollup and ledger classification. Disposition: open.

### f-moved-test-ratchet | medium | Four ratchet entries remain for the moved core test_irnr module

`cadrumo.core.tests.test_irnr` moved to `src/cadrumo/domain/calculations/registry/tests/test_irnr_registry_tokens.py`; four core-is-innermost entries remain and count as blocking retirement candidates because `_valid_retirement` in `dev/quality/import_health.py` requires composition-integrity evidence with no producer. Entries are not removed by policy override. Disposition: pending harness repair and owning evidence path.

## Recommendations
