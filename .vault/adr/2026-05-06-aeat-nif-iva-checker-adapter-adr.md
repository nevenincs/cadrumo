---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-06-live-parity-oracle-backend-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `aeat-nif-iva-checker-adapter` adr: `AEAT NIF-IVA other-EU-countries verification adapter` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It is the first concrete oracle
adapter under the live parity oracle backend that targets an
intra-community VAT-identifier verification surface, and it deliberately
routes through AEAT's own public NIF-IVA verification page rather than the
European Commission's VIES service directly.

This ADR depends on the live parity oracle backend ADR. It does not modify
any decision in that document; it provides a concrete adapter that
satisfies the backend's Protocol contract while staying inside the
existing remote-state-guard host-pinning policy without expansion.

## Problem Statement

Modelo 349 declares one Tipo 2 record per intra-community operator-and-
clave pair, with each record carrying the operator's EU VAT identifier
(positions 76-92 in the official record-design). The validity of that VAT
identifier under EU rules is the legal precondition for every Tipo 2
record. The same precondition applies to Modelo 303 exempt
intra-community deliveries, Modelo 369 OSS/IOSS returns, and Modelo 390
annual summaries that aggregate Modelo 303 deliveries.

The canonical source of EU VAT-identifier validity is the European
Commission's VIES service. AEAT delegates to VIES from inside its own
public NIF-IVA verification surface and explicitly references VIES in the
Modelo 349 procedure documentation. Two architectural paths therefore
exist for the first VAT-identifier oracle adapter:

- Hit VIES directly at ec.europa.eu under the `taxation_customs/vies`
  path. Cleanest authority chain, but requires extending the
  remote-state-guard's host-pinning allow-list to include a non-AEAT
  host. The host-pinning constant is a controlled safety surface; expanding
  it is a deliberate decision that requires explicit human authorisation
  and a separate ADR.
- Hit AEAT's own public NIF-IVA verification surface. Same verdict
  authority (AEAT delegates to VIES under the hood) but the surface is
  hosted at sede.agenciatributaria.gob.es, so the existing host-pinning
  policy admits the operation without any expansion. Mirrors the
  `_renta_web_open_oracle.py` precedent, which already targets sede
  hosts.

This ADR commits to the AEAT-side surface for the first adapter slice.
The EU VIES direct path remains a future possibility under a separate
ADR that explicitly authorises the host-pinning expansion.

## Decision

This ADR proposes the following concrete architecture.

1. The AEAT NIF-IVA checker adapter lives under
   `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py` and
   implements the `LiveParityOracle` Protocol declared by the live
   parity oracle backend ADR.
2. The adapter's `oracle_id` is the stable identifier
   `aeat-nif-iva-checker`. The id is global; modelo cross-references
   bind to it by name.
3. The adapter's `surface_kind` is `vat_id_check`. The closed enum value
   matches the live parity oracle backend ADR's surface-kind taxonomy.
4. The adapter targets the public AEAT verification page at
   sede.agenciatributaria.gob.es. The page exposes a form-driven VAT-ID
   validity check for other EU member states; AEAT relays the query to
   VIES under the hood and renders the response. Because the page is on
   an AEAT host, the existing remote-state-guard host-pinning policy
   admits the operation without extension.
5. The adapter classifies as environment `production`. The AEAT page
   accepts synthetic NIF inputs and creates no NIF-history state under
   the autonomo's own account; the lookup is anonymous from AEAT's
   perspective and equivalent to a public dictionary query.
6. The adapter's `planned_operations` declares, in execution order:
   one HTTP GET against the AEAT landing page, one
   `browser_action` to fill the synthetic NIF + member-state form
   fields, one `browser_action` per declared NIF to scrape the rendered
   response, and one terminal `browser_action` to discard the browser
   session without saving any state.
7. The adapter's `verify_payload` calls
   `assert_oracle_operations_allowed` at the entry of the method
   against the supplied `RemoteStateGuardPolicy` before any HTTP or
   browser-action code runs. The guard is the only path through which
   the adapter can reach AEAT.
8. The Playwright-driven execution layer is intentionally not
   implemented in this slice. `verify_payload` raises
   `NotImplementedError` after the guard pre-flight succeeds, mirroring
   the `_renta_web_open_oracle.py` precedent. The contract is the spec
   target; the live driver lands in a follow-up that wires the
   browser-action sequence to a headless Chromium session.
9. Adapter registration into the global `LiveParityCatalogue` is gated
   on the live driver arriving. Until then the adapter class exists for
   contract conformance and tests, and the catalogue does not bind any
   modelo cross-reference to the adapter's id. Cross-references that
   want live VAT-identifier verification must wait for the follow-up
   slice.
10. The adapter does not encode any modelo-specific casilla mapping.
    The `expected` mapping is keyed by operator NIF; the adapter must
    not reference Modelo 349 record-design positions, Modelo 303
    casilla numbers, or any other modelo-specific schema.
11. The adapter returns a `ParityResult` with one
    `ParityFieldComparison` per declared NIF when the live driver
    lands. Each field carries the NIF as `name`, the expected validity
    (`"valid"` or `"invalid"`) as `expected`, the AEAT-reported
    validity as `observed`, and verdict `match` when expected and
    observed agree, `mismatch` when they disagree, or
    `unverifiable` when AEAT (proxying VIES) reports member-state
    unavailability.
12. The adapter's offline contract tests run without any HTTP or
    browser-action code. The tests cover Protocol conformance,
    `planned_operations` enumeration, the guard pre-flight refusal of
    a policy whose allowed_hosts does not include the AEAT page host,
    and the catalogue registration round-trip under production
    classification.

## Constraints

