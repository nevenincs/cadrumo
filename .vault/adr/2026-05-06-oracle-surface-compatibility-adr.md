---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-oracle-environment-consistency-adr]]'
  - '[[2026-05-06-cross-reference-oracle-binding-adr]]'
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]'
  - "[[2026-05-06-live-parity-oracle-backend-research]]"
---


# `oracle-surface-compatibility` adr: `Reject oracle bindings whose surface_kind is incompatible with the cross-reference surface` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It closes the third
follow-up item explicitly named in both the cross-reference oracle
binding ADR and the oracle environment consistency ADR: surface-kind
consistency between a cross-reference's declared surface and the
bound oracle's `surface_kind`.

The previous two ADRs deliberately stopped short of this check
because the oracle surface-kind taxonomy lives in code while the
cross-reference surface taxonomy lives in the schema. With both
taxonomies stable and the boot-time audit pass already in place,
the compatibility table is the natural extension that closes the
gap without introducing new infrastructure.

## Problem Statement

A modelo cross-reference declares a `surface` from the registry
schema's controlled vocabulary
(`open_simulator`, `integration_test_service`,
`public_read_surface`, `authenticated_read_surface`,
`static_official_documentation`). An oracle adapter declares a
`surface_kind` from the live-parity backend's controlled vocabulary
(`file_validator`, `open_simulator`, `vat_id_check`,
`pre_filing_validator`, `integration_test_service`). The two
taxonomies overlap but are not identical; they describe the same
real-world surfaces from two angles.

A binding can be syntactically valid (registered oracle, compatible
environment) yet semantically wrong:

- A cross-reference declared as `static_official_documentation` cannot
  be serviced by any oracle, because static-doc surfaces produce no
  verifiable response. Binding such a cross-reference to any oracle
  is a registry mistake the audit must surface.
- A cross-reference declared as `authenticated_read_surface` cannot
  be serviced by an `open_simulator` oracle, because open simulators
  by definition require no authentication. The two surfaces describe
  different AEAT services; binding one to the other masks the
  contract drift.
- A cross-reference declared as `public_read_surface` is correctly
  serviced by `vat_id_check` (the AEAT NIF-IVA case: a public
  read surface that proxies to VIES) and by `file_validator` (a
  public read surface that validates uploaded payloads), but is
  *not* correctly serviced by `pre_filing_validator` (which
  inherently requires authentication and a draft session under the
  autonomo's NIF — that is the `authenticated_read_surface`
  contract).

Without an explicit compatibility table, these mistakes hide until
calculation time and produce confusing failures that look like
catalogue or guard-policy bugs.

## Decision

This ADR proposes the following concrete addition.

1. A module-level constant in `_live_parity.py` named
   `_COMPATIBLE_SURFACE_PAIRS` declares the allow-list of
   compatible (cross-reference surface, oracle surface_kind) pairs.
   The constant is a `frozenset` of two-tuples; only the pairs
   listed are valid bindings.
2. The initial allow-list contains the following pairs, derived from
   the surfaces both taxonomies actually describe today:
   - `("open_simulator", "open_simulator")`
   - `("integration_test_service", "integration_test_service")`
   - `("public_read_surface", "vat_id_check")`
   - `("public_read_surface", "file_validator")`
   - `("authenticated_read_surface", "pre_filing_validator")`
3. The constant deliberately omits `static_official_documentation`
   from every pair: static-doc surfaces have no verifiable response
   and cannot be the target of any oracle. Any cross-reference whose
   surface is `static_official_documentation` is rejected if it
   declares an oracle binding.
4. The check lives inside the existing `audit_oracle_bindings`
   function. It runs only when the catalogue lookup succeeds (no
   double-reporting on already-failing bindings) and emits a
   distinct failure-message shape that names the cross-reference
   surface alongside the oracle surface_kind so the diagnosis is
   unambiguous.
5. Adding a new oracle surface_kind or new cross-reference surface
   in a follow-up commit must extend the allow-list as part of the
   same commit. The compatibility table is the contract; bypassing
   it is a registry mistake.

## Constraints

