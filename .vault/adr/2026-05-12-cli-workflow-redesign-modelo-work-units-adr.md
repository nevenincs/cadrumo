---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

# `cli-workflow-redesign` adr: `Modelo calculation work units and internal filing state` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI redesign must make `modelo` the primary calculation and internal filing
domain. The current command design risks leaving calculation, draft state,
registry inspection, historical filing records, and export/import mechanisms
split across `declaration`, `filing`, `workflow`, `registry`, and storage
terminology that does not match the user's mental model.

Modelo work must not be treated as an expert side command. The project exists to
make hard tax work accessible, so modelo calculation and verification must be a
normal product surface that exposes the calculation backend clearly.

## Considerations

- Ledger data flows into modelo calculations.
- Profile data supplies the identity, legal/tax status, regime, address, and
  other contextual values needed by modelo calculation.
- Some modelos can require previous filing history or remote live data to
  compute or verify correctly.
- Live AEAT submission remains disabled.
- Internal logical filing state is different from live AEAT submission.
- Terminology must distinguish:
  - internal local filing state
  - verified complete modelo revision
  - live-compatible export
  - live AEAT submission, which is reserved and disabled
- Modelo state must be bucket-backed and linked to the active profile's data
  slice.
- Bucket selection and bucket management are configuration concerns. `aeat app
  modelo` consumes the active bucket selected by `aeat config bucket`; it must
  not introduce an `app bucket` surface.
- Normal modelo UX should not require the user to touch bucket commands. Modelo
  commands drive calculation, verification, filing, import/export artifacts, and
  status inside the active bucket through backend services.

## Constraints

- Every modelo work unit must be scoped by stable `bucket_id`.
- Every modelo work unit must identify at least:
  - modelo code
  - tax year
  - period
  - modelo revision / schema revision
- Calculation inputs must be traceable to their sources:
  - ledger financial transactions and enrichments
  - purchase invoice evidence links and business operation invoice links where
    applicable
  - profile values
  - previous internal filing records
  - remote live observations when explicitly captured
- A verified complete modelo revision can be marked current inside the bucket.
- Marking a modelo work unit current or internally filed must not imply live
  submission.
- Decision history must be persisted with timestamps and enough structured
  context to explain when and why a modelo revision became current.
- Storage must protect relational links between buckets, ledger financial
  transactions, payable invoices, collectible invoices, purchase invoice
  evidence, profile values, modelo calculations, exports, and decision records.

## Implementation

The redesigned `modelo` domain exposes the calculation engine directly. The
command vocabulary is designed around modelo work units, not generic
filing/archive language.

Command vocabulary (accepted target surface; not current registration):

- `aeat app modelo list`
- `aeat app modelo create`
- `aeat app modelo status`
- `aeat app modelo rename`
- `aeat app modelo bindings list`
- `aeat app modelo bindings preview`
- `aeat app modelo calculate`
- `aeat app modelo verify`
- `aeat app modelo file`
- `aeat app modelo filing-record list|show`
- `aeat app modelo export`
- `aeat app modelo import`
- `aeat app modelo reconcile`
- `aeat app modelo amend`
- `aeat app modelo history`

`name` and `help` are not accepted target verbs. Register the work-unit
vocabulary above under `aeat app modelo`; keep registry-introspection commands
only where they do not obscure work-unit lifecycle commands.

The full command tree is locked by the app-modelo-shape and app-modelo-
bindings-shape ADRs. Domain ownership is settled here:

- `ledger` owns incoming and expense transaction history, transaction
  enrichment, categorization/split behavior, attachments, VAT/IRPF inputs, and
  proportionality-related inputs used by calculation.
- `profile` owns current profile identity/legal/tax/address/regime context and
  active bucket selection.
- `modelo` owns calculation work units, the calculation engine, verification
  output/state, internal filing state, filing-record ownership, and
  verification/export-status ownership.
- `bucket` owns storage identity and persistence; it supports the domains but is
  not normal interactive workflow UX.
- `modelo` does not own live AEAT submission.

Storage model required for implementation (tracked in the execution plan):

- bucket table / bucket identity
- modelo work-unit table keyed by bucket, modelo, year, period, and revision
- calculation input snapshot table or equivalent structured source trace
- calculation result / casilla value table
- verification report records linked to calculation revisions
- filing records linked to immutable filed calculation revisions
- bucket event-history records for material workflow transitions
- export/import artifact records tied back to the modelo work unit
- current filed pointer that resolves to a filing record, which resolves to the
  immutable filed calculation revision

## Period and selector vocabulary (apex review 2026-05-12)

Modelo work units are keyed by bucket, modelo, year, period, and revision.
Operator-facing selectors must be discoverable. The CLI accepts canonical
period tokens and documented AEAT aliases instead of leaving operators to guess
between `Q1` / `T1` / `1` / `0A`. The redesigned tree fixes:

- Canonical period tokens accepted on input AND emitted on output:
  - quarterly: `Q1`, `Q2`, `Q3`, `Q4`
  - monthly: `M01` through `M12`
  - annual: `annual`
  - one-off / non-periodic: `none`
- AEAT-internal aliases accepted on input only (for parity with sede-imported
  data): `1T`/`2T`/`3T`/`4T` map to the canonical `Q1`–`Q4`; `0A` maps to
  `annual`.
- The valid period set for each modelo is registry-driven; `aeat app modelo
  bindings list --modelo M` and `aeat app modelo list --modelo M` both
  enumerate the accepted period tokens for that modelo.
- Year tokens are four-digit integers (`2026`); a future regime ADR may add
  cross-year selectors but they are out of scope here.
- Selector form: `--modelo M --year YYYY --period TOKEN` is the explicit
  triple; `WORK_UNIT_ID` is the stable opaque form returned by
  `aeat app modelo create` and accepted everywhere a work-unit is targeted.

## Rationale

`modelo` is the natural product concept for the calculation backend. Users do
not think in terms of registry internals, secure-object namespaces, or filing
draft implementation details. They think in terms of the tax model they need to
prepare for a year and period.

Making `modelo` the calculation and internal filing domain gives the CLI a
single place to answer:

- what modelos are available
- what state a modelo is in for the active bucket
- what data is missing
- what calculation was produced
- what schema revision was used
- whether the current revision is verified complete
- what was exported or imported
- what changed over time

This also keeps the live-submission boundary explicit. A local verified modelo
revision is a product state inside the bucket, not an AEAT submission.

## Consequences

- Existing `declaration`, `filing`, `workflow`, and `registry` responsibilities
  must be audited and reassigned around the `modelo` work-unit lifecycle.
- The current `app modelo` introspection surface is not enough; it must become
  the calculation-domain surface, not only a registry-query surface.
- Storage work is required before modelo lifecycle commands can be made safe.
- Existing archive/export/import terminology must be replaced where it refers
  to profile-scoped modelo data movement.
- Every calculation and verification result needs source traceability and a
  timestamped bucket event history.
- The app-modelo-shape ADR, app-modelo-bindings-shape ADR, bucket-event-
  history ADR, ledger-transaction-management ADR, and bucket ADR close every
  item previously tracked here. No further ADRs are required.
