---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-live-parity-oracle-backend-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `live-parity-oracle` adr: `Modelo-agnostic read-only AEAT verification backend` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It formalises the cohesive backend
that every modelo's calculation engine consumes when verifying a
registry-rendered payload against AEAT-published live surfaces. The backend
sits one level above the existing remote-state guard and is a hard
prerequisite for any modelo wave that claims live conformance evidence.

This ADR extends and depends on the parent calculation-truth-registry ADR.
It does not replace any decision in that document; it formalises the runtime
contract for decisions D24, D25, D26, D27 and D28 of the parent ADR by
declaring the modelo-agnostic abstractions through which every concrete
oracle must be implemented.

## Problem Statement

The calculation-truth-registry ADR mandates that every modelo revision
declares a live/static AEAT cross-reference decision and that every live
cross-reference path is protected by a remote-state guard. The remote-state
guard is already implemented as a deny-by-default policy that pins AEAT
hosts, blocks write methods, and rejects forbidden action tokens.

What was missing is the orchestration layer that ties a registry-declared
cross-reference to a concrete verification interaction with an AEAT-published
surface, returns a structured parity verdict, and prevents the implementation
from drifting into an ad-hoc per-modelo network adapter. Without this layer
each modelo wave would re-invent its own oracle adapter, which would
duplicate guard wiring, fragment the parity-result shape, and surface drift
between adapters in subtle correctness bugs.

The architecture must therefore separate three concerns:

- The static cross-reference classification and remote-state policy
  declared in the registry, which is already covered by the parent ADR and
  the existing guard implementation.
- The runtime contract every read-only oracle adapter must satisfy, which
  is the subject of this ADR.
- The concrete oracle adapters that talk to specific AEAT surfaces, which
  are out of scope for this ADR and arrive in follow-up ADRs per surface
  family.

The autonomo workflow leans on this backend because every IVA-relevant
modelo, every IRPF instalment modelo, and every annual summary will need
the same gate: render the synthetic payload from the registry, drive it
through a read-only AEAT verification surface, fold the response back into
a structured verdict, and refuse to leave the process if any planned step
violates the registry's cross-reference policy.

## Decision

This ADR proposes the following concrete architecture.

1. The live parity oracle backend lives under
   `src/aeat/domain/calculations/registry/_live_parity.py` as a
   modelo-agnostic module.
2. The backend exposes a `LiveParityOracle` Protocol with two contractual
   methods: `planned_operations(payload, expected)` and
   `verify_payload(policy, payload, expected)`. Every concrete oracle must
   implement both methods.
3. `planned_operations` must enumerate every HTTP request, browser action
   and local computation the oracle will perform, in execution order, before
   any side-effecting code runs. Concrete oracles must not perform any
   operation that is not present in the planned set.
4. Every planned operation must be pre-flighted through
   `assert_remote_operation_allowed` against the registry-declared
   `RemoteStateGuardPolicy` before the oracle is invoked. The pre-flight
   helper is the single mandatory gate; oracles may not implement their own
   guard logic.
5. Concrete oracles must call the guard at the entry of `verify_payload`
   even when an external caller has already pre-flighted the same plan. The
   guard is the only path through which an oracle can reach AEAT.
6. The canonical oracle response shape is `ParityResult` with verdict in
   the closed enum `match | mismatch | unverifiable | blocked`. AEAT-side
   mismatch is data, not an exception; structural unanswerability is data,
   not an exception; only catastrophic adapter errors raise.
7. The `blocked` verdict represents a refusal by the remote-state guard
   before any operation reached AEAT. Callers must persist the blocked
   verdict as audit evidence of why the conformance check did not run.
8. Per-field comparison evidence travels in `ParityFieldComparison` records
   inside `ParityResult.fields`, with field names unique inside a result.
   Every named field carries an expected and observed string, plus a
   per-field verdict. Raw response evidence is referenced by an opaque
   locator string and stored elsewhere, never inlined in the result.
9. Oracles register themselves in a process-wide `LiveParityCatalogue`
   keyed by `oracle_id`. Duplicate ids are fatal at registration time.
10. Each modelo's registry cross-reference declares the oracle it binds to
    by `oracle_id`. The registry runtime looks the oracle up in the
    catalogue and never instantiates network code by other means.
