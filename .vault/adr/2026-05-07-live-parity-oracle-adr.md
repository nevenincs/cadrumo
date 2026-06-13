---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-06-oracle-surface-compatibility-adr]]"
  - "[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]"
  - "[[2026-05-07-live-parity-oracle-plan]]"
  - "[[2026-05-06-cross-reference-oracle-binding-adr]]"
  - "[[2026-05-07-aeat-vies-auth-tier-research]]"
---



# `authenticated-synthetic-surface-taxonomy` adr: `Add an authenticated_simulator surface category for auth-gated callable verification surfaces` | (**status:** `accepted`)

## Review State

This ADR is accepted as the operational record of an empirical
finding from 2026-05-07: the AEAT GROI Spanish-ROI consult servlet
requires cl@ve-movil authentication, accepts arbitrary synthetic
NIFs, and submits via POST. None of those properties fit any of the
existing four cross-reference surface categories
(`open_simulator`, `integration_test_service`,
`public_read_surface`, `authenticated_read_surface`,
`static_official_documentation`).

The AEAT-VIES surface-split ADR documented the empirical finding;
the GROI sede driver and registry oracle ship in HEAD and pass live
end-to-end against AEAT. The cross-reference schema validator
prevents declaring a registry-data cross-reference for GROI because
the validator's surface-tier rules are too strict. This ADR closes
that gap.

## Problem Statement

The cross-reference schema validator at
`_schema.LiveCrossReferenceDecision._validate_cross_reference`
enforces the following surface-shape rules:

- `open_simulator` requires `executable_parity_evidence`,
  forbids `requires_authentication=True`, allows synthetic data,
  allows POST.
- `integration_test_service` requires `executable_parity_evidence`,
  no other constraints checked.
- `public_read_surface` requires `observation_evidence` (NOT
  `executable_parity_evidence`), forbids
  `requires_authentication=True`, forbids synthetic data, allows
  only `GET / HEAD / OPTIONS`.
- `authenticated_read_surface` requires `observation_evidence`,
  requires `requires_authentication=True`,
  requires `requires_aeat_authorization=True`, forbids synthetic
  data, allows only `GET / HEAD / OPTIONS`.
- `static_official_documentation` forbids
  `executable_parity_evidence`, forbids synthetic data.

The empirical GROI semantics:

- Requires authentication (cl@ve-movil session loaded; without it
  AEAT redirects to `/Sede/errores/erro4033.html`).
- Accepts arbitrary NIFs as input — the form's NIF input validates
  format only, then queries the ROI registry.
- The form submits via HTTP POST to
  `ConsultaOperadorSedeGroiServlet`. The POST is a CONSULT (a SELECT
  against the ROI registry); per AEAT service contract no AEAT-side
  state is modified.
- The verdict authority is callable / executable parity: the
  registry oracle compares observed verdicts against the caller's
  declared expected verdicts and returns a `ParityResult`.

No existing surface category permits all four properties
simultaneously: `authenticated_read_surface` requires
`observation_evidence` and forbids POST + synthetic data;
`open_simulator` forbids authentication; the others are obviously
wrong.

## Decision

Add a new surface category `authenticated_simulator` to
`LiveCrossReferenceDecision.surface` with the following validator
rules:

1. `evidence_tier` MUST be `executable_parity_evidence` (it is a
   callable verification surface).
2. `requires_authentication` MUST be `True` (this is the defining
   property of the new category).
3. `requires_aeat_authorization` MAY be `True` or `False` (auth
   tier varies; cl@ve-movil is sufficient for some surfaces, others
   may require certificate-tier authorization on top — empirical
   per-surface).
4. `synthetic_data_allowed` MAY be `True` or `False` (most
   simulators accept synthetic data; some may not).
5. `allowed_methods` MAY include `POST` in addition to
   `GET / HEAD / OPTIONS` (the form-submit POST is the AEAT-prescribed
   query mechanism for some surfaces).
6. `allowed_hosts` MUST be non-empty (same as the other live
   surfaces).
7. The remote-state guard's existing constraints apply unchanged:
   the canonical `AEAT_WRITE_FORBIDDEN_ACTIONS` set is required in
   `forbidden_actions`; the global forbidden-token set blocks any
   action label carrying a write verb; the host-pinning suffix
   `agenciatributaria.gob.es / aeat.es` remains the outer fence.

Extend `_live_parity._COMPATIBLE_SURFACE_PAIRS` with the pair
`("authenticated_simulator", "vat_id_check")`. This is the pair
GROI's oracle (oracle id `aeat-groi-spanish-roi-checker`,
surface_kind `vat_id_check`) needs to bind to a modelo 349
cross-reference under the new category.

The existing IXVI oracle (oracle id `aeat-nif-iva-checker`,
surface_kind `vat_id_check`) will likely also bind under
`authenticated_simulator` once the auth-tier probe documented in
the auth-tier research note resolves the IXVI-specific
authentication contract. That binding is out of scope for this ADR
but inherits the new category cleanly.

## Constraints

The new category MUST NOT relax the read-only mandate. Specifically:

- Allowing `POST` in `allowed_methods` does NOT allow the guard's
  `kind="http", method="POST"` operation past
  `_evaluate_http`'s read-only-method check. The POST is
  represented in the driver's `planned_operations` as a
  `kind="browser_action"` whose action label passes the forbidden-
  action / forbidden-token check. The HTTP-method check stays
  strict; only the cross-reference's `allowed_methods` declaration
  changes.
