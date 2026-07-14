---
name: cli-notices-are-the-only-diagnostic-channel
trigger: always_on
---

# CLI notices are the only diagnostic channel

## Rule

Operator-facing non-blocking diagnostics — warnings, advisories, and next-step
hints — MUST be emitted through the typed `Notice` channel on the shared CLI
envelope spine (`cadrumo.core.json_contract.Notice`, via `_emit_envelope(...,
notices=[...])` / `emit_json_success(..., notices=[...])`). A command MUST NOT
re-introduce a bespoke advisory/`next`/`suggestion` field inside its `result`
payload (an `OutputSchema` subclass). The shared spine (`schema_version`,
`command`, `status`, `notices`) is uniform across the success envelope and the
stderr error document; `status` derives from notice severity and stays in
lock-step with the `ExitCode` table.

## Why

ADR `2026-06-10-cli-envelope-notice-standardisation-adr` found the success
`SchemaEnvelope` and stderr `ErrorEnvelope` disjoint with no shared `status`, the
success `warnings` channel structurally dead, and advisories smuggled as bespoke
`result` fields (`source_advisories`, `authorization_advisory`, config `next`) —
so the contract was un-introspectable and bypassed the envelope redaction funnel.
The no-allowlist conformance gate `test_json_schema_conformance.py`
(`test_registered_schema_has_no_bespoke_notice_field`) makes the regression a hard
CI failure.

## How

- **Good:** a calculate advisory is projected with `advisory_notice(code, message,
  context={...})` and passed via `_emit_envelope(..., notices=[...])`, its text
  line rebuilt from the same notice so JSON and text cannot drift; a next-step hint
  is an `info`-severity `Notice` whose `suggestion` is the follow-on command, not
  a `next: str` result field; structured provenance (`reason`, `source_kind`,
  `resolver_id`) rides on `Notice.context`.
- **Bad:** adding `authorization_advisory: str | None`, `source_advisories:
  tuple[...]`, or any `*_advisory` / bare `next` / `suggestion` as a top-level
  field on a registered `OutputSchema` — the gate fails until it moves to `notices`.
- **Allowed (not a violation):** primary structured result data a command exists
  to produce — verify `findings`, calendar `warnings`, a `next_due` date, a
  per-finding `next_action`. These are output, not incidental diagnostics; the
  gate's forbidden set is scoped to bare `next` / `suggestion` / `*_advisory`.

## Source

ADR/plan/exec `2026-06-10-cli-envelope-notice-standardisation-*`. Enforced by
`src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`
(`test_success_envelope_carries_shared_spine`,
`test_registered_schema_has_no_bespoke_notice_field`,
`test_error_document_shares_the_success_spine`).