11. Oracle implementations live in sibling modules so the abstraction stays
    free of network code. A network adapter that fails to import must not
    break the registry validator or the snapshot builder.
12. Each oracle declares one of the following surface kinds, which match
    the cross-reference classifications in the parent ADR:
    `file_validator`, `open_simulator`, `vat_id_check`,
    `pre_filing_validator`, `integration_test_service`. New surface kinds
    require an ADR amendment.
13. The backend forbids any oracle from sending payloads to authenticated
    filing portals, presentation surfaces, signing endpoints, payment or
    direct-debit surfaces, amendment or cancellation surfaces, and document
    submission surfaces. The deny set is inherited from the existing guard
    forbidden-token list and the per-policy forbidden actions; oracles must
    not bypass either.
13a. The backend additionally forbids any oracle that creates server-side
    state at AEAT under an authenticated production NIF, even when that
    state is intermediate and not yet legally binding. AEAT verification
    surfaces such as TGVI online stage uploaded files in a server-side
    `FINALIZED` state pending an explicit presentation step. The
    intermediate state is visible in the NIF's declaration-history
    surfaces, can be configured for substitutive replacement of prior
    filings, and is logged as an upload attempt regardless of whether it
    is later presented. Oracles that interact with such surfaces are
    therefore acceptable only under AEAT-published pre-production or test
    environments that issue dedicated test NIFs, are gated behind an
    explicit test-environment feature flag, and may never be registered
    against the autonomo's real NIF in production. Per-environment
    isolation is implemented at adapter level; the backend treats every
    catalogue-registered oracle as production-safe and refuses to invoke
    any oracle whose adapter does not assert an explicit
    production-or-test environment classification.
14. Oracle implementations must be deterministic and side-effect-free
    locally. They may not write to the filesystem outside an
    explicitly-scoped audit cache, may not mutate process-wide state, and
    may not consume environment-controlled secrets without going through
    the registry's authentication adapter.
15. The backend is the only path through which a calculation engine can
    request live verification of its rendered payload. Bypassing the
    backend to call AEAT directly from filing, calculation, or export code
    is a hard architectural violation.

## Constraints

The backend must remain modelo-agnostic. No oracle implementation may
encode modelo-specific casilla numbers, formula IDs, or revision selectors.
Per-modelo metadata travels through the `expected` mapping and the registry
cross-reference declaration; the oracle interprets it generically.

The backend must remain authentication-agnostic at the abstraction layer.
Concrete oracles that require an authenticated AEAT session declare it
through their cross-reference classification (`authenticated_read_surface`
or `integration_test_service`); the backend does not own the authentication
flow, and the existing remote-state guard refuses any unauthenticated call
to a classification that requires authentication.

A blocked-verdict result must be indistinguishable from a refused execution
from the caller's perspective: both record audit evidence and neither
allows the caller to claim conformance. This prevents an oracle whose plan
was rejected from being mistaken for one that returned a real AEAT
mismatch.

The verification surface inventory must remain a registry artefact, not
hardcoded in code. The catalogue accepts oracles registered at import
time; concrete adapters self-register, the registry binds them to
cross-references by id, and the rest of the runtime operates on identifiers
only.

The backend must never originate write operations against AEAT under any
classification. A `forbidden_stateful_surface` policy must yield a blocked
verdict; a `static_official_only` policy must yield a blocked verdict for
any HTTP or browser operation; an `authenticated_read_surface` policy must
yield a blocked verdict for any non-read-only HTTP method. These are
enforced by the existing guard, but the oracle backend explicitly tests
each refusal path.

## Implementation Direction

Create `src/aeat/domain/calculations/registry/_live_parity.py` with the
`LiveParityOracle` Protocol, the `ParityResult` and
`ParityFieldComparison` records, the `LiveParityCatalogue`, and the
`build_planned_operations`, `pre_flight_oracle_operations`,
`evaluate_planned_operations`, and `assert_oracle_operations_allowed`
helpers.

Create `src/aeat/domain/calculations/registry/test_live_parity.py` with
modelo-agnostic tests that exercise the protocol contract, the catalogue,
and the guard-refusal paths through a synthetic in-memory oracle. The
tests must not touch any real AEAT surface; live tests live in the
per-oracle adapter modules and are gated behind the project live-test
environment variable.