- The driver-level form-action attribute guard (the
  `_assert_form_action_is_consult_endpoint` helper added to the
  GROI driver) becomes mandatory for any
  `authenticated_simulator` cross-reference whose oracle drives a
  form submission. The cross-reference's `oracle_id` must point at
  an oracle whose driver implements the action-attribute pre-check;
  oracle authors confirm this in their adapter ADR.
- `synthetic_data_allowed=True` is permitted under the new
  category but ONLY because the AEAT surface itself accepts
  arbitrary inputs without state mutation. A surface that creates
  any AEAT-side draft / staged record under the calling NIF MUST
  NOT use `synthetic_data_allowed=True` regardless of category;
  the live-parity-oracle ADR's D13a forbidden surface principle
  (TGVI online and similar) holds across all categories.

The schema change MUST be backwards-compatible. Every existing
cross-reference shape continues to validate after the change
(committed registry data passes `aeat app registry verify`
unchanged).

## Implementation Direction

Schema change in `_schema.py`:

- Extend `LiveCrossReferenceDecision.surface`'s `Literal[...]` to
  include `"authenticated_simulator"`.
- Extend `_validate_cross_reference` with a branch for
  `authenticated_simulator`:
  - require `evidence_tier == "executable_parity_evidence"`;
  - require `requires_authentication == True`;
  - require `allowed_hosts` non-empty;
  - require methods to be a subset of `{GET, HEAD, OPTIONS, POST}`;
  - permit `synthetic_data_allowed` to be `True` or `False`.

Compatibility table change in `_live_parity.py`:

- Extend `_COMPATIBLE_SURFACE_PAIRS` with
  `("authenticated_simulator", "vat_id_check")`.
- Update the surface-compatibility ADR's allow-list table in the
  same commit (the table is the contract).

Test surface in `test_registry_schema.py`:

- Add a positive test: a synthetic `LiveCrossReferenceDecision`
  with `surface="authenticated_simulator"`,
  `evidence_tier="executable_parity_evidence"`,
  `requires_authentication=True`, `synthetic_data_allowed=True`,
  POST in allowed_methods validates clean.
- Add negative tests: each rule (executable parity required, auth
  required, methods restricted to the 4-token set) raises with a
  diagnostic message.
- Confirm every existing cross-reference in the committed registry
  still validates.

Documentation:

- Update the surface-compatibility ADR's "Decision" allow-list to
  include the new pair.
- Update the cross-reference-oracle-binding ADR's "Compatibility
  table" reference to mention the new category.
- The plan's Phase 1 verification block ticks complete only after
  all of the above land and `aeat app registry verify` reports
  exit 0 against the unchanged registry.

## Rationale

The four existing categories were designed against the assumption
that a CALLABLE verification surface (one that returns a verdict
rather than just being read or documented) is necessarily public
and unauthenticated. Live probing showed that assumption is
contradicted by AEAT's actual deployment: callable verification
surfaces under cl@ve-movil exist (GROI) and are valuable for
production filing flows.

Choosing (a) a new `authenticated_simulator` category instead of
(b) relaxing `authenticated_read_surface` to permit POST + synthetic
data is the correct choice because (b) would conflate two genuinely
distinct semantics: "I read a single declaration from AEAT under my
own NIF" (existing) vs "I call a verification service with synthetic
inputs and read AEAT's verdict" (new). The two are different
contracts: the read-surface returns the caller's own filing
history, while the simulator-surface returns a verdict against
arbitrary inputs. Treating them as one category would obscure
real-world reasoning (e.g., a future agent looking at a cross-
reference can't tell whether the surface returns a personal record
or a public lookup).

## Consequences

The cross-reference schema gains one new surface category with
explicit validator rules.

The compatibility table gains one new pair. The IXVI oracle and
the GROI oracle both bind cleanly under the new category once the
modelo 349 (and eventual modelo 349 IXVI) cross-references land in
registry data.

Plan Phase 1 (this ADR) unblocks plan Phase 2 (modelo 349 GROI
binding). The remaining four plan phases (CI gating, drift
detector, oracle-binding how-to, IXVI cert probe) do not depend on
this ADR.

The read-only mandate's four enforcement layers are unchanged: the
new category does not weaken any of them. `POST` in
`allowed_methods` is a declaration of the AEAT-prescribed query
mechanism, not a permission for the guard's HTTP-method check
(which stays strict).

## Explicit Non-Decisions

This ADR does not bind any oracle to any modelo cross-reference.
That happens in plan Phase 2 (modelo 349 GROI binding) and in
follow-up modelo bindings.

This ADR does not deprecate `open_simulator`. The Renta WEB Open
simulator (modelo 100) is genuinely public and does not require
authentication; it stays under `open_simulator`.

This ADR does not extend the surface-kind taxonomy. The oracle's
`surface_kind` enum (`vat_id_check`, `pre_filing_validator`,
`file_validator`, `open_simulator`, `integration_test_service`)
remains as it is. Only the cross-reference's `surface` enum gains
a value.

## Open Review Questions

Should `requires_aeat_authorization` be REQUIRED for
`authenticated_simulator` cross-references whose oracle has
surface_kind in `{file_validator, pre_filing_validator}`? Those
surfaces typically demand authorization beyond cl@ve-movil
(certificate-tier or ROI-registered caller). Defer until the IXVI
cert probe (plan Phase 6) returns empirical data.

Should the new category be subdivided further into
`authenticated_synthetic_simulator` (accepts arbitrary inputs) and
`authenticated_personal_simulator` (only the caller's own data)?
Defer until a second authenticated-simulator surface lands; one
data point doesn't justify the subdivision.
