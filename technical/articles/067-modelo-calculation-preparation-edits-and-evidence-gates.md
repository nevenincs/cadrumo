# Modelo calculation preparation, edits, and evidence gates

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-067` · **Topic:** [Modelo work and revision lifecycle, part 1](../topics/modelo-work-and-revision-lifecycle-part-1.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 19 modules, 5,039 physical lines, 218,705 bytes, and 46,659 measured `o200k_base` proxy tokens across nine bounded pages. It spans Modelo calculation preparation and adjustment, the guarded edit executor, several legal-advisory collectors, ledger filing-evidence gates, and Modelo 210 grouped-renta/treaty checks. The source was inspected statically; no application code or tests were run and no source was changed. The token count is a measured proxy, not an assertion about model context limits.

## Product capabilities

The application layer prepares calculation inputs against an active work unit and a law-selected registry snapshot. It checks profile readiness, input casilla IDs, ledger-tax readiness for the binding sources the selected revision actually uses, Modelo 303's IVA-wallet decision, and registry-required bindings before handing a `PreparedCalculation` bundle to the calculation action. Ledger findings irrelevant to a Renta-only revision do not automatically block it; an IVA-aggregation revision treats the full IVA preflight surface as relevant. A separate Modelo 200 gate requires an accounting-result input when active business ledger rows are present. Preparation pipeline (`src/cadrumo/application/modelo/_calculation_preparation.py`) Source-sensitive ledger gate (`src/cadrumo/application/modelo/_calculation_preparation.py`)

The shared calculation helpers preserve the identity between a work unit's pinned revision and the snapshot resolved from the law coordinates. Formula outputs become typed casilla observations with formula operands and legal/source provenance; imported values receive provenance from the same selected revision. The model-specific adjustment module validates detail-row ownership, unions resolver and caller rows by natural identity only when figures agree, projects fixed-record M131 values, guards cross-period M390/M303 reconciliation from saving a silent zero where annual amounts exist, and removes scalar template outputs populated by repeating export rows. Revision identity and snapshot resolution (`src/cadrumo/application/modelo/_calculation_helpers.py`) Grounded observations (`src/cadrumo/application/modelo/_calculation_helpers.py`) Detail-row union (`src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`) M390 reconciliation guard (`src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`)

For IVA annual regularization, source staging runs the registry engine in memory to materialize current-year inputs for prorrata and the dependent capital-goods resolver, merges both resolver results, and adds diagnostics for declared but unhandled or unexpectedly missing binding sources. The staging run is intentionally not itself a persisted calculation. Staged dependent resolvers (`src/cadrumo/application/modelo/_calculation_source_staging.py`) Non-persisting registry materialization (`src/cadrumo/application/modelo/_calculation_source_staging.py`) Present-source gaps (`src/cadrumo/application/modelo/_calculation_source_staging.py`)

The chunk also implements distinct verification and calculation notices. Art. 109 coverage is derived from current-period activity ledger rows and a registry-selected ratio and activity-class selectors; it returns a proven/insufficient status instead of treating missing substrate as zero. Attribution-received facts versus the M100 attributed-income casilla, an indeterminate Madrid birth/adoption deduction, year-end capital-goods regularization, and a claimed M210 treaty override each have tailored warnings or diagnostics. These surface possible underclaims or unresolved facts; the M210 treaty and autonomic-deduction messages are advisory rather than automatic eligibility decisions. Art. 109 derivation (`src/cadrumo/application/modelo/_art109_activity_income.py`) Attribution handoff advisory (`src/cadrumo/application/modelo/_attribution_received_advisory.py`) Madrid deduction advisory (`src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`) Capital-goods regularization diagnostic (`src/cadrumo/application/modelo/_bienes_inversion_advisory.py`)

An enrolled Modelo edit executor supports scalar and binding edits by replaying the current operator layer, explicit clears, and other caller context through the canonical calculation boundary. It validates typed values against the registry grammar, rechecks baseline coordinates just before effect, refuses clearing a source-fed casilla, returns typed no-effect refusals for pre-effect failures, and co-commits a mutation receipt. Although row-intent models and row reconstruction helpers exist, the active path currently rejects any row intents as not yet wired; recalculation-only mutation families are also refused. Intent execution and receipt (`src/cadrumo/application/modelo/_edit_execution.py`) Commit-point baseline check (`src/cadrumo/application/modelo/_edit_execution.py`)

## Ledger trust and filing boundaries

When verify, amendment, or evidence recapture seals a revision, the anchor-capture helper packages the revision's contributing transaction IDs, observation grounding, and operator-entered fact basis against a supplied snapshot fingerprint. The draft drift gate compares that anchor with current ledger membership and facts; unavailable membership, new contributors, changed/removed rows, or an unanchored ledger-derived draft produce a blocking stale-calculation finding. It deliberately does not recalculate during verification, preserving the values the operator reviewed. Ledger fact-basis capture (`src/cadrumo/application/modelo/_ledger_anchor_capture.py`) Draft drift comparison (`src/cadrumo/application/modelo/_ledger_drift_gate.py`)

The filing-grade IVA evidence gate inspects the frozen ledger evidence rows, distinguishes absent enum values from unparseable persisted schema values, and blocks unsupported deductible input IVA before a lifecycle finish line. A present but unreadable lifecycle, business classification, or direction is treated as a gap when it can affect the decision. The implementation documents a deliberate difference from verify-time evidence classification: it still credits any attachment on the frozen bundle, in addition to linked invoice evidence, preserving a recovery path for older finalized revisions. Persisted-row evidence classification (`src/cadrumo/application/modelo/_ledger_evidence_gate.py`) Filing refusal (`src/cadrumo/application/modelo/_ledger_evidence_gate.py`)

Modelo 210 annual grouped-renta rows must be complete, homogeneous, and compatible with the official selected income type before calculation; verification repeats the check over persisted revisions. Treaty fact resolution is period/date-specific, and when a governed treaty override actually applies the LOB advisory asks the operator to confirm beneficial ownership/substance that profile data cannot establish. Calculation and verify integrity checks (`src/cadrumo/application/modelo/_m210_agrupacion_renta.py`) Treaty fact resolution (`src/cadrumo/application/modelo/_m210_convenio_facts.py`) Treaty eligibility advisory (`src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py`)

## Quality, security, and unresolved questions

Several boundaries are strong: immutable authority snapshots, explicit provenance on observations, source-aware calculation gates, refusal rather than invented zeros for unresolved evidence, idempotent-style edit receipts, and blocking ledger drift between a draft and the live book. Failure messages generally carry typed reasons and actionable next steps. The advisory collectors keep the operator informed without claiming to resolve facts the product does not hold.

There are important limits and conditional risks. Art. 109's `_proved_withheld_income` infers withholding by comparing invoice base plus IVA with the absolute cash amount received. The inspected code does not consume a direct withholding amount or withholding flag here, so partial payment, offsets, or other invoice-to-cash differences could be mistaken for withholding; confirm the transaction model excludes those cases or add explicit evidence. Withholding inference and row substrate (`src/cadrumo/application/modelo/_art109_activity_income.py`) (The exact helper is within the fully read function body.) The treaty advisory obtains its override through a helper that opens `bundled_indexed_authority()` itself rather than receiving the caller's pinned operation. If authority generations can change during a verification run, the advisory could read a different generation than the snapshot under review; the surrounding runtime's generation immutability is not established by this chunk. Standalone treaty resolver (`src/cadrumo/application/modelo/_m210_convenio_facts.py`)

The edit executor's scalar and binding work is concrete, but all row intents are currently turned away before row reconstruction runs, leaving a gap between the available row-edit data structures/helpers and supported execution. Reorder is also intentionally absent because revision identity is order-blind. Sensitive profile, transaction, tax-ID, and ledger evidence values pass through these boundaries; this chunk supplies typed constraints and provenance, not a full authorization, redaction, or storage-encryption policy. Early unsupported-intent gate (`src/cadrumo/application/modelo/_edit_execution.py`) Row reconstruction helper (`src/cadrumo/application/modelo/_edit_execution.py`)

Cross-module synthesis should verify the transaction semantics behind the Art. 109 cash comparison, the pinned-generation contract for treaty advisories, recovery UX for ledger-evidence refusals, and wiring of edit receipts to the storage transaction. No test execution or runtime correctness is implied by this static pass; source comments describing reproduced failures are implementation evidence, not independently reproduced results here.

## Coverage appendix

All 18 assigned files were read fully across nine bounded pages; no unread ranges remain.

- modelo/__init__.py (`src/cadrumo/application/modelo/__init__.py`) — 1–8
- modelo/_amendment_kind_resolution.py (`src/cadrumo/application/modelo/_amendment_kind_resolution.py`) — 1–192
- modelo/_art109_activity_income.py (`src/cadrumo/application/modelo/_art109_activity_income.py`) — 1–417
- modelo/_attribution_received_advisory.py (`src/cadrumo/application/modelo/_attribution_received_advisory.py`) — 1–287
- modelo/_autonomic_deduccion_advisory.py (`src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`) — 1–242
- modelo/_bienes_inversion_advisory.py (`src/cadrumo/application/modelo/_bienes_inversion_advisory.py`) — 1–176
- modelo/_calculation_aggregation_context.py (`src/cadrumo/application/modelo/_calculation_aggregation_context.py`) — 1–58
- modelo/_calculation_helpers.py (`src/cadrumo/application/modelo/_calculation_helpers.py`) — 1–353
- modelo/_calculation_modelo_adjustments.py (`src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`) — 1–559
- modelo/_calculation_preparation.py (`src/cadrumo/application/modelo/_calculation_preparation.py`) — 1–474
- modelo/_calculation_source_staging.py (`src/cadrumo/application/modelo/_calculation_source_staging.py`) — 1–581
- modelo/_decimal_parsing.py (`src/cadrumo/application/modelo/_decimal_parsing.py`) — 1–79
- modelo/_edit_execution.py (`src/cadrumo/application/modelo/_edit_execution.py`) — 1–646
- modelo/_ledger_anchor_capture.py (`src/cadrumo/application/modelo/_ledger_anchor_capture.py`) — 1–153
- modelo/_ledger_drift_gate.py (`src/cadrumo/application/modelo/_ledger_drift_gate.py`) — 1–236
- modelo/_ledger_evidence_gate.py (`src/cadrumo/application/modelo/_ledger_evidence_gate.py`) — 1–267
- modelo/_m210_agrupacion_renta.py (`src/cadrumo/application/modelo/_m210_agrupacion_renta.py`) — 1–157
- modelo/_m210_convenio_facts.py (`src/cadrumo/application/modelo/_m210_convenio_facts.py`) — 1–33
- modelo/_m210_convenio_lob_advisory.py (`src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py`) — 1–121
<!-- /preserved:article -->
