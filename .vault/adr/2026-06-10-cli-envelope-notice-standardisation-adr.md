---
tags:
  - '#adr'
  - '#cli-envelope-notice-standardisation'
date: '2026-06-10'
related:
  - "[[2026-06-10-cli-envelope-notice-standardisation-research]]"
  - "[[2026-06-02-emit-envelope-schema-burndown-adr]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-06-01-envelope-conformance-gate-adr]]"
---

# `cli-envelope-notice-standardisation` adr: `Shared outer-key envelope spine with status and typed notices` | (**status:** `accepted`)

## Problem Statement

The `emit-envelope-schema-burndown` rollout standardised the CLI's **success
payload shape**: every leaf command emits a registered `OutputSchema` through
`_emit_envelope`, enforced by a no-allowlist symmetric-diff conformance gate.
That work is complete. It did **not** standardise the surrounding return
contract — status, warning/failure modes, and the hints/lints/suggestions
surface. The grounding research records the gap: the success `SchemaEnvelope`
and the stderr `ErrorEnvelope` are disjoint shapes with no shared `status`
discriminator; the success `warnings` channel is structurally dead (the
`_emit_envelope` helper has no `warnings` parameter and zero call sites
populate it); non-blocking advisories are modelled as bespoke per-command
fields inside `result` (`source_advisories`, `authorization_advisory`) and
duplicated as text lines; next-step hints are scattered across per-payload
`next:` fields, overview guidance text, and locale prose; and a refusal path
(`_active_profile_or_exit`) still leaks a third, un-enveloped `{error, next}`
shape. A machine consumer cannot read one contract to learn whether a command
succeeded, what it warned about, or what to do next.

This ADR records the decision to give every CLI return document — success and
error alike — a **shared outer spine** carrying `status` and a single typed
`notices` channel, and to migrate the scattered advisory/hint surfaces onto it.

## Considerations

- **Shared spine vs. full unification.** A single collapsed envelope (one shape
  with optional `result` and optional `error`) maximises uniformity but forces
  every success consumer to tolerate a nullable `error` and inflates the error
  boundary's blast radius. The shared-spine option keeps `result` (success) and
  `error` (failure) as distinct bodies under common outer keys, which aligns
  the contract without a nullable-everything shape. Chosen: shared spine.
- **The domain already owns severity.** `ModeloFinding` (`WARNING` /
  `BLOCKING`), the `source_advisories` diagnostics, the RETMAR mandatory-filing
  warning, and the revision-stamp advisory are existing typed, severity-bearing
  records. The CLI should *project* these into the notice channel, not
  re-model them per command.
- **Exit codes are sound.** `ExitCode` and `get_error_exit_code(category)` are
  already centralised and uniform; the new `status` derives from the same table
  so the JSON `status` and the shell exit code can never disagree.
- **Text-mode output is an operator-UX invariant.** As in the burndown, the
  envelope change touches the JSON shape only; rendered text output per command
  stays byte-identical and is guarded per command.

## Constraints

- No frontier risk: the change is local pydantic-v2 model edits plus a helper
  signature change and a conformance-gate extension; all libraries are mature
  and in-cutoff.
- Parent-feature stability: this depends on the **completed**
  `emit-envelope-schema-burndown` (231 migrated sites, gate green) and the
  `envelope-conformance-gate` no-allowlist gate. Both are landed and stable, so
  there is no blocking upstream gap.
- The `centralized-output-redaction` profile consumes typed payloads; the
  `notices` channel MUST pass through the same field-redaction funnel
  (`redact_structured_for_cli_output`) so a notice cannot leak a secret.
- `schema_version` MUST move to a single coordinated value shared by both
  envelopes; bumping it remains a contract-breaking change owned by the gate,
  not a casual edit.
- Migration is one Step per (bespoke-field removal + notice projection). A
  command that keeps a bespoke advisory field after its notice projection lands
  fails the extended gate. No half-migration states.

## Implementation

