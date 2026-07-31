---
tags:
  - '#audit'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ebb62e23d193a68f81076aaf5272ca9251ed8e0e40b3efcfb44b1b38b558e68e'
related:
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
---

# `arch-remediation-gates-ratchet` audit: `implementation review`

## Scope

Review of the repaired Import Linter ledger, the new ledger ratchet tests, and
the vault execution records for the gate-ledger repair plan. The review checked
that the broad application-to-adapters wildcard is absent, the remaining
module-level pins resolve on disk, the count-ratchet baselines match the
post-repair ledger, no plan metadata was added to runtime test code, and the
required gates run cleanly.

## Findings

No open findings.

### follow-up-profile-activity-test-boundary | low | application test no longer imports CLI test helpers

Reviewed the 2026-07-05 ratchet follow-up that rewired
`test_review_profile_activity_staleness` away from the CLI test-support
package. The test still provisions a real encrypted profile bucket and mutates
the relation-scoping `activities.description` fact through application
profile primitives; it no longer adds an application-to-entrypoints edge to the
layered contract. Focused pytest passed, and the layered linter rerun no longer
reports an application-to-entrypoints violation. The layered contract remains
red on the broader application-to-adapters inventory, so this is a boundary
reduction only, not program closure.

### follow-up-error-class-registration-boundary | low | application test no longer imports AEAT auth adapter

Reviewed the 2026-07-05 ratchet follow-up that rewired
`test_error_class_registration` away from the outbound AEAT auth adapter. The
certificate probe still builds a real PKCS#12 bundle and calls the application
`probe_provider_configuration` surface; the assertion now observes the
propagated `AeatError` through the registered `AUTH_AUTH_VALIDATION` code
instead of importing the adapter exception class. Focused pytest and ruff
passed. The layered linter rerun no longer reports
`application.tests.test_error_class_registration`, but the importlinter ledger
count remains above baseline at 850, so this is a targeted boundary cleanup
only.

### follow-up-ledger-import-errors-boundary | low | application ledger test uses local test support re-export

Reviewed the 2026-07-05 ratchet follow-up that removed the direct SQL storage
adapter import from `test_actions_import_errors`. The test continues to use
the real `SecureObjectRepository`, now obtained through the existing
`application.ledger.tests._action_test_support` support surface that the
neighboring ledger action tests already use. Focused pytest and ruff passed.
The layered linter rerun no longer reports
`application.ledger.tests.test_actions_import_errors`, but the importlinter
ledger count remains above baseline at 850, so this is another targeted
boundary cleanup only.

### follow-up-renta-classifier-size-budget | low | Renta expense classifier below callable budget

Reviewed the 2026-07-05 ratchet follow-up that extracted the repeated
`RentaLedgerAggregationIssue` envelope construction from
`_classify_renta_transaction` into `_renta_transaction_issue`. The classifier's
branch ordering, reason codes, and detail strings remain unchanged; the callable
line count dropped from 190 to 164, below the default 180-line budget. Focused
Renta aggregation tests and ruff passed. The codebase-size gate rerun no longer
reports `_classify_renta_transaction`, but it remains red on the other known
module and callable offenders.

### follow-up-evidence-confirm-size-budget | low | evidence confirm callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted invoice-date
resolution from `confirm_invoice_draft_from_evidence` into
`_resolve_confirmed_invoice_date`. The confirm flow still reuses the same draft
value, preserves the same missing-date refusal text and suggestion, and
delegates the catalogue write unchanged. The callable line count dropped from
183 to 175, below the default 180-line budget. Focused evidence-draft tests and
ruff passed. The codebase-size gate rerun no longer reports
`confirm_invoice_draft_from_evidence`, but remains red on the other known
module and callable offenders.

### follow-up-m145-cli-size-budget | low | M145 registration callable below budget

Reviewed the 2026-07-05 ratchet follow-up that moved the Modelo 145
state-transition Typer command closures from `register_m145_communication_commands`
into `_register_m145_transition_commands`. The command names, help text, actor
resolution, active-bucket guard, and emitted payload operations remain unchanged.
The registration callable line count dropped from 185 to 139, below the default
180-line budget. Ruff passed, and the M145 CLI integration suite passed with
`-m integration`. The codebase-size gate rerun no longer reports
`register_m145_communication_commands`, but remains red on the other known
module and callable offenders.