The compatibility table must be conservative. Pairs are added only
when the surface combination is operationally known to be safe and
to produce a verifiable response under the existing remote-state
guard policy classifications. Speculative pairs are not added until
a concrete adapter or cross-reference exercises them.

The check must not rely on importing schema types into the live-
parity module beyond what is already imported. The cross-reference
surface is read from the cross-reference instance's already-typed
attribute; the table itself stores plain string literals so the
constant has no schema dependency at module-load time.

The check must not double-report. A cross-reference whose oracle
lookup already failed (unknown id or environment mismatch) is
already accounted for and the surface-kind check is skipped for
that binding. The audit emits at most one failure per cross-
reference per audit pass.

The failure message must name both surfaces. Compatibility errors
are subtle; the message must show the registry-side surface and
the oracle-side surface_kind in the same string so the diagnosis
does not require consulting two files.

## Implementation Direction

Extend `src/aeat/domain/calculations/registry/_live_parity.py`:

- Add `_COMPATIBLE_SURFACE_PAIRS: frozenset[tuple[str, str]]` at
  module level, populated with the five pairs listed above.
- Inside `audit_oracle_bindings`, after a successful catalogue
  lookup, check that
  `(cross_reference.surface, oracle.surface_kind)` is in the
  constant. On miss, append a failure string of the form
  ``"modelo {modelo_id} revision {revision_id} cross-reference
  {cross_ref_id} surface {surface!r} is not compatible with oracle
  {oracle_id!r} surface_kind {kind!r}"``.
- The constant is fileprivate (leading underscore); follow-up ADRs
  that want to extend the table do so by editing this constant in
  the same commit that introduces the new surface combination.

Add `src/aeat/domain/calculations/registry/test_audit_oracle_surface_compatibility.py`
with the following coverage:

- A binding whose (surface, surface_kind) pair is in the allow-list
  produces no failure.
- A binding whose surface is `static_official_documentation`
  produces a failure that names both surfaces.
- A binding whose surface is `authenticated_read_surface` and
  whose oracle surface_kind is `open_simulator` produces a failure
  that names both surfaces.
- A binding that already fails the catalogue lookup does not also
  emit a surface-compatibility failure (no double-reporting).
- The full allow-list of compatible pairs all pass.

## Rationale

A frozen module-level constant is the smallest representation of a
mapping that does not require new infrastructure. The audit pass
already iterates every cross-reference; adding one tuple-membership
check inside the existing loop is a one-line extension of an
already-tested function.

The five-pair initial allow-list captures every (surface,
surface_kind) combination that committed adapter ADRs justify
(`open_simulator` for the Renta WEB Open simulator, `vat_id_check`
for the AEAT NIF-IVA checker) plus three combinations that future
adapter ADRs are expected to land
(`integration_test_service`, `file_validator` on
`public_read_surface`, and `pre_filing_validator` on
`authenticated_read_surface`). Each future ADR that introduces a
new combination amends the table in the same commit, keeping the
contract centralised.

`static_official_documentation` is excluded from every pair by
construction. Static-doc surfaces are pointers to BOE/AEAT
publications; they cannot be queried, validated, or simulated.
Binding any oracle to such a surface is a category error.

The decision to keep the check inside `audit_oracle_bindings`
rather than introducing a separate `audit_surface_compatibility`
function avoids duplicate iteration and keeps the audit's contract
("one failure per cross-reference per audit") intact.

## Consequences

The live-parity module gains one frozen constant and a few lines
inside the existing audit function. No registry data changes, no
schema changes, no validator coupling changes.

The audit's failure-string vocabulary grows by one shape (the
surface-incompatibility shape). Application bootstrap that already
consumes audit output continues to work without changes; the new
shape is treated like any other audit failure.

Future oracle adapters that target a new surface combination must
amend the compatibility table or their bindings will fail the
audit. This is intentional: the table is the contract.

## Explicit Non-Decisions

This ADR does not refactor the surface-kind or cross-reference
surface taxonomies. Both stay as they are.

This ADR does not promote the constant to a public name. The check
is internal to the audit; callers do not need to query the table
directly.

This ADR does not enforce surface compatibility at registry-load
time. The compatibility check remains a runtime audit because the
oracle surface_kind is read from the catalogue, which the registry
validator deliberately does not depend on.
