---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---
# `cli-workflow-redesign` adr: `modelo calculate engine wiring` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The W39 modelo-calculate-revisions ADR introduced `calculate_modelo_revision` as the lifecycle entry for producing draft revisions. The first cut accepted a `casilla_values` mapping verbatim from the operator: the action persisted whatever the caller passed. This let the W39/W40/W41/W42/W43 chain land its lifecycle plumbing (state machine, supersession, pointer advance, bucket events), but it did NOT actually run the registry's formula engine. A calculation produced by `calculate` was indistinguishable from a hand-typed mapping; nothing tied the output back to the registry's authoritative arithmetic.

The registry already exposes a complete formula engine: `calculate_registry_snapshot(snapshot, *, inputs, binding_values, enum_binding_values, relation_values, date_context)` evaluates every declared formula in dependency order, returns the full casilla map, and refuses unknown casilla / binding / relation references. Wiring this engine into `calculate_modelo_revision` is the difference between "calculate persists whatever you give it" and "calculate computes the modelo against the registry's truth".

## Considerations

- The engine reads the registry snapshot for `(modelo, filing_year, period)`. The calculate action must resolve that snapshot before it can run the engine; failure to resolve is a hard refusal (the operator has no path to compute the modelo) rather than a fallback to "store-as-given".
- The engine's `date_context["filing_period"]` selects date-versioned parameters (e.g., legal-rate changes mid-year). The action defaults this to the end-of-period date; an `as_of`-equivalent parameter (`filing_period_date`) lets advanced callers reconstruct prior-rate calculations.
- The W40 verify path previously checked operator-supplied keys against the registry's required-manual-input set by inspecting `casilla_values`. With the engine wired, `casilla_values` always carries every declared casilla (engine-defaulted to zero for missing inputs); the operator's intent is preserved in `inputs_snapshot`. Verify's "missing required casilla" gate must read `inputs_snapshot`, not `casilla_values`.
- The amend path (W49) and the import path (W49b) deliberately bypass calculate: they accept externally-attested casilla values directly because AEAT already computed them. The engine wiring does NOT apply to those paths.
- Content addressing of the revision id is the union of `(inputs_snapshot, binding_overrides, casilla_values)`. With the engine wired, structurally identical inputs produce structurally identical outputs, so two `calculate` calls with the same inputs still collapse to the same revision id (idempotency preserved).

## Constraints

- No fallback. If the registry snapshot does not resolve, `CalculationRegistryUnavailableError` is raised; the action does not persist a revision with operator-only values bypassing the engine.
- No engine bypass. There is no parameter that lets callers skip the engine; every locally-computed revision goes through `calculate_registry_snapshot`.
- The engine's input contract is preserved at the action boundary: unknown casilla / binding / relation ids raise `RegistryValidationError`; missing required bindings raise `RegistryValidationError`; computed-casilla ids as inputs raise `RegistryValidationError`. The action surfaces these as user-facing errors at the CLI boundary.
- `inputs_snapshot` and `binding_overrides` are stored as canonical decimal strings (sorted, normalised) so the content-addressed revision id is stable across re-runs that differ only in encoding (e.g. `"1.0"` vs `"1.00"`).
- The verify-path read of "missing required casilla" switches from `casilla_values` to `inputs_snapshot`; this is the canonical operator-intent surface going forward.

## Implementation

`calculate_modelo_revision` takes:

* `casilla_inputs: Mapping[str, Decimal]` — the operator's manual casilla values.
* `binding_values: Mapping[str, Decimal] | None` — numeric bindings (ledger aggregates, prior-filing pulls, etc.).
* `enum_binding_values: Mapping[str, str] | None` — string-valued bindings (profile enums like CCAA).
* `relation_values: Mapping[str, Decimal] | None` — relation aggregates (cross-period sums).
* `filing_period_date: date | None` — override for `date_context["filing_period"]`; defaults to end-of-period.

The pipeline:

1. Load work unit; refuse on DISCARDED.
2. Load the validated registry authority; resolve the snapshot for the work unit's `(modelo, filing_year, period)`. Failure raises `CalculationRegistryUnavailableError`.
3. Run `calculate_registry_snapshot` with the operator inputs and bindings.
4. Build `inputs_snapshot` (canonical decimal strings of `casilla_inputs`) and `binding_overrides` (canonical strings of `binding_values` + `enum_binding_values`).
5. Use the engine's full output as `casilla_values`.
6. Derive the content-addressed `calculation_revision_id`; persist in DRAFT state; advance the work unit's `current_calculation_revision_id`; emit `modelo.calculation.created` with a payload that now reports `formula_count` from the engine result.

`verify_modelo_revision` reads `target.inputs_snapshot` (not `target.casilla_values`) when checking required-manual-input coverage. This is the operator-intent surface.

The CLI `aeat app modelo work calculate` routes operator-supplied `--casilla CASILLA=VALUE` into `casilla_inputs` and `--binding KEY=VALUE` into either `binding_values` (if the value is a valid decimal) or `enum_binding_values` (otherwise). `CalculationRegistryUnavailableError` is mapped to `typer.BadParameter` at the boundary.

## Rationale

The calculate verb is the first step in the file-chain that actually requires registry truth. Without the engine wired it was a placeholder; with it wired it produces revisions that match what AEAT's own workbook would produce for the same inputs. This unlocks downstream guarantees: verify can trust that the persisted values are derivable from the operator's inputs plus the registry's formulas; file produces a fichero-BOE whose numbers match the engine; amend's content-addressing of corrective revisions is meaningful because the baseline values are computed, not hand-typed.

Reading `inputs_snapshot` rather than `casilla_values` for verify's "missing required" gate is the natural shift once the engine is wired. Before wiring, `casilla_values` was the only surface for operator intent; after wiring, it carries the engine's full output and `inputs_snapshot` is the operator-intent surface. The verify ADR's intent — "did the operator provide every required manual input?" — maps cleanly to the inputs surface.

## Consequences

- `calculate_modelo_revision` now runs the registry engine for every locally-computed revision. The persisted `casilla_values` reflects what the modelo's formulas produce; downstream consumers (export, verify, aggregation) can trust it without re-deriving.
- Work units anchored at a `(modelo, year, period)` tuple that the registry does not cover cannot be calculated locally — by design. Operators get a clear error rather than a silently-persisted draft.
- The fixture for the file-flow / amend-flow / import-flow tests moves to modelo 130 / 1T / 2026 (9 manual inputs + 10 formulas + 1 prior-filing binding) so the engine has real ground to run on. The verify-section continues to use modelo 180 (which has required-manual casillas) with its declared binding + relation values supplied.
- The verify path's "missing required casilla" gate now checks `inputs_snapshot`. The semantic shift is intentional: operator-supplied zeros are valid inputs; operator-absent inputs are the missing-required cases.
- New `CalculationRegistryUnavailableError` and `filing_period_date` action parameter are part of the public API; the apex plan tracks the wiring under wave `W39b` (modelo calculate engine wiring) with phases P249..P251 fully closed.
