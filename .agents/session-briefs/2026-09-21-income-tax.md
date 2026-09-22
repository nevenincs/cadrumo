# Income tax workflow: preflight brief

Brief ID: INCOME-01. Revision: 0.6. Date: 2026-09-21.
Status: acceptance contract; income implementation active in another session; cc/UUID not yet recorded here.
Coordinator: this conversation. Session cc numbers and UUIDs: not supplied.
Mandatory cadence: [session policy revision 1.3](session-policy.md). Delegate bounded discovery and factual audit reports to Luna Max throughout implementation; leads consume reports and make targeted source reads. Existing sessions adopt through the next checkpoint without restarting completed work.

## Goal

Prove that CLI and TUI can each take the same synthetic financial inputs through the ledger, persist invoices, calculate personal income tax, verify the declaration, and export the official importable filing artifact. Prove interchangeability by continuing each frontend's work in the other frontend. Answer single-period, cross-period, missing-history, and annual Modelo 100 questions separately.

This document prepares implementation prompts. Its existence does not start implementation or claim any acceptance case passes. The user reports a clean/green backend baseline; this preflight has not revalidated it. No live filing submission is included.

## Selected scope and remaining fixture decisions

- Selected regime: synthetic self-employed taxpayer under direct estimation, Modelo 130 to annual Modelo 100. Modelo 131 and other regimes are out of scope for this first brief.
- Tax year: latest completed year supported by both modelos' calculation and official export definitions for the selected scenario. Resolve programmatically from authority data and a declared as-of date; pin both revision identities. Report the latest completed calendar year, selected supported year, and any support gap explicitly. Never hide missing latest-year support behind an older passing scenario.
- Synthetic taxpayer: fix applicable territory, residency, activity/regime, filing obligation dates, and personal/family attributes before deriving expected values. Explicitly exclude untested income categories from completion claims.
- Export acceptance: validate the actual authority-selected artifact format. Runtime has fichero-BOE and XML-dictionary export paths, including Modelo 100 XML-specific logic. A filename or successful write is not proof of importability; official-service acceptance requires its own evidence and is not assumed from local validation.

## Acceptance matrix

| ID | Scenario | Required evidence |
| --- | --- | --- |
| A1 | Ledger ingestion and persistence | Enter synthetic income/expense invoices through each frontend's supported user flow; reopen storage in a fresh process/session and verify amounts, dates, classification, and evidence links. No direct database fixture insertion substitutes for this journey. |
| A2 | Financial lineage | Calculation reads persisted invoices. Trace contributing records and exclusions into source inputs/casillas. In a separate controlled variant, change one invoice through a supported flow and prove the expected calculation difference. |
| A3 | Single period | Complete an applicable period from ledger input through calculation, verification, and valid export; independently check values, precision, and disposition. Include a legitimate first period with no prior obligation. |
| A4 | Multiple periods | Use distinct amounts in each period, boundary dates, and an out-of-year control. Prove the selected revision's cumulative/period window, deductions/payments, and isolation from unrelated years/profiles; prevent duplicate counting. |
| A5 | Missing history | Remove required prior history from an isolated scenario. Distinguish missing, recorded zero, not applicable, and available history. Distinguish calculated/draft/exported/actually filed states under existing contracts. Identify missing modelo/year/period and remediation. Incomplete required inputs must not become a silently successful final export. |
| A6 | Annual Modelo 100 | Reconcile annual financial sources, applicable prior payments/withholdings, and other required inputs with independently established expected annual values. Do not treat a sum of quarterly cumulative totals as an annual oracle. Demonstrate provenance and missing-source handling. |
| A7 | Frontend parity | Run CLI-only and TUI-only journeys against separate isolated stores created from one versioned synthetic input definition; compare canonical state, calculation, verification, refusals, and exported tax content with the oracle. |
| A8 | Interchangeability | Run CLI-to-TUI and TUI-to-CLI continuations on the same scenario store, using sequential access. Preserve classification, work/revision identity, history, and export meaning across restarts. |
| A9 | Export correctness | Validate official format/schema/record structure and declared financial fields for each selected modelo/revision. Compare bytes when deterministic; enumerate and justify any variable nonfinancial metadata before comparing normalized meaning. |
| A10 | Repeatable year-independent workflow | One parameterized scenario definition and runner drives the selected year across both frontends and continuation cases. Report selected year/revisions, coverage, artifacts, and outcomes in machine-readable form. Deterministic resolver tests use an explicit as-of date and bounded authority inputs; year rollover must not silently change their subject. |

