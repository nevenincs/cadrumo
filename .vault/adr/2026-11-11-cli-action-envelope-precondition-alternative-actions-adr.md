---
tags:
  - '#adr'
  - '#cli-action-envelope'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:5d27e990c59f3d5d824f5286ef765292503f32136004a6808cf4e998e1fa3c3d'
related:
  - "[[2026-08-13-cli-action-envelope-successor-adr]]"
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
  - "[[2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `cli-action-envelope` adr: `ordered alternative recovery actions on one precondition verdict` | (**status:** `accepted`)

Proposed 2026-11-11 on the ruling PRIME made for the operator that day: Option A in its additive form. Accepted 2026-11-11 by PRIME under the operator's delegation, confirmed that day, after reading it in full against the conditions it set; implementation follows the current hand-over.

## Problem Statement

A precondition verdict carries exactly one recovery action or one closed no-recovery outcome (`src/cadrumo/core/precondition_action_invariants.py:116-183`, `src/cadrumo/application/operator_actions/models.py:30-39`). The accepted 2026-11-11 amendment in `2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr` requires that, when an in-envelope upstream return is absent, `operator.modelo.work.attest_prior_value` is served beside the create, import or capture door of the earlier return. The verdict cannot express that. `cross_period_door` returns one scenario and one argument map (`src/cadrumo/application/modelo/verification_cross_period.py:731`, `:736-786`) and serves the attest door only outside the envelope (`:764-771`). The admission flag already exists (`src/cadrumo/application/calculations/cross_period_models.py:480`, set at `src/cadrumo/application/calculations/cross_period_clean_state.py:848`), but no door reads it.

The record that owned the verdict contract, `2026-08-09-cli-action-envelope-hardening-adr`, was archived and later removed from the vault. `2026-08-13-cli-action-envelope-successor-adr` and `2026-08-11-tui-architecture-adr` still cite it. No live ADR governs the verdict shape, so this is a new decision in the `cli-action-envelope` feature rather than an amendment. The removed record's text is readable at commit `f4729489f9^`, and the 2026-08-13 successor still cites it; restoring it is not part of this decision.

## Considerations

- One finding reports one fact. A blocked dependency is one blocker, whatever the number of ways to clear it.
- Every existing renderer reads the single `action` field: the CLI envelope (`src/cadrumo/entrypoints/cli/common.py:435-469`), the shared text lines (`src/cadrumo_client/commands/output.py:20-28`, `:70-79`), the runtime CLI (`src/cadrumo_runtime/commands/presentation.py:25`, `src/cadrumo_runtime/commands/main.py:168`), the verification snapshot the desktop reads (`src/cadrumo/application/modelo/verification_projection.py:127-168`), and the operation snapshot (`src/cadrumo/application/operator_actions/projection.py:103-143`).
- Verdicts are persisted. Stopped operations store the verdict as canonical JSON (`src/cadrumo/application/operations/error_detail.py:151-158`); workflow history stores its snapshot (`src/cadrumo/application/workflow/run_projection.py:285`, `:311-313`).
- The recovery-action census joins each `(leaf, condition, scenario)` profile to observed outcomes (`src/cadrumo/application/operator_surface/models.py:200-229`, `dev/mcp_eval/action_coverage.py:174-179`).
- Rust and desktop builds are frozen. Native changes are text only.
- Surfaces render served doors; they author no tax choice.

## Considered options

- **Additive ordered alternatives list (chosen).** `action` stays the primary door, unchanged. An optional list names further doors. Old consumers see the record they see today.
- **Replace `action` with a list.** Rejected: it breaks every consumer, every generated type and every stored verdict.
- **A second finding per extra door.** Rejected: one blocker would be reported twice, and a finding would no longer state one fact.
- **A door on the calculation note.** Rejected and out of scope: notes stay doorless; the verify finding carries the door.

## Constraints