### follow-up-amendment-action-size-budget | low | amendment workflow callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted amendment draft
revision construction and filing-catalogue supersession updates from
`amend_modelo_revision` into `_build_amendment_draft_revision` and
`_build_amendment_filing_updates`. The public workflow still performs the same
baseline loading, amendment-kind guards, registry completeness gate,
verification/filed transitions, and side-effect persistence in the same order.
The callable line count dropped from 197 to 173, below the default 180-line
budget. Ruff passed, and the focused amendment flow/kind-resolution suites
passed. The codebase-size gate rerun no longer reports `amend_modelo_revision`,
but remains red on the other known module and callable offenders.

### follow-up-ledger-evidence-confirm-size-budget | low | evidence confirm CLI callables below budget

Reviewed the 2026-07-05 ratchet follow-up that moved the
`evidence_confirm` command body into `_run_evidence_confirm`, leaving the Typer
handler as a parameter bridge. The command still validates exactly-one evidence
reference, delegates to `confirm_invoice_draft_from_evidence`, renders the same
payload rows, and emits the same idempotent/next-action notices. The
`_register_evidence_confirm_command` callable dropped from 211 to 125 lines and
`evidence_confirm` dropped from 203 to 117, both below the default 180-line
budget. Ruff passed, and the real evidence-confirm CLI integration suite passed
with `-m integration`. The codebase-size gate rerun no longer reports either
ledger evidence confirm callable, but remains red on the other known module and
callable offenders.

### follow-up-review-package-build-size-budget | low | review-package build callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted review-package build
payload/line projection into the new `_modelo_review_package_rendering` module.
The `review_package_build` command still resolves the target revision, exports
the fichero-BOE draft, builds the package, and emits the same envelope shape;
only the final result projection moved out of the oversized CLI module. The
callable line count dropped from 199 to 179, below the default 180-line budget,
and the CLI module line count dropped from 1349 to 1332. Ruff passed, the real
review-package CLI integration suite passed with `-m integration`, and the new
rendering module is reachable from existing tests. The codebase-size gate rerun
no longer reports `review_package_build`, but remains red on the other known
module and callable offenders.

### follow-up-mcp-build-server-size-budget | low | MCP server builder below pinned budget

Reviewed the 2026-07-05 ratchet follow-up that hoisted the optional telemetry
forwarder out of `build_server`. The server still constructs the same
persona-scoped tool list, meta/floor/grounding tools, prompt handlers, resource
handlers, confirmation routes, faithfulness gate, and telemetry rows; only the
thin optional sink forwarding helper moved to module scope. The `build_server`
callable line count dropped from 355 to 337, below its pinned 341-line budget.
Ruff passed, and the real MCP server integration tests covering meta-tools,
serving gates, persona wiring, and client handshake passed with
`-m integration`. The codebase-size gate rerun no longer reports
`build_server`, but remains red on the other known module and callable
offenders.

### follow-up-ledger-bindings-module-size-budget | low | ledger bindings below module budget

Reviewed the 2026-07-05 ratchet follow-up that removed standalone decorative
separator comments from `_ledger_bindings.py` while preserving all section
headings, explanatory domain comments, public exports, selectors, validators,
and resolver logic. The module line count dropped from 1404 to 1395, below its
1400-line budget. Ruff passed, and the focused registry suites covering public
API boundaries, selector shapes, OSS/IOSS aggregation, IVA aggregation, and
annual IVA aggregation passed. The codebase-size gate rerun no longer reports
`_ledger_bindings.py`, but remains red on the other known module and callable
offenders.

### follow-up-modelo-reconcile-module-size-budget | low | reconcile module below budget

Reviewed the 2026-07-05 ratchet follow-up that tightened the
`_DECLARATION_CASILLA_RECONCILE_MODELOS` explanatory docstring without changing
the enrolled modelo set, the declaration-source refusal contract, or any
reconcile logic. The module line count dropped from 1254 to 1246, below its
1250-line budget. Ruff passed, and the real reconcile service/CLI tests covering
justificante reconciliation, declaration casilla reconciliation, multi-modelo
enrollment, value comparison, and CLI behavior passed. The codebase-size gate
rerun no longer reports `_reconcile.py`, but remains red on the other known
module and callable offenders.

### follow-up-transaction-models-module-size-budget | low | transaction models at module budget

Reviewed the 2026-07-05 ratchet follow-up that tightened top-level and catalogue
docstrings in `domain/transactions/_models.py` without changing the transaction
models, validators, serializers, catalogue behavior, or public exports. The
module line count dropped from 1353 to 1340, matching its 1340-line budget. Ruff
passed, and the full domain transaction test suite passed. The codebase-size
gate rerun no longer reports `domain/transactions/_models.py`, but remains red
on the other known module and callable offenders.