Fixtures and expected results are defined once. Each frontend ingests them itself. Hand calculations/authority-grounded expectations must be independent of the production calculation being tested. Equality between frontends alone is insufficient. Applicability and required-history rules must be evidenced for the chosen profile/year; do not invent a blanket obligation to possess every preceding return.

The income fixture must include bank/ledger transactions and coherently linked persisted issued invoices, with distinct taxable base, VAT where applicable, withholding, and net receipt. Prove invoice figures and provenance actually contribute; a cash-only fallback must not accidentally satisfy the oracle. Exercise absent/refused invoice evidence as a separate case and report its advisory/refusal behavior. Include controlled invoice-date versus transaction-date boundary cases, with expected treatment grounded in the selected calculation contract rather than assumed uniform across income and expenses.

## Programmatic execution requirements

Follow [ACCEPTANCE-01](acceptance-pattern.md) for dev/acceptance/ placement, temporary settings, isolated stores, credential transport, cleanup, receipts, and shared execution plumbing. The active dev/acceptance/income_tax/ driver is the first implementation to align with this pattern, not an exemption from it. Preserve the other session's code ownership.

- Provide an explicit year override and a latest-supported mode through the existing appropriate development/test tooling; do not add a product CLI command merely to host acceptance tests.
- Generate invoice dates, period boundaries, history addresses, and annual targets from a year parameter. Keep scenario identities and distinct per-period amounts stable. Resolve application period codes from the established contract (currently 1T through 4T and 0A), not invented aliases.
- Discover compatible Modelo 130 and Modelo 100 revisions, calculation support, and export layouts from canonical authority data. Pin the selected authority generation for a run. Missing, ambiguous, or incompatible support is a visible result, not a skip presented as success.
- Reuse one scenario specification and oracle across CLI, installed TUI, and continuation drivers. Exercise real persisted user flows and installed composition; direct service seeding or injected-only screen tests cannot substitute for frontend acceptance.
- Expected values must account for year-dependent rules. Keep independently grounded oracle data/calculation separate from production calculations; do not reuse production outputs as expected values or blindly reuse one year's rates for another year.
- Run the full acceptance journey once for the selected latest supported year. Use a small, directed resolver/year-parameterization check to prove year independence; do not automatically multiply expensive end-to-end runs across every historical year.
- Isolate each scenario's secure storage and use deterministic synthetic input definitions. Reuse a store only within its intended sequential cross-frontend continuation. Repeated runs must not accumulate duplicate invoices/history from previous runs.
- Emit a machine-readable receipt keyed by brief revision, scenario, frontend path, year, authority/revisions, relevant source state, and acceptance ID. Distinguish failure, missing capability, blocked prerequisites, and not exercised. Capture sanitized diagnostics and artifact validation results.

## Session allocation

| Name | Goal | Exclusive write ownership | cc / UUID |
| --- | --- | --- | --- |
| income-cli | Prove CLI journey and shared financial correctness; integrate shared fixes; own final shared gates | CLI plus explicitly assigned application/domain/persistence files and canonical shared fixture/oracle files | pending / pending |
| income-tui | Prove the same journey through installed TUI and both continuation directions; complete required TUI wiring | TUI screens/controllers/composition and TUI tests; shared files require coordinator reassignment | pending / pending |

Read-only reconnaissance may overlap. Pin the shared behavior/fixture contract before dependent implementation. Integrate shared changes first when needed. Later shared changes invalidate affected TUI evidence and require only the relevant reruns. Ownership is provisional until the concrete work packets name files.

## Stable instructions for both session prompts

You are SESSION_NAME. Deliver its goal against INCOME-01 and the coordinator's selected scope, owned files, and acceptance IDs. Record your cc number, UUID, lead model, and brief revision before work. Consume the relevant Luna Max discovery/audit report and use targeted reads for the cited contract or code being changed. Delegate missing-context questions; do not load whole source inventories or session transcripts.

Apply [the shared session policy](session-policy.md) for agent levels, bounded delegation, reporting, file ownership, and verification reservations. income-cli provisionally owns final shared gates, subject to the coordinator's single reservation list across income and IVA. income-tui consumes those receipts. This assignment must not cause duplicate aggregate checks when IVA work lands in the same integration state.

