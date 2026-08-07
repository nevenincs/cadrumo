---
name: cli-notices-are-the-only-diagnostic-channel
trigger: always_on
---

# CLI notices are the only diagnostic channel

Operator-facing non-blocking diagnostics — warnings, advisories, next-step hints
— MUST be emitted through the typed `Notice` channel on the shared CLI envelope
spine (`cadrumo.core.json_contract.Notice`, via `_emit_envelope(...,
notices=[...])` / `emit_json_success(..., notices=[...])`).

A command MUST NOT re-introduce a bespoke advisory, `next`, or `suggestion` field
inside its `result` payload. The shared spine (`schema_version`, `command`,
`status`, `notices`) is uniform across the success envelope and the stderr error
document; `status` derives from notice severity and stays in lock-step with the
`ExitCode` table.

The success and error envelopes were once disjoint with no shared `status`, the
success `warnings` channel was structurally dead, and advisories were smuggled as
bespoke `result` fields — so the contract was un-introspectable and bypassed the
envelope redaction funnel.

## How

- **Good:** an advisory is projected with `advisory_notice(code, message,
  context={...})` and passed via `notices=`, its text line rebuilt from the same
  notice so JSON and text cannot drift. A next-step hint is an `info`-severity
  notice whose `suggestion` is the follow-on command. Structured provenance rides
  on `Notice.context`.
- **Bad:** adding `authorization_advisory`, `source_advisories`, or any
  `*_advisory` / bare `next` / `suggestion` as a top-level field on a registered
  `OutputSchema` — the no-allowlist conformance gate fails until it moves.
- **Allowed:** primary structured result data a command exists to produce —
  verify `findings`, calendar `warnings`, a `next_due` date, a per-finding
  `next_action`. These are output, not incidental diagnostics.

## The operator harness cites only the live surface

Every agent-harness document under `src/cadrumo/_data/agent/` that names a CLI
verb or a JSON-envelope field MUST cite only verbs resolving against the live
operator-surface manifest and fields existing on the live envelope models, and
MUST be co-committed with the CLI surface it couples to.

The harness is the operating layer an LLM tax advisor loads to drive the
deterministic CLI, so a citation to a renamed verb hands the agent a dead
instruction it cannot recover from. A drift gate parses every shipped rule,
persona and skill, extracts each `aeat ...` command path and each named
envelope-spine field, and asserts they resolve — so drift is a loud test failure
rather than silent operator misdirection.

## How

- **Bad:** citing a verb that does not exist, or renaming a CLI verb without
  sweeping the harness documents that cite it.

Enforced by `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`
and `src/cadrumo/agent/tests/test_rule_surface_conformance.py`. Source: ADRs
`2026-06-10-cli-envelope-notice-standardisation-adr`,
`2026-06-30-agent-harness-adr`.