- **Additive.** An absent or empty list is the behaviour of today. The fields `action`, `argument_bindings`, `missing_argument_names`, `conditionality` and `no_recovery_outcome` keep their names and meanings, and describe the primary door only.
- **Stored records unchanged.** A verdict without alternatives validates and serializes to the same bytes as before, so stored error details and workflow history keep validating and hashing alike.
- **Typed and ordered.** Each entry holds an action of the action type of the verdict (`ActionReference` in the application, `ResolvedActionReference` on the wire) plus the argument bindings, missing argument names and derived conditionality of that action. Order is meaning: the primary `action` comes first, then the list in order. No action id repeats, including the primary one. A list is allowed only beside an actionable `action`, never beside `no_recovery_outcome`.
- **Same argument rules.** Each entry obeys the argument rules of the verdict: unique names, condition-evidence arguments backed by declared evidence, missing names matching missing bindings, conditionality `immediate` or `requires_arguments` as derived.
- **Declared, not improvised.** The precondition profile declares the exact ordered alternative set for its scenario. A producer whose alternatives differ from the declaration fails closed, as a disagreeing primary does today (`src/cadrumo/application/modelo/preconditions.py:1017-1022`). A different door set is a different scenario id.
- **Every door shown.** The CLI and runtime renderers show every door, primary first. JSON carries the list; text output adds one line for it only when it is non-empty.
- **One finding, one fact.** A second finding carrying another door is rejected.
- **Notes stay doorless.** No note action field is part of this decision.
- **Native text only.** The generated contract types and the native schema pin are updated as text, not built, with a line in the `NATIVE-DEBT.md` list the coordinator keeps, naming the check to run when the freeze lifts.
- **Manifest regenerated.** The operation contract manifest is regenerated with `python -m dev.operation_contract_manifest.generate` and proved with `--check`.

## Implementation

We will add one optional, ordered, typed list of alternative recovery actions to the precondition verdict and to each of its wire records, and we will use it first for the cross-period attest door beside the door of the earlier return. Type and field names below are hypotheses; the constraints bind.