A new typed `Notice` model (strict, frozen) carries a closed `severity`
(`info` | `warning`), a stable `code`, a `message`, and an optional
`suggestion` / `next` recovery or follow-on action. It is the single channel
for non-blocking warnings, advisories, and next-step hints.

Both return documents gain the shared outer keys `schema_version`, `command`,
`status`, and `notices: list[Notice]`:

- **Success** (`SchemaEnvelope`) keeps `result`; `status` is derived
  (`warning` when any notice is warning-severity, else `success`). The dead
  `warnings: list[str]` field is removed in favour of `notices`.
- **Error** (`ErrorEnvelope`) gains `command`, `status` (always `error`), and
  `notices`; its existing `error` body (`code`, `category`, `message`,
  `suggestion`, `retryable`, `runbook_id`, `trace_id`) is retained, nested
  consistently under the spine.

`_emit_envelope` gains a `notices=` parameter and computes `status` from the
notice severities. Domain `ModeloFinding` / advisory records are mapped into
`Notice` by a small projection helper rather than re-modelled at each call
site. The scattered surfaces — `source_advisories`, `authorization_advisory`,
config `next:` fields, and the overview next-step guidance — are migrated onto
the `notices` channel, and their duplicated text-line emitters are rebuilt from
the same notices so text and JSON cannot drift. The `_active_profile_or_exit`
refusal is routed through the typed refusal/error path so no un-enveloped shape
remains.

The conformance gate is extended to assert (1) every emitted document carries
the outer spine with a valid `status`, and (2) no registered `OutputSchema`
re-introduces a bespoke advisory/`next`/`suggestion` field outside the
`notices` channel — making the uniform channel the only sanctioned surface.

The rollout is an L3 burndown plan modelled on `emit-envelope-schema-burndown`:
one Wave for the contract+helper+gate foundation, then per-command-group Waves
migrating the bespoke fields, each Step closing with the gate green and the
per-command text invariant held.

## Rationale

The shared-spine shape gives a machine consumer one set of outer keys to read
regardless of outcome, with `status` as the single discriminator, while keeping
the success and error bodies cleanly separated (research F2). Folding the dead
`warnings` slot and the per-command advisory fields into one typed `Notice`
channel removes the "smuggle diagnostics inside `result`" anti-pattern
(research F3, F4) and gives hints/suggestions a uniform home alongside the
already-structured error suggestions (research F5). Deriving `status` from the
existing `ExitCode` table keeps the JSON and shell contracts in lock-step
(research F7). Routing the last refusal through the typed path closes the
residual un-enveloped surface (research F6). Reusing the burndown's
one-Step-per-site discipline and no-allowlist gate makes the migration
auditable and regression-proof.

## Consequences

- Every operator-facing command exposes a uniform, introspectable contract:
  outcome (`status`), payload-or-error body, and a single `notices` list for
  warnings/advisories/hints. New consumers read one shape.
- The extended gate makes "a command re-grows a bespoke advisory field" a hard
  CI failure, so the uniformity cannot silently rot.
- Cost: the contract edit touches the 231 success sites at the helper boundary
  (mostly mechanical — most sites pass no notices) plus the bounded set of
  commands that currently carry bespoke advisory/hint fields. The error
  boundary changes once. Removing `SchemaEnvelope.warnings` and bumping
  `schema_version` is a deliberate breaking change to the JSON contract,
  acceptable under the project's zero-legacy / pre-beta posture.
- Opens the path for the redaction profile to classify notice fields uniformly,
  and for future per-notice runbook linkage mirroring the error `runbook_id`.

## Codification candidates

- **Rule slug:** `cli-notices-are-the-only-diagnostic-channel`.
  **Rule:** Operator-facing non-blocking diagnostics (warnings, advisories,
  next-step hints) MUST be emitted through the typed `Notice` channel on the
  shared envelope spine; a command MUST NOT re-introduce a bespoke
  advisory/`next`/`suggestion` field inside its `result` payload. (Promote only
  after the burndown lands and the extended conformance gate is green.)