Concrete oracle adapters arrive in follow-up ADRs and live in sibling
modules. The first three priority adapters are an EU VAT-ID checker for
intra-community partner validation, a fixed-width file validator for the
official AEAT file-format validation surface, and a synthetic-input
simulator for the AEAT public open-simulator family. Each adapter ADR
identifies the AEAT surface it consumes, declares its allowed hosts and
HTTP methods, declares its planned operations under a sample policy, and
documents the parity-field schema its responses produce.

The backend is a hard prerequisite for any modelo wave that claims live
conformance evidence. The per-modelo parity ledger gains an explicit
backend-readiness gate: a wave may declare live cross-reference coverage
only when the relevant oracle adapter has been registered in the catalogue
and exercised through the standard contract tests.

## Rationale

A shared oracle backend prevents per-modelo drift in three concrete ways.

First, it prevents drift in remote-state safety. With one pre-flight path
every adapter consumes, a regression in the guard logic surfaces in every
adapter's contract tests at once. Per-modelo adapters with their own guard
wiring would surface guard regressions one modelo at a time and only when
that modelo's tests run.

Second, it prevents drift in result shape. With one canonical
`ParityResult` shape, audit records, observation stores, ledger reports,
and human review surfaces consume one schema. Per-modelo result shapes
would produce inconsistent audit evidence and would force every consumer
to handle every shape.

Third, it prevents drift in surface classification. The closed enum of
oracle surface kinds matches the cross-reference classifications in the
parent ADR. New AEAT surface families require an ADR amendment, which
forces a documented decision rather than a silent capability addition.

The backend is read-only by construction. The architecture cannot be
extended into write operations without redefining the
`RemoteStateGuardPolicy` deny-by-default behaviour, redefining the
forbidden-token list, and redefining the closed enum of surface
classifications. None of those redefinitions are accessible to oracle
implementations; only the parent ADR and a follow-up ADR amendment can
authorise them.

## Consequences

Every modelo wave gains a single integration point for live verification.
Adding a new modelo to the live conformance set is a registry-only change:
declare the cross-reference, bind it to a registered oracle id, list the
expected fields. No new network code is required for any modelo whose
verification surface has an existing adapter.

The backend imposes a process-wide invariant that no live AEAT call leaves
the calculation engine without going through the guard. Application,
filing, review, export, CLI, and adapter code that needs live AEAT data
must consume an oracle from the catalogue. Direct HTTP calls to AEAT from
calculation-engine code are forbidden.

The backend creates a discoverable inventory of every live AEAT surface
the project consumes. The registry can audit the catalogue, the
cross-reference set, and the oracle-id bindings to enumerate exactly which
AEAT surfaces are touched and under which classification.

The backend imposes an explicit per-adapter rollout cost. Each new oracle
adapter requires an adapter ADR, allowed-host declarations, planned-
operation enumeration, contract tests, and live tests gated behind the
live-test environment variable. This cost is intentional: it is the price
of preventing ad-hoc network code in the calculation engine.

The backend leaves remote-write capability strictly out of scope. Filing
remains gated by the parent ADR's hard prohibitions and by the existing
remote-state guard. The oracle backend will never be the path through
which a payload reaches AEAT for presentation, signing, payment, or
amendment.

## Explicit Non-Decisions

This ADR does not approve any concrete oracle adapter. Each adapter
arrives in its own ADR.

This ADR does not redefine the cross-reference classification taxonomy.
The closed enum matches the parent ADR.

This ADR does not relax any remote-state guard rule. The backend is
strictly additive to the guard and may not be configured to bypass it.

This ADR does not authorise authenticated write surfaces under any
classification.

## Open Review Questions

Should the catalogue support per-environment isolation, so that contract
tests in CI do not pick up oracle adapters whose registration depends on
optional dependencies that are absent in CI?

Should `ParityResult.raw_evidence_locator` be required for verdict
`mismatch`, so that every recorded mismatch has a recoverable AEAT
response artefact?

Should every oracle adapter be required to declare a
read-only-replay-fixture path so contract tests can run offline against a
captured AEAT response without ever reaching the network?
