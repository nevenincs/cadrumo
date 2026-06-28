---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - "[[2026-05-06-live-parity-oracle-backend-research]]"
---


# `cross-reference-oracle-binding` adr: `Bind cross-references to oracles by id` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It addresses the first open
review question raised in the live parity oracle backend ADR: should
modelo cross-references carry the oracle binding as a typed field
rather than as a free-form string?

This ADR depends on the live parity oracle backend ADR and on the
specific adapter ADRs that have already established the
`oracle_id` namespace (Renta WEB Open and AEAT NIF-IVA so far). It
extends the registry schema in a backwards-compatible way; no existing
modelo TOML breaks.

## Problem Statement

The live parity oracle backend uses a process-wide
`LiveParityCatalogue` keyed by `oracle_id`. Each adapter declares
its `oracle_id` as a stable identifier (e.g. `aeat-nif-iva-checker`,
`modelo-100-renta-web-open`).

Modelo registry TOMLs declare `live_cross_references` per revision.
A cross-reference describes one AEAT-side surface the modelo can
interact with under the remote-state guard. When the surface is also
serviced by a registered oracle adapter, callers want to look the
oracle up by id and pre-flight its planned operations against the
cross-reference's policy.

Today the binding lives only in code or convention: a caller hard-codes
the oracle id alongside the cross-reference id. This invites three
classes of drift:

- An oracle id can be misspelled in code without the registry validator
  noticing; the failure surfaces only at calculation time.
- A cross-reference can declare a surface that no registered oracle
  serves; the gap is invisible at registry-load time.
- Two cross-references can claim the same oracle without the registry
  detecting the conflict.

Carrying the oracle binding as a typed field on the cross-reference
itself moves the failure modes left: registry load surfaces unresolved
oracle ids; the validator surfaces double-binding conflicts; the
calculation engine consumes a typed binding rather than reconstructing
it.

## Decision

This ADR proposes the following concrete schema extension.

1. `LiveCrossReferenceDecision` gains one optional field
   `oracle_id: str | None = None`. The default is `None`, preserving
   the behaviour of every existing cross-reference: no oracle is bound
   unless the modelo TOML explicitly declares one.
2. The field is constrained to a non-empty string when present and
   matches the same identifier shape concrete adapters declare for
   their `oracle_id` property (kebab-case, ASCII alphanumerics plus
   hyphens, max length 128 characters).
3. The registry validator does not require the bound oracle to be
   present in the catalogue at registry-load time. Adapter
   registration is process-wide and may be deferred until application
   bootstrap; the registry must remain loadable without the catalogue.
4. The registry validator does require that the bound oracle id, when
   present, conform to the identifier shape and be unique inside a
   single revision. Two cross-references on the same revision cannot
   bind to the same oracle id.
5. Catalogue lookup at calculation time consumes the bound oracle id
   and resolves it through `LiveParityCatalogue.lookup`. Lookup
   failures (unknown id, environment mismatch) are reported as
   structured errors that name the cross-reference id alongside the
   oracle id so callers can diagnose drift.
6. Modelo TOMLs may now declare an `oracle_id` key inside any
   `[[revisions.<id>.live_cross_references]]` table. The key is
   optional; cross-references that do not bind an oracle behave
   exactly as before.
7. The cross-reference's `surface` and `evidence_tier` must remain
   consistent with the bound oracle's `surface_kind`. The registry
   validator does not enforce that consistency yet because the oracle
   surface-kind taxonomy is in code only; consistency enforcement
   arrives in a follow-up ADR that maps cross-reference surfaces to
   oracle surface kinds.

## Constraints

The field must be optional. Existing modelo TOMLs that do not declare
an oracle binding must continue to load and validate with no changes.

The field must be string-typed. The catalogue is keyed by `str`; making
the field a stricter typed alias (e.g. `OracleId`) is left for a
follow-up that introduces the alias project-wide alongside the existing
identifier-type pattern.

The field must not affect remote-state guard policy construction. The
guard policy continues to derive from the cross-reference's existing
fields; the oracle binding is metadata that the calculation engine
consumes separately. A cross-reference can therefore declare a bound
oracle even when its policy classification independently forbids the
oracle's planned operations; the guard's pre-flight is the gate, the
binding is the pointer.

