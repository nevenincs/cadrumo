---
tags:
  - '#adr'
  - '#emit-envelope-schema-burndown'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
  - "[[2026-05-28-centralized-output-redaction-plan]]"
  - "[[2026-06-02-centralized-output-redaction-audit]]"
  - '[[2026-06-04-emit-envelope-schema-burndown-research]]'
---

# `emit-envelope-schema-burndown` adr: `emit-envelope schema burndown rollout` | (**status:** `accepted`)

## Problem Statement

The original `json-output-contract` ADR (2026-04-25) established the
operator-facing CLI JSON envelope contract: every command emits a
strict pydantic `OutputSchema` subclass, registered under
`@register_schema(command_path)`, and routed through the
`_emit_envelope` central helper rather than ad-hoc `_emit` /
`typer.echo` writes. The contract is enforced by the symmetric-
difference conformance gate
`test_json_schema_conformance::test_zero_bare_emit_sites_outside_exemption_set`.

When the contract was first ratified, dozens of operator commands
across the ledger, modelo, config, overview, registry, and live
surfaces still emitted untyped payloads through bare `_emit`. This
ADR records the burndown decision: enumerate every bare-emit site,
author the matching `OutputSchema` subclass beside the command
group's existing payload module, migrate the emit call site to
`_emit_envelope` with the typed payload, and register the schema in
the central registry. The burndown rolls out as the
`emit-envelope-schema-burndown` plan (208 Steps across 6 Waves; one
Wave per command-group surface).

## Considerations

- Every migration is a closed-loop change: payload class authored;
  emit site migrated; conformance gate re-run. No half-migration
  states.
- The `MIGRATED_COMMANDS` allow-list in the conformance gate
  shrinks monotonically; once a command is migrated, the conformance
  gate's symmetric-diff check makes regression impossible.
- Some sites are not migration candidates and are explicitly
  excluded (the wizard runner's transport `_emit` is not an
  operator-facing payload surface; the observability sink's `_emit`
  is a test seam, not the CLI emit helper). The exclusion list is
  documented in the conformance gate.

## Constraints

- Migrations MUST be one Step per (payload-class + emit-site) pair.
  A class without a matching emit-site migration is dead code; an
  emit-site change without the typed class fails the conformance
  gate.
- Each command path the burndown migrates MUST keep its existing
  rendered-text output identical (operator UX invariant). The
  envelope contract changes the JSON shape; it does NOT change the
  text-mode rendering. Tests guard this on every migrated command.
- The translation of command paths into kebab-case identifiers is
  fixed by the central registry; the burndown does NOT rename
  command paths.

## Implementation

For each Wave (one Wave per command group — `_ledger`, `_modelo`,
`_overview`, `_config.profile_censo`, `_config.google`,
`_registry_corpus`, etc.), the burndown:

1. Audits the command-group module for every `_emit(ctx, payload,
   lines)` call site.
2. For each site, designs an `OutputSchema` subclass whose field
   set matches the payload dict literally (strict, frozen, extra
   forbidden), and decorates it with
   `@register_schema(command_path)`.
3. Migrates the call site to
   `_emit_envelope(ctx, command=command_path, result=typed_result,
   lines=lines)`.
4. Re-runs the conformance gate and a focused per-command pytest
   pass before moving to the next site.

The plan's 208 Steps are partitioned across Waves so independent
command groups can be migrated in parallel. Waves whose emit sites
share a payload module (e.g. all four censo commands writing to
`_profile_censo_payloads.py`) are ordered together to keep each
commit atomic.

## Rationale

A typed envelope per command makes the CLI's contract auditable in
one place (the symmetric-diff conformance gate) rather than scattered
across every emit site. The same typed boundary that gates JSON
shape also gates field-level redaction policy (companion
`centralized-output-redaction` rollout), so the burndown is a
prerequisite for the redaction wave: only typed payloads can carry
the per-field sensitivity classification the redaction profile
consumes.

The plan is split into per-command-group Waves because the migrations
are independent: each Wave owns a payload module and a CLI module
pair, so commits and tests scope to one Wave without crossing
boundaries.

## Consequences

- Every operator-facing command has a discoverable JSON shape via
  `register_schema`; new consumers can introspect the central
  registry instead of grepping emit call sites.
- The conformance gate's symmetric-diff check enforces "no new bare
  emit sites land without the typed payload and registration."
- Migrating later means more sites are still on the bare path, so
  redaction policy can leak there until each is migrated. This ADR
  treats burndown completion as a precondition for "all surfaces
  carry redaction policy uniformly."
- The exclusion list (wizard transport, observability sink test
  seam) is intentionally short and documented; expanding it
  requires explicit ADR amendment.

## Codification candidates

None this pass. The `OutputSchema` + `register_schema` discipline
is already codified in the parent json-output-contract ADR; this
rollout ADR records the per-Wave execution decision rather than a
new framework-wide rule.
