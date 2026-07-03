---
name: cli-notices-are-the-only-diagnostic-channel
---

# CLI notices are the only diagnostic channel

## Rule

Operator-facing non-blocking diagnostics — warnings, advisories, and next-step
hints — MUST be emitted through the typed `Notice` channel on the shared CLI
envelope spine (`aeat.core.json_contract.Notice`, surfaced via
`_emit_envelope(..., notices=[...])` / `emit_json_success(..., notices=[...])`).
A command MUST NOT re-introduce a bespoke advisory/`next`/`suggestion` field
inside its `result` payload (an `OutputSchema` subclass). The shared spine
(`schema_version`, `command`, `status`, `notices`) is uniform across the success
envelope and the stderr error document; `status` derives from notice severity
and stays in lock-step with the `ExitCode` table.

## Why

The `cli-envelope-notice-standardisation` campaign (ADR
`2026-06-10-cli-envelope-notice-standardisation-adr`) found the success
`SchemaEnvelope` and the stderr `ErrorEnvelope` were disjoint with no shared
`status`, the success `warnings` channel was structurally dead, and non-blocking
advisories were smuggled as bespoke per-command `result` fields
(`source_advisories`, `authorization_advisory`, config `next`) plus duplicated
text lines. That made the contract un-introspectable: a consumer could not read
one shape to learn the outcome or what to do next. The standardisation collapsed
every diagnostic onto one typed `Notice` channel and a shared spine. A new
bespoke advisory field re-fragments the surface and silently bypasses the
redaction funnel that runs over the envelope. The no-allowlist conformance gate
(`test_json_schema_conformance.py`:
`test_registered_schema_has_no_bespoke_notice_field`) makes the regression a
hard CI failure, so the uniformity cannot rot.

## How

- **Good:** a calculate advisory is projected with `advisory_notice(code,
  message, context={...})` and passed via `_emit_envelope(..., notices=[...])`;
  its text line is rebuilt from the same notice so JSON and text cannot drift.
- **Good:** a post-action next-step hint is an `info`-severity `Notice` whose
  `suggestion` is the follow-on command (e.g. the wizard create/edit next step,
  the overview status next-step guidance), not a `next: str` result field.
- **Good:** structured provenance a former bespoke payload exposed
  (`reason`, `source_kind`, `resolver_id`) rides on `Notice.context`
  (mirroring `ErrorEnvelope.context`), so nothing machine-queryable is lost.
- **Bad:** adding `authorization_advisory: str | None` or `source_advisories:
  tuple[...]` (or any `*_advisory` / bare `next` / `suggestion`) as a top-level
  field on a registered `OutputSchema`. The gate fails until it moves to
  `notices`.
- **Allowed (not a violation):** primary structured result data that a command
  exists to produce — verify `findings`, calendar `warnings`, a `next_due` date,
  a per-finding `next_action`. These are the command's output, not incidental
  diagnostics, and the gate's forbidden set is scoped to bare `next` /
  `suggestion` / `*_advisory` precisely to leave them alone.

## Source

ADR `2026-06-10-cli-envelope-notice-standardisation-adr`; plan
`2026-06-10-cli-envelope-notice-standardisation-plan`; exec
`2026-06-10-cli-envelope-notice-standardisation-exec`. Enforced by
`src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
(`test_success_envelope_carries_shared_spine`,
`test_registered_schema_has_no_bespoke_notice_field`,
`test_error_document_shares_the_success_spine`). Companion to
`aeat-calculation-grounding` (provenance through boundaries) and
`no-silent-under-declaration` (an unrouted diagnostic must surface, not vanish).
Promoted per the `vaultspec-codify` discipline once the burndown landed and the
extended conformance gate was green.