### follow-up-secure-objects-module-size-budget | low | secure-object adapter at module budget

Reviewed the 2026-07-05 ratchet follow-up that tightened the
`SecureObjectRepository.list_records` docstring without changing the fail-closed
listing behavior, mixed readable/unreadable diagnostic path, encryption,
revision-integrity checks, or SQL writes. The module line count dropped from
1305 to 1295, matching its 1295-line budget. Ruff passed, and the secure-object
SQL tests for unreadable rows, revision metadata, batch writes, and archive
roundtrip passed. The codebase-size gate rerun no longer reports
`secure_objects.py`, but remains red on the other known module and callable
offenders.

### follow-up-config-payloads-module-size-budget | low | config payloads below module budget

Reviewed the 2026-07-05 ratchet follow-up that tightened `_config_payloads.py`
transport-schema prose and removed separator-only comments without changing any
registered command key, payload field, `extra="allow"` branch, or schema
projection helper. The module line count dropped from 1289 to 1249, below the
default 1250-line budget. Ruff passed, the integration JSON-schema conformance
suite passed, and the app contract manifest suite passed. The CLI module-size
gate rerun no longer reports `_config_payloads.py`, but remains red on the other
known CLI module offenders; the codebase-size gate likewise no longer reports
the file and remains red on the other known module and callable offenders.

### follow-up-review-package-cli-module-size-budget | low | review-package CLI below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved review-package CLI
envelope projection into the existing `_modelo_review_package_rendering.py`
helper without changing command registration, option names, validation branches,
application calls, file writes, or emitted command keys. The CLI module line
count dropped from 1332 to 1129, below the default 1250-line budget. Ruff
passed, the review-package CLI integration suite passed, the integration
JSON-schema conformance suite passed, and the app contract manifest suite
passed. The CLI module-size gate rerun no longer reports
`_modelo_review_package_cli.py`, but remains red on `_modelo_payloads.py` and
`_overview.py`; the codebase-size gate likewise still has unrelated module and
callable offenders.

### follow-up-overview-cli-module-size-budget | low | overview CLI below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved overview calendar, agenda,
backlog, explain, prepare, and pipeline envelope projection into the existing
`_overview_rendering.py` helper without changing command registration, option
names, repository reads, application builder calls, or refusal branches. The CLI
module line count dropped from 1494 to 1181, below the default 1250-line budget.
Ruff passed, schema conformance and app-contract checks passed, the non-calendar
overview suite passed, and focused calendar formatter tests passed. A broader
overview sweep remains red on current profile-storage/session failures and
pre-existing strict-calendar expectation drift; those failures were inventoried
in `var/log/overview-cli-rendering-split-explicit-20260705.log`. The CLI
module-size gate rerun no longer reports `_overview.py`, but remains red on the
peer-dirty `_modelo_payloads.py`; the codebase-size gate likewise no longer
reports `_overview.py` and remains red on the other known module and callable
offenders.

### follow-up-core-config-module-size-budget | low | core config below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved Google, workbook-parity,
and financial-ingest settings fields into the new `_config_integration_fields.py`
mixin without changing field names, defaults, validators, environment variable
names, or the central `Settings` facade. `Settings` still exposes the moved
fields through inheritance and `Settings.env_var_names()`. The `config.py` line
count dropped from 1329 to 1259, below its 1281-line budget. Ruff passed, a
settings smoke check passed, and the focused settings/state-root suite passed
after excluding the pre-existing `.env.example` telemetry-field alignment gap
inventoried in `var/log/core-config-integration-fields-split-20260705.log`.
The codebase-size gate rerun no longer reports `core/config.py`, but remains red
on the other known module and callable offenders.

### follow-up-ledger-llm-classification-contracts-size-budget | low | LLM classification module below budget

Reviewed the 2026-07-05 ratchet follow-up that moved the LLM ledger
suggestion/result contracts and classify-surface provider enum into the new
`_llm_suggestions.py` module. `_llm_classification.py` still imports and
re-exports the same public names, keeps provider availability probing local to
the behavior module, and leaves suggest/apply/reject call paths unchanged. The
module line count dropped from 1714 to 1506, below its pinned 1664-line budget;
the new contract module is 176 lines. Ruff passed, the focused real LLM ledger
suggest/saturate/split/reject suites passed, CLI/import smoke tests passed, and
the facade identity check confirmed the public `aeat.application.ledger`
provider export is still the `_llm_classification` re-export. The codebase-size
gate rerun no longer reports `_llm_classification.py`, but remains red on the
other known module and callable offenders inventoried in
`var/log/codebase-size-after-ledger-llm-split-20260705.log`.