The adapter must remain modelo-agnostic. The `expected` mapping is keyed
by operator NIF; the adapter must not encode Modelo 349 record-design
positions, Modelo 303 casilla numbers, or any other modelo-specific
schema.

The adapter must remain authentication-free. The AEAT NIF-IVA
verification page is a public surface; the adapter must not consume
clave-móvil credentials, certificate sessions, or any other authenticated
context. If a future change to AEAT's surface introduces an
authentication step, the adapter must fail loudly rather than silently
authenticate.

The adapter must respect AEAT page rate limits and politeness
conventions. The live driver, when it lands, must throttle requests to
avoid triggering AEAT-side abuse detection. Rate-limit refusals from
AEAT map to `unverifiable` per-field verdicts, not exceptions.

The adapter must not transmit the autonomo's own NIF to the AEAT
NIF-IVA page. The autonomo is a Spanish taxpayer; querying their own
Spanish NIF on a non-Spanish-VAT-ID surface is meaningless and would
log an unnecessary AEAT-side request under their identity.

The host-pinning policy is not modified. This ADR explicitly opts to
operate inside the existing AEAT-host allow-list rather than expand it;
the EU VIES direct path is left out of scope.

## Implementation Direction

Implement the adapter under
`src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`:

- One class `AeatNifIvaCheckerOracle` satisfies the
  `LiveParityOracle` Protocol.
- A module-level constant carries the AEAT verification page URL.
- `planned_operations` returns the GET-landing + form-fill + per-NIF
  scrape + session-discard sequence as a strict tuple of
  `RemoteOperation` records.
- `verify_payload` calls `assert_oracle_operations_allowed` first,
  then raises `NotImplementedError` until the live driver lands.
- The module exposes a `register_default` helper that registers the
  adapter under environment `production` once the live driver is
  ready. The helper is not invoked at import time.

Add `src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py`
with the following coverage:

- The adapter satisfies the `LiveParityOracle` Protocol.
- `planned_operations` enumerates the GET, the form-fill action, one
  scrape per declared NIF, and the discard action; ordering is
  deterministic and respects the input NIF order via sorted
  iteration.
- `planned_operations` rejects empty `expected` mappings with a
  registry validation error.
- `verify_payload` calls the guard before reaching the
  `NotImplementedError`; the guard refusal path is exercised against a
  policy whose allowed_hosts excludes the AEAT page host.
- The catalogue accepts the adapter under environment `production`
  via the `register_default` helper.

The follow-up slice that wires the Playwright-driven browser session
inherits this contract and replaces the `NotImplementedError` with a
real `ParityResult` build. The follow-up arrives in its own commit
with its own targeted tests.

## Rationale

Picking the AEAT-side surface for the first concrete VAT-identifier
adapter respects the project's safety culture around the host-pinning
allow-list. The constant is not a constraint to be worked around; it is
a control surface whose deliberate narrowness is the reason live AEAT
calls remain auditable. Routing through AEAT's own NIF-IVA verification
page achieves the same verdict authority (AEAT delegates to VIES) while
keeping the host-pinning policy untouched.

This adapter establishes the second AEAT-side oracle precedent
alongside the Renta WEB Open oracle. Together they cover two of the
three live-parity surface kinds the calculation truth registry consumes
day-to-day: open simulators that compute outputs from synthetic inputs
(Renta WEB Open), and identifier-validity verifiers (AEAT NIF-IVA).
The third kind, fixed-width file validators, remains gated on the
test-environment classification per the live parity oracle backend ADR.

The deferred Playwright driver follows the precedent already set by
the Renta WEB Open adapter. Shipping the contract in this slice
without the live driver lets dependent modelo cross-references be
authored against the adapter id ahead of the driver arriving, and
gives the Playwright slice a fully-articulated planned-operation
target to drive against.

## Consequences

Modelo 349 gains a documented binding target for operator-NIF
verification that does not require any host-pinning expansion. The
binding is declared in the modelo's cross-reference; the adapter
binding becomes active when the Playwright driver lands.

Modelo 303, 369, and 390 inherit the same adapter when their cross-
references declare a binding to `aeat-nif-iva-checker`. No new code
is required for those modelos beyond the cross-reference declaration.

The remote-state-guard host-pinning constant is unchanged. The
project's safety culture around that constant is preserved; future
ADRs that propose host-list expansion remain explicit and reviewable.

Live tests for the adapter are gated behind the project's live-test
environment variable and live in a separate test class once the
Playwright driver lands. The default test run never contacts AEAT.

The adapter does not eliminate the need for a future EU VIES direct
path. Direct VIES integration may still be useful (lower latency, no
AEAT intermediary) and remains a candidate for a future ADR that
authorises the host-pinning expansion. This ADR does not foreclose
that path; it simply does not require it.

## Explicit Non-Decisions

This ADR does not authorise the EU VIES direct path. A future ADR may
add `ec.europa.eu` to the host-pinning allow-list under a documented
delegation rationale.

This ADR does not implement the Playwright driver. The driver arrives
in a follow-up slice with its own targeted tests and live-test gating.

This ADR does not register the adapter into the production catalogue at
import time. The catalogue binding waits for the driver.

## Open Review Questions

Should the adapter cache AEAT NIF-IVA responses with a short TTL to
avoid redundant lookups inside a single Modelo 349 export? The page
delegates to VIES which is itself a fact-of-the-day surface; an
in-process cache would respect the surface's nature without exceeding
the memory budget.

Should the adapter expose a configurable per-operation timeout so a
slow AEAT response folds into `unverifiable` rather than blocking the
calculation engine? The default would be a small value to fail fast.

Should the modelo registry TOML carry the oracle binding as a typed
field on the cross-reference rather than a free-form string? Typing it
would surface unresolved oracle ids at registry load time rather than
at calculation time.
