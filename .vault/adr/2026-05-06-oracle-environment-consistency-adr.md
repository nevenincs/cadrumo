---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-cross-reference-oracle-binding-adr]]'
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]'
  - "[[2026-05-06-live-parity-oracle-backend-research]]"
---


# `oracle-environment-consistency` adr: `Verify cross-reference oracle bindings against catalogue at boot` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It addresses the second open
review question raised in the live parity oracle backend ADR: how do
we surface the situation where a modelo cross-reference binds to an
oracle that the catalogue does not vend under the requested
environment?

The cross-reference oracle binding ADR established the
``oracle_id`` field on ``LiveCrossReferenceDecision`` and noted that
catalogue lookup remained a runtime concern. The runtime resolver
covers per-call lookups but not the modelo-wide audit pass. That is
the gap this ADR closes.

## Problem Statement

A bound oracle id is declarative; the catalogue at runtime is the
authority for which adapters are actually registered and under which
environment. Three failure modes can hide between them:

- A modelo TOML binds to an oracle id that no adapter registers
  (typo, deferred adapter, removed ADR). The runtime surfaces it on
  the first calculation that touches the cross-reference; until then
  the modelo looks healthy.
- A modelo TOML binds to a test-environment-only adapter (e.g., a
  pre-production AEAT integration test service) but the calling
  context is production. The catalogue lookup raises, but only after
  some other production-side work has already been done.
- A modelo TOML binds to a production-only adapter from a context
  that is exercising test-environment flows. The same lookup error
  surfaces in the opposite direction.

All three are catalogue-aware checks: the registry alone cannot tell
whether an oracle id resolves under a given environment, and the
catalogue alone has no view of which cross-references claim which
oracle ids. The natural place to bridge them is a single function
that takes both and returns a structured failure list per modelo.

A boot-time audit pass is the appropriate moment for this check.
Application bootstrap loads both the registry and the catalogue
before any calculation runs; running the audit there surfaces every
binding-vs-catalogue mismatch up front, in one report, rather than
piecemeal during downstream calculation work.

## Decision

This ADR proposes the following concrete addition.

1. A new function `audit_oracle_bindings` lives in `_live_parity.py`
   alongside the resolver. It takes a single modelo definition, a
   catalogue, and an explicit environment context, and returns a
   tuple of failure strings (one per offending cross-reference). The
   return type is a tuple, not a raise, because the calculation
   engine wants to aggregate failures across many modelos before
   surfacing them.
2. The function iterates every revision of the modelo and every
   cross-reference of every revision. Cross-references without an
   ``oracle_id`` binding are skipped silently. Cross-references with
   a binding are looked up through the catalogue; lookup failures
   are converted into failure strings that name the modelo id, the
   revision id, the cross-reference id, the bound oracle id, and the
   underlying catalogue error.
3. A second function `audit_registry_oracle_bindings` takes an
   iterable of modelo definitions plus the catalogue and the
   environment, runs `audit_oracle_bindings` over every modelo, and
   returns the aggregate failure list. Application bootstrap calls
   this once per startup and stores the failures alongside the
   registry-validation failures.
4. Neither function performs any network operation. Both rely
   entirely on the catalogue's existing lookup contract for
   environment filtering and unknown-oracle detection.
5. Neither function modifies the registry or the catalogue. They are
   pure inspectors, safe to run at any point and re-run without side
   effects.
6. Failure messages are stable strings designed for direct logging
   and for inclusion in registry-health reports. They name every
   identifier needed to diagnose the mismatch from the message
   alone, with no requirement to consult the calling context.

## Constraints

The audit must not require the catalogue to be fully populated. A
modelo whose oracles have not been registered yet (e.g., adapters
gated on Playwright drivers landing in follow-up commits) would
otherwise emit spurious failures during the gap between schema-field
adoption and adapter registration. To handle this cleanly the audit
runs only when the caller commits to a non-empty catalogue; callers
that pass an empty catalogue are signalling "no audit yet" and the
function returns an empty failure tuple.

The audit must not couple the registry validator to the runtime
catalogue. The runtime catalogue is a process-level singleton in
practice; importing it from the registry validator would re-introduce
the coupling the previous ADR explicitly avoided. The audit therefore
lives in `_live_parity.py`, where the catalogue type already lives,
and the registry validator stays catalogue-free.

The audit must not raise on the first failure. It must aggregate so
the caller sees every binding mismatch in one report. This mirrors
the existing registry-validator's failure-list pattern.

## Implementation Direction

Extend `src/aeat/domain/calculations/registry/_live_parity.py`:

- Add `audit_oracle_bindings(modelo, catalogue, *, environment)` that
  returns `tuple[str, ...]`. Iterate revisions, then cross-references.
  For each cross-reference with a non-None ``oracle_id``, attempt
  ``catalogue.lookup(oracle_id, environment=environment)`` inside a
  ``try`` that converts the resulting ``RegistryValidationError`` into
  a failure string of the form
  ``"modelo {modelo_id} revision {revision_id} cross-reference
  {cross_ref_id} bound oracle {oracle_id}: {underlying_message}"``.
- Add `audit_registry_oracle_bindings(modelos, catalogue, *,
  environment)` that aggregates per-modelo audits.
- Both functions short-circuit to an empty tuple when the catalogue
  reports no registered oracles, so the boot-time audit is a no-op
  during the field-addition / adapter-registration handoff.

Add `src/aeat/domain/calculations/registry/test_audit_oracle_bindings.py`
with the following coverage:

- A modelo with no cross-reference bindings produces an empty audit.
- A modelo with a single binding to a production-registered oracle
  produces an empty audit under the production environment.
- A modelo with a single binding to a test-environment-only oracle
  produces a failure under the production environment that names
  the modelo, revision, cross-reference, oracle id, and "test_environment".
- A modelo with a single binding to an unregistered oracle produces
  a failure that names the modelo, revision, cross-reference, oracle
  id, and "unknown".
- Aggregation across two modelos preserves both failure strings in
  a single tuple.
- An empty catalogue produces an empty audit, regardless of how
  many bindings the registry declares.

## Rationale

The audit is intentionally pure inspection. Every failure mode it
detects is already detected by the runtime resolver on first call;
the audit's value is detecting all of them at once at boot, before
the application accepts any calculation request. This shifts the
diagnostic horizon left without coupling the registry validator to
the catalogue.

The empty-catalogue short-circuit keeps the audit silent during
adapter rollout. The previous ADR deliberately allowed modelo TOMLs
to declare bindings before adapter registration lands; surfacing
spurious failures during that gap would punish the very rollout
pattern the previous ADR enabled.

The aggregate function mirrors the registry validator's
failure-list pattern, so application bootstrap can fold both into a
single startup report.

## Consequences

The live-parity module gains two pure inspection functions and one
test module. No registry data changes, no validator coupling
changes, no schema changes.

The runtime gains a single boot-time pass it can run before
calculations start. The pass surfaces every binding-vs-catalogue
mismatch in one report. The pass is opt-in: applications that do
not call it continue to depend on per-call resolver errors only,
matching today's behaviour.

The audit does not enforce surface-kind consistency between the
cross-reference's surface and the oracle's surface_kind. That
consistency check is still left to a later ADR, as noted in the
binding ADR.

## Explicit Non-Decisions

This ADR does not raise on first failure. The audit aggregates and
returns a tuple; the caller decides how to surface failures.

This ADR does not load or wire the catalogue automatically. The
caller passes the catalogue explicitly; this preserves the existing
boundary between registry data and runtime adapter state.

This ADR does not enforce surface-kind consistency. That coupling
is the subject of a later ADR.