### follow-up-filing-export-xml-dictionary-size-budget | low | filing export below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved the XML-dictionary
declaration renderer from `application.filing._export` into the sibling
`_export_xml_dictionary.py` module. The draft export dispatcher still routes
`xml_dictionary` layouts through the same registry-derived dictionary entries,
official XSD `versionxsd` discovery, Modelo 100 `ECIVIL` code validation, and
ElementTree serialization; the fixed-width renderer and verify path remain in
`_export.py`. The module line count dropped from 1369 to 1221, below the
default 1250-line budget; the new XML renderer module is 174 lines. Ruff
passed, the real filing export/layout refusal suite passed, and the modelo
export application suite passed. The codebase-size gate rerun no longer reports
`application/filing/_export.py`, but remains red on the other known module and
callable offenders inventoried in
`var/log/codebase-size-after-filing-export-xml-split-20260705.log`.

### follow-up-registry-query-reports-size-budget | low | registry query service below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved the registry query report
contracts from `_queries.py` into the sibling `_query_reports.py` module.
`_queries.py` still imports and re-exports the same public report names, and
the top-level `domain.calculations.registry` facade still resolves them through
the existing `_queries` import path. The service behavior remains in
`_queries.py`, including revision resolution, binding row projection, relation
input discovery, and public selector normalization. The module line count
dropped from 1478 to 945, below its pinned 1331-line budget; the new report
contract module is 269 lines. Ruff passed, focused registry query/source/support
tests passed, cross-module import resolution passed, and the facade identity
check confirmed `ModeloListRow` still resolves through `_queries`. The
codebase-size gate rerun no longer reports `_queries.py`, but remains red on
the other known module and callable offenders inventoried in
`var/log/codebase-size-after-registry-query-reports-split-20260705.log`.

### follow-up-registry-schema-extraction-size-budget | low | registry schema below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved the registry extraction
profile schema family (`BboxAnchorSpec`, `ExtractionTargetDefinition`, and
`ExtractionProfileDefinition`) from `_schema.py` into `_schema_extraction.py`.
`_schema.py` still imports and re-exports the same public names through the
existing `_schema` and package facade paths, while revision, snapshot, and
validation models continue to reference the same classes. The module line count
dropped from 1553 to 1412, below its pinned 1490-line budget; the new extraction
schema module is 97 lines. Ruff passed, registry schema/referential/corpus
round-trip/provisional-specimen tests passed, declaration parser boundary tests
passed, and the facade identity check confirmed `ExtractionProfileDefinition`
still resolves through `_schema`. The codebase-size gate rerun no longer
reports `_schema.py`, but remains red on the other known module and callable
offenders inventoried in
`var/log/codebase-size-after-registry-schema-extraction-split-20260705.log`.

### follow-up-verification-predicate-runtime-size-budget | low | verification actions below module and callable budgets

Reviewed the 2026-07-05 ratchet follow-up that moved registry-authored
verification predicate parsing/evaluation from `_verification_actions.py` into
the new `_verification_predicates.py` runtime module. `_verification_actions.py`
still re-exports the existing private predicate constants and evaluator names
used by tests and by `_official_box_advisory.py`, while verification collection
continues to call the same predicate, unresolved-rate, and advisory sources.
The advisory predicate dispatcher was split into per-operator evaluators, and
the revision advisory tail was extracted into `_append_revision_advisory_findings`.
The module line count dropped from 1877 to 1131, below its pinned 1750-line
budget; the new predicate runtime module is 855 lines. Ruff passed, focused
predicate/verification behavior tests passed (181 tests), a re-export identity
smoke check passed, and the codebase-size rerun no longer reports `_verification_actions.py`,
`_evaluate_advisory_predicate_fires`, or
`_collect_revision_verification_findings`. The size gate remains red on the
other known module/callable offenders inventoried in
`var/log/codebase-size-after-verification-predicate-split-20260705.log`.