- **Core invariant.** `src/cadrumo/core/precondition_action_invariants.py:116-206`: add a generic entry model (working name `PreconditionAlternativeAction[ActionT, ArgumentT]`) with `action`, `argument_bindings`, `missing_argument_names` and `conditionality`, validated by the existing argument and conditionality rules. Add `alternative_actions` (an empty tuple by default) to `PreconditionOutcomeInvariant`, omitted from serialization when empty. Extend `_validate_outcome` (`:159-183`) to refuse a list beside `no_recovery_outcome`, a repeated action id, and an entry whose conditionality its bindings contradict. Keep list order; do not sort it.
- **Application verdict.** `src/cadrumo/application/operator_actions/models.py:30-39`: bind the entry to `ActionReference` and `ActionArgumentBinding`; change the docstring from "exactly one" to "one primary action, then ordered alternatives".
- **Wire records.** `src/cadrumo/core/json_contract.py:201-209` (`ResolvedPreconditionAction`): bind the entry to `ResolvedActionReference` and `ResolvedActionArgument`. `src/cadrumo/application/operator_actions/projection.py:103-143` (`PreconditionVerdictSnapshot`) and `src/cadrumo/application/modelo/verification_projection.py:127-168` (`ModeloPreconditionSnapshot`): add an entry snapshot and carry it through `from_verdict`/`to_verdict` and `from_failure`/`to_failure`. Follow the existing default convention of each record, provided a verdict without alternatives round-trips unchanged.
- **Resolver.** `src/cadrumo/application/operator_surface/precondition_action.py:46-109`: resolve and validate each entry against the catalogue and its target leaf exactly as the primary. `src/cadrumo/entrypoints/cli/common.py:455-469` and `src/cadrumo_runtime/commands/presentation.py:25`: apply the executable prefix to the `cli_path` of every entry.
- **Profiles.** `src/cadrumo/application/operator_surface/models.py:200-229` (`ManifestActionProfile`): add `alternative_actions` of `ActionReference` entries, allowed only with `action`, unique, and excluding the primary. `src/cadrumo/application/modelo/preconditions.py:56-70` (`_profile`) takes the alternatives. `:186-214`: declare attestable scenarios for `modelo.work.verify` and `modelo.work.file` (working names `source_absent_attestable`, create then attest, and `filed_evidence_missing_attestable`, `operator.live.filed.pull` then attest). `:1000-1084`: the builders take per-alternative argument values and operator-supplied argument names, and refuse an undeclared or missing alternative.
- **Cross-period door.** `src/cadrumo/application/modelo/verification_cross_period.py:731-786`: `CrossPeriodDoor` gains the ordered alternatives with their argument maps. When `evidence.attestation_admitted` is true and the upstream return is absent inside the envelope, `cross_period_door` keeps the create or capture door as primary and appends the attest door, bound to the same facts the out-of-envelope branch binds (`:765-771`) with `value` operator-supplied (`:731-733`). The out-of-envelope branch keeps attest as its only door. `src/cadrumo/application/modelo/verification_gate_findings.py:308-327` passes the alternatives to the builder.
- **CLI and runtime renderers.** `src/cadrumo_client/commands/output.py:20-28`, `:70-79`: emit `precondition_action.alternative_actions` only when non-empty; the runtime CLI uses the same lines. `src/cadrumo/entrypoints/cli/action_rendering.py:16-19` and `src/cadrumo/entrypoints/cli/modelo_rendering.py:793-810` carry the list through the DTO dump; `src/cadrumo/entrypoints/cli/modelo_results.py:263` changes only through the DTO.
- **Generated contract types.** `native/desktop/frontend/src/shell/modeloContract/modeloWorkVerify.ts:59-69` and the other generated modules naming the snapshot (`modelo.ts`, `modeloReadiness.ts`, `modeloQuickfile.ts`): regenerate with `node native/desktop/frontend/scripts/modelo-fixtures.mjs` (contract step), a text generator that compiles nothing. If it cannot run, record the gap rather than hand-edit generated text.
- **Native pin.** `native/application/src/person_operations/protocol.rs:22-23` (`ERROR_DETAIL_SCHEMA_FINGERPRINT`): update it as text if `dev/packaging/tests/test_native_error_detail_schema.py` reports drift. Hypothesis: it does not drift, because the error detail carries the verdict as a JSON string (`src/cadrumo/application/operations/error_detail.py:151-158`). Either way, add one line to `X:/code/cadrumo/.tmp/2026-11-11-prime/NATIVE-DEBT.md` naming the changed TypeScript types, the pin status and the checks (tsc, the verify-form test, the window showing both doors).
- **Manifest.** Regenerate `src/cadrumo/_data/operations/contract_manifest.json` with `python -m dev.operation_contract_manifest.generate`, then run it with `--check`.
- **Tests.**
  - `src/cadrumo/application/operator_actions/tests/test_models.py`: the list accepted and refused (beside no-recovery, repeated id, primary repeated, contradicted conditionality, unsupported evidence argument), order kept, and byte-identical JSON for a verdict without alternatives.
  - `src/cadrumo/core/tests/test_json_envelope_roundtrip.py`: resolved-record round trip with and without the list.
  - `src/cadrumo/application/modelo/tests/test_cross_period_door.py`: an absent in-envelope upstream gives create then attest; a filed source gives pull then attest; out of the envelope, attest stays alone; a present upstream gives no attest.
  - `src/cadrumo/application/modelo/tests/test_cross_period_attest_door_profiles.py`: the attestable profiles resolve both doors against the live command leaves, and an undeclared alternative fails closed.
  - Snapshot round trips in the operator-actions and verification projection tests.
  - A CLI and runtime rendering test through the real resolver showing both doors in JSON and text, and no new text line when the list is empty.

## Rationale

The additive list is the only option that serves the attest door the accepted amendment requires without changing any existing consumer, stored verdict or one-fact finding. Declaring the door set in the profile keeps the census exact and keeps the door choice in the application, not the renderer.

## Consequences

- The "served beside them" ruling of the cross-period amendment becomes implementable at verify and file.
- Every result schema carrying a verdict snapshot changes fingerprint, so the manifest regenerates, and the desktop types are text-updated but unbuilt until the freeze lifts. Until then the window and the TUI show the primary door only.
- Other producers may adopt alternatives later within these constraints, one declared scenario at a time.
- Reconsider if a consumer needs doors that are not interchangeable ways to clear the same fact; that is a different finding, not an alternative.
