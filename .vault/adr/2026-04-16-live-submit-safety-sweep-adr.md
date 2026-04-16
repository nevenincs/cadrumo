---
tags:
  - '#adr'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-submit-safety-sweep-research]]'
  - '[[2026-04-16-live-submit-safety-sweep-reference]]'
  - '[[2026-04-12-submission-engine-adr]]'
  - '[[2026-04-12-workflow-engine-adr]]'
  - '[[2026-04-13-filing-complementaria-adr]]'
---

# `live-submit-safety-sweep` adr: `issue-117-contract-migration` | (**status:** `accepted`)

## Problem Statement

The legacy live-submit safety contract depended on two external control points:
the `override_confirmation` parameter and the
`AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` environment variable. That split
model made live behavior too easy to vary by caller, too easy to preserve
through wrapper layers, and too easy to represent as available even where no
real live wiring existed.

The audited production gaps in `#142` through `#146` show that the old contract
has drifted across `aeat.submission`, `aeat.workflow`, and the live-capable CLI
surfaces. This ADR replaces that contract with the hardening model required by
`#117`: explicit live intent at the API boundary, ordered live gates in the
engine, an internal confirmation hook, append-only audit logging, and fail-closed
behavior for unsupported live surfaces.

## Considerations

- Live-capable APIs must require an explicit caller choice between dry-run and
  live execution.
- Safety checks must execute in a single ordered engine path rather than being
  distributed across callers and wrappers.
- Test execution must fail closed for live submission paths, with no
  exceptions or compatibility bypasses once `PYTEST_CURRENT_TEST` is present.
- Confirmation must remain possible for real live execution without remaining
  part of the public API contract.
- Auditability must cover both simulated and live submission attempts.
- Unsupported CLI live paths must refuse execution instead of reporting
  behavior they cannot perform.
- Workflow-facing entry points should inherit engine safety semantics rather
  than preserving separate override behavior for compatibility.

## Constraints

- The decision must remove the legacy `override_confirmation` plus
  `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` contract rather than layering
  another option onto it.
- The live-submit path must be gated by both runtime refusal under pytest and
  explicit enablement through `AEAT_LIVE_SUBMIT_ENABLED`.
- Any live-capable CLI surface must require an explicit `--dry-run` or `--live`
  choice and must not consult `AEAT_LIVE_TESTS_ENABLED` or
  `requires_live_enabled()` for write behavior.
- The confirmation implementation must live in internal code that is not a
  supported pytest import surface.
- Audit logging must be append-only and must record both dry-run and live
  attempts in the same log contract.
- CLI surfaces backed by `_NullSession` cannot truthfully support `--live`
  until real wiring exists.
- Workflow protocol, adapter, and engine surfaces must migrate to the new
  contract explicitly instead of forwarding compatibility shims.

## Implementation

- `dry_run` becomes a required keyword-only argument on live-capable APIs in
  `aeat.submission` and `aeat.workflow`. Callers must state intent explicitly,
  and every inherited call site is rewritten to spell out `dry_run=True` or
  `dry_run=False`.
- The engine becomes the sole authority for ordered live gates. A live attempt
  proceeds in this order only: pytest refusal, `AEAT_LIVE_SUBMIT_ENABLED` check,
  internal confirmation, audit-log append before dispatch, transport dispatch,
  and audit-log append with response and justificante data after dispatch.
- The typed refusal contract is standardized in `aeat.submission` with
  `AeatLiveSubmitNotEnabledError`, `AeatPytestLiveWriteRefusedError`, and
  `AeatLiveSubmitConfirmationRefusedError`.
- Human confirmation moves into internal module `_confirm.py`. It prints the
  filing summary and checksum to `stderr`, performs a blocking `stdin` read with
  no timeout or default answer, requires the exact phrase
  `CONFIRMO FILING {modelo} {period}`, and fails closed on test-time imports.
- Append-only audit logging moves into `_audit.py`. A strict typed record is
  written to `.aeat/live-submit-audit.log`; dry-run and live attempts share the
  same log so the operational trail is complete. Live attempts record both the
  pre-dispatch event and the post-dispatch response or justificante outcome.
- CLI submit commands that remain genuinely live-capable require an explicit
  `--dry-run` or `--live` mode selection. They do not preserve
  `--i-understand-this-is-real`, do not reuse `AEAT_LIVE_TESTS_ENABLED`, and do
  not use `typer.confirm(...)` as a write gate.
- CLI surfaces that still rely on `_NullSession` must refuse `--live` until
  real live wiring exists. They must not claim successful live-submit behavior
  when the underlying transport or session is not implemented.
- Workflow surfaces inherit the core engine contract directly. They do not
  preserve `override_confirmation`, and they do not define an alternate
  live-submit safety path.

## Rationale

The legacy model allowed safety-critical behavior to be negotiated outside the
engine. That created too much room for wrapper drift, partial migrations, and
misleading surface behavior. Requiring keyword-only `dry_run` fixes the API
boundary first: a caller must opt into live mode explicitly. Centralizing the
ordered gates in the engine fixes the execution path next: live behavior cannot
proceed unless the hardened runtime conditions are satisfied.

Moving confirmation into `_confirm.py` deliberately narrows its role.
Confirmation remains part of live execution, but it is no longer a public
contract that wrappers or tests can import, override, or preserve as
compatibility behavior. The audit decision in `_audit.py` complements that
hardening by ensuring every attempt is recorded, including dry-run traffic that
would otherwise disappear from the operational record.

Refusing `--live` on `_NullSession` CLI surfaces is also intentional. A hard
refusal is more correct than a compatibility path that appears to work but
cannot actually perform a real live submission. Making workflow surfaces
inherit the engine contract completes the change by preventing the old override
semantics from reappearing at higher layers.

## Consequences

- Live-capable callers must be updated to pass `dry_run=` explicitly.
- The legacy `override_confirmation` contract is removed rather than preserved
  behind wrappers or workflow helpers.
- `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` is superseded by the hardened
  engine model and no longer defines the live-submit contract.
- Live submission fails closed under pytest and without
  `AEAT_LIVE_SUBMIT_ENABLED`, with no test-only override surface.
- Confirmation remains available only through internal engine behavior in
  `_confirm.py`.
- Audit records expand to include both dry-run and live attempts through the
  append-only log in `_audit.py`.
- CLI users invoking `--live` on `_NullSession` surfaces receive an explicit
  refusal until real live wiring is implemented.
- Workflow surfaces become simpler and safer because they inherit the engine
  contract instead of carrying a parallel override mechanism.
- This is a deliberate breaking change in exchange for a clearer, stricter, and
  more auditable live-submit model.