### follow-up-calculation-actions-adjustments-size-budget | low | calculation actions below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved the modelo-specific
calculation adjustment helpers from `_calculation_actions.py` into the new
`_calculation_modelo_adjustments.py` module: M131 fixed-record data-base
projection, M390/303 silent-zero reconciliation refusal, M349 row-template
output suppression, and M349 detail-row binding totals. `_calculation_actions.py`
still imports those helpers back under the same private names used by the
existing tests, while the source-mesh resolver, calculation persistence call,
and registry-engine invocation stay in the action module. The module line count
dropped from 1500 to 1262, below its pinned 1400-line budget; the new adjustment
module is 261 lines. Ruff passed, focused M131/M349/M390/calculation tests
passed (41 tests), a re-export identity smoke check passed, and the
codebase-size rerun no longer reports `_calculation_actions.py`. The size gate
remains red on the other known module/callable offenders inventoried in
`var/log/codebase-size-after-calculation-adjustments-split-20260705.log`.

### follow-up-m131-modulos-engine-test-size-budget | low | M131 modulos engine test below module budget

Reviewed the 2026-07-05 ratchet follow-up that split the M131 EO modulos
engine test data and activity cases without changing oracle values or
assertions. Shared coefficient tables and independent expected-value helpers
now live in `_modelo_131_modulos_engine_support.py`; food and hospitality cases
live in `test_modelo_131_modulos_engine_food.py`; retail, repair, transport,
and service cases live in `test_modelo_131_modulos_engine_retail_services.py`.
The original `test_modelo_131_modulos_engine.py` keeps the core smoke,
no-silent-fabrication, indices, and advisory flag coverage. Post-format line
counts are 616 lines for the original module, 560 for the support module, 440
for the food module, and 887 for the retail/services module. Ruff and syntax
checks passed, the split M131 modulos suite passed (99 tests), and the
codebase-size rerun no longer reports `test_modelo_131_modulos_engine.py`.
The size gate remains red only on the known peer-owned `_formula_runtime.py`
and `_modelo_payloads.py` offenders inventoried in
`var/log/codebase-size-after-m131-modulos-test-split-20260705.log`.

### follow-up-modelo-iva-wallet-payload-size-budget | low | modelo payloads below module budget

Reviewed the 2026-07-05 ratchet follow-up that moved the IVA wallet balance,
seed, and override JSON-result schemas from `_modelo_payloads.py` into the new
`_modelo_iva_wallet_payloads.py` module. `_modelo_payloads.py` still imports
and re-exports `IvaWalletBalanceResult`, `IvaWalletSeedResult`, and
`IvaWalletOverrideResult`, and the CLI's existing
`from ._modelo_payloads import ...` call path remains unchanged. The missing
`IvaWalletOverrideResult` `__all__` export was added while preserving direct
module imports. `_modelo_payloads.py` dropped from 1353 to 1310 lines, below
its pinned 1341-line budget; the new IVA wallet payload module is 63 lines.
Ruff and syntax checks passed, the IVA wallet seed/correct/override CLI suite
passed with the integration marker enabled (16 tests), JSON schema/module-size
payload gates passed (2 tests), a re-export identity smoke check passed, and
the codebase-size rerun no longer reports `_modelo_payloads.py`. The size gate
remains red only on `_formula_runtime.py` and `calculate_registry_snapshot`,
inventoried in
`var/log/codebase-size-after-modelo-iva-wallet-payload-split-20260705.log`.

### follow-up-formula-runtime-m131-size-budget | high | formula runtime below module and callable budgets

Reviewed the 2026-07-05 ratchet follow-up that moved the M131
estimacion-objetiva modulos runtime evaluators from `_formula_runtime.py` into
the new `_formula_runtime_m131.py` sibling module. `_formula_runtime.py` keeps
the single dispatcher and routes the six existing M131 op names through
`_formula_runtime_m131.evaluate_m131_*`; no registry op name, resolver
convention, source kind, or calculation contract changed. The snapshot entry
point also moved its external binding/relation id validation block into
`_validate_external_value_ids`, preserving the same hard-failure checks while
bringing `calculate_registry_snapshot` below its callable ceiling.
`_formula_runtime.py` dropped from 2365 to 1587 lines, below its pinned
1835-line budget; `calculate_registry_snapshot` dropped from 234 to 217 lines,
below its pinned 228-line budget; the new M131 runtime module is 850 lines.
Ruff and syntax checks passed, the focused formula-runtime and split M131
modulos suite passed (110 tests), an import-link smoke check passed, and the
codebase-size gate passed cleanly (2 tests) in
`var/log/codebase-size-after-formula-runtime-m131-split-20260705.log`.

## Recommendations

Keep the `aeat.tests.secure_sql -> aeat.adapters.**` wildcard under explicit
review in later inversion work. It remains justified here because the helper is
a shared secure-storage test utility that imports real persistence adapters.