The field must round-trip through the strict frozen Pydantic schema and
through the TOML loader without bespoke parsing. The registry test
surface confirms both round-trips.

## Implementation Direction

Extend `src/aeat/domain/calculations/registry/_schema.py`:

- Add `oracle_id: str | None = Field(default=None, min_length=1, max_length=128)`
  to `LiveCrossReferenceDecision`.
- Add a `field_validator` that enforces the identifier shape
  (lowercase ASCII letters, digits, hyphens; must start with a letter;
  no trailing hyphens) when the value is non-None.

Extend `src/aeat/domain/calculations/registry/_validate.py`:

- During revision validation, collect every non-None
  `oracle_id` declared by the revision's
  `live_cross_references` and reject duplicates with a clear error
  citing both cross-reference ids.

Add `src/aeat/domain/calculations/registry/test_cross_reference_oracle_binding.py`
with the following coverage:

- A cross-reference with no `oracle_id` validates and round-trips
  through the schema.
- A cross-reference with a valid `oracle_id` validates and round-trips
  through the schema.
- A cross-reference with an empty-string `oracle_id` is rejected by
  Pydantic.
- A cross-reference with a malformed `oracle_id` (uppercase, leading
  digit, trailing hyphen) is rejected by the field validator.
- A revision with two cross-references binding to the same
  `oracle_id` is rejected by the registry validator.
- A revision with two cross-references binding to distinct
  `oracle_id`s validates clean.

## Rationale

Typing the binding moves drift detection left. A modelo TOML that
binds to a registered oracle becomes self-describing: the cross-
reference declares the surface, the policy, and the oracle id all in
one place. A modelo TOML that binds to an unregistered oracle still
loads (the catalogue is a runtime concern), but the calculation
engine surfaces the missing-oracle condition through a structured
error that names the offending cross-reference.

The double-binding ban prevents two cross-references on the same
revision from racing for the same oracle. The catalogue permits one
oracle per id, so two cross-references binding to the same id would
silently collapse into one verification path; explicit duplicate
rejection forces the modelo TOML to declare two distinct surfaces
when two distinct oracles are needed.

The decision deliberately stops short of enforcing surface-kind
consistency between the cross-reference and the bound oracle. The
oracle backend's surface-kind taxonomy is in code; enforcing
consistency at registry-load time would couple the registry validator
to the catalogue's import-time state. A follow-up ADR adds that
coupling once the surface-kind to cross-reference-surface mapping is
formalised.

## Consequences

Modelo registry TOMLs gain one optional field. No existing TOML
changes; new bindings are explicit and reviewable.

The registry validator gains one duplicate-binding check per revision.
The check is local to the revision and does not require the
catalogue, so it remains static-analysis-friendly.

The calculation engine gains a typed binding to consume. Adapter
lookups by oracle id can now be sourced from the cross-reference
itself, reducing hard-coded oracle ids in modelo-specific code paths.

The decision opens a follow-up ADR for surface-kind consistency
enforcement and a follow-up ADR for environment-classification
consistency between the cross-reference and the bound oracle (the
catalogue already separates production from test-environment
adapters; ensuring a production cross-reference cannot bind to a
test-environment-only adapter is the next safety closure).

## Explicit Non-Decisions

This ADR does not enforce surface-kind consistency between the cross-
reference and the bound oracle. A follow-up ADR will.

This ADR does not introduce a typed `OracleId` alias. The field is
plain `str | None` for now; a typed alias arrives in a follow-up that
aligns with the project's existing identifier-type pattern.

This ADR does not bind any modelo cross-reference to any oracle. Each
modelo's TOML may opt in to a binding when its parity ledger calls
for it; this ADR only adds the field.

## Open Review Questions

Should the field accept a tuple of oracle ids so a cross-reference
that wants verification through multiple oracles in parallel can
declare them all? The current single-id form is simpler and matches
the existing one-cross-reference-one-surface convention.

Should the field be promoted to a dictionary keyed by oracle id with
optional metadata (e.g., timeout overrides, expected-field schema
selectors)? The current bare-string form is the minimum viable
contract; richer metadata can land in a follow-up.

Should the registry validator also assert that every adapter
registered in the catalogue corresponds to at least one cross-
reference binding somewhere in the registry? That would surface
orphan adapters at registry-load time but would require the
catalogue to be loaded before registry validation runs.