## Initial source map

- CLI: src/cadrumo/entrypoints/cli/modelo_work_command_specs.py, ledger command families, common.py, errors.py; shared composition under src/cadrumo/entrypoints/.
- TUI: src/cadrumo/entrypoints/tui/launcher.py and ledger/, declarations/, modelo/, aeat_sync/. Installed declarations and AEAT Sync composition have optional handoffs left unbound; establish relevance to this brief before assigning fixes.
- Aggregation: src/cadrumo/application/aggregation/modelo_bindings.py delegates income/expense projections and includes Modelo 130 cumulative-quarter, Modelo 100 annual, and Modelo 131 agrarian income branches. Static presence is not demonstrated end-to-end support.
- Invoice evidence: application/aggregation/renta_income_ledger.py and _renta_income_evidence.py load transaction/invoice catalogues; sales evidence checks reciprocal linkage, bucket, invoice kind, decomposition, and net-cash coherence. Expense paths include renta_ledger.py and modelo_bindings_renta_expenses.py. Verify each path's date semantics separately.
- Filing history: application/calculations/multi_year.py, cross_period_clean_state.py, and cross_period_models.py; inspect required prior observations, activity-start scoping, explicit zero, and unresolved diagnostics for the selected year/profile.
- TUI structural constraint: entrypoints/tui/modelo/view/filing.py explicitly documents a read destination without canonical filing state/history projection and with draft readiness permanently unmeasured under its current contract. Do not recast that limitation as a trivial missing callback. Determine whether the required journey can use existing contracts; any new architectural decision must be escalated before implementation.
- Export: src/cadrumo/application/filing/export.py, _export_parity.py, _export_xml_dictionary.py.
- Existing chain evidence: src/cadrumo/adapters/persistence/profile/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py contains four cumulative Modelo 130 calculations followed by annual Modelo 100, with annual payment fold-in assertions. It fixes year 2024, uses an empty invoice catalogue, and calls application services; it is not frontend or invoice-consumption acceptance.
- Known export refusal in that test: test_autonoma_m100_salary_certificate_retenciones_export_replays_verified_total_pagos expects ModeloExportError with cause aux_block_undeclared and aux_version among missing fields, and asserts that no file exists. This static observation has not been rerun. Check the selected latest-year layout first; do not claim all revisions are blocked solely from the 2024 fixture, invent an Aux/VERSION value, or weaken the refusal to produce an invalid artifact.
- Year-selection reference: src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py::_scenario_year uses published_supported_filing_years and the last completed year. Reuse relevant existing primitives, but prove compatibility for both modelos, their selected scenario, and exports; this helper alone is not that proof.
- Cross-cutting: src/cadrumo/core/logging.py, redaction/rules.py, errors/, secure_object_write.py, storage_taxonomy.py; src/cadrumo/adapters/persistence/storage/.
- Verification: just check-types (ty, pyrefly, basedpyright across supported platforms); just check-import-boundaries; targeted pytest; specialized TUI render/keychain lanes only when their evidence is required and reserved.

## Completion report

For each acceptance ID report proven, failed, blocked, or not exercised, with evidence. State separately whether CLI works, TUI works, continuation works, single-period works, multiple-period aggregation works, missing history is handled, annual Modelo 100 works, and each official export is locally validated. Never compress partial success into an unqualified claim that personal income tax is fully supported.

## Initial work order

1. Resolve the latest completed target year and both revisions; inspect and narrowly exercise Modelo 100 export admission, especially Aux/VERSION. Report capability gaps before investing in a full UI journey. Support discovery must not filter away a missing required export field and silently select an older year.
2. Fix the synthetic profile/scenario and independent expected values; explicitly enumerate required prior-year and prior-period history for it. Finalize file ownership and verification reservations.
3. Implement or adapt the shared parameterized scenario driver and CLI journey; in parallel, the TUI session inventories exact installed action gaps against the agreed contract. Shared-runtime findings have one owner.
4. Complete scoped frontend work, route any architecture decision back to the coordinator, then exercise both isolated frontend journeys and sequential continuation directions.
5. Run remaining reserved targeted checks and one coordinated set of applicable aggregate gates; deliver the acceptance matrix and machine-readable receipts.
