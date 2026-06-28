---
tags:
  - '#adr'
  - '#modelo-multiyear-renta'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-05-21-work-verify-deadline-independence-adr]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
  - '[[2026-06-02-modelo-multiyear-renta-151-beckham-research]]'
  - '[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-research]]'
  - '[[2026-06-02-modelo-multiyear-renta-income-research]]'
  - '[[2026-06-04-modelo-multiyear-renta-research]]'
---



# `modelo-multiyear-renta` adr: `multi-year-renta modelo authorization gate` | (**status:** `accepted`)

## Problem Statement

The application supports 30 modelos. Each modelo's calculation backend is currently
trusted by default: presence of an engine or adapter is treated as proof the modelo
works, with no enforced evidence that the backend produces correct, stable behaviour
across more than a single tax year. A backend that happens to compile and pass a
single-period smoke test can carry a year-specific defect — a hard-coded rate, a
boundary that only holds for one campaign, a carry-forward that was never exercised —
straight into operator-facing output.

The owner mandate is non-negotiable and frames this ADR: **every modelo's calculation
backend is NON-FUNCTIONAL until an authorization gate is lifted, and the gate may only
be lifted by a passing end-to-end persona test that spans at least two distinct renta
(annual) periods.** Every one of the 30 modelos enrolls in this gate. None is
out-of-scope, including the structural and informativa modelos that carry no numeric
calculation.

The architectural problem is therefore: how do we represent per-modelo authorization as
a single un-fakeable source of truth, derive a typed per-revision capability from it
without drift, surface partial rollout honestly, and bind authorization to *real*
multi-year evidence rather than to a self-asserted claim — for modelo classes whose
evidence shape differs (calculation vs reconciliation vs data-fidelity vs structural)?

## Considerations

- The gate must be **default-deny**: a modelo is UNAUTHORIZED unless something explicitly
  and verifiably authorizes it. Absence authorizes nothing; an empty manifest authorizes
  zero modelos.
- Authorization is a **claim that must be verified**, not trusted. This is the same
  trust-but-verify shape already codified for fixtures in the
  `fixture-provenance-declared-in-sidecar` rule: a declaration in data, cross-checked
  against physical evidence the declaration cannot fabricate.
- The capability the runtime consults must **not be authored independently** of the
  manifest, or the two will drift. It must be *derived* at the registry boundary.
- Partial rollout is the expected state for the whole campaign. The system must report
  `authorized N/30` honestly and must never present "all modelos functional" while only
  a subset is.
- Architecture boundaries constrain the surface: no new CLI root verb (root stays
  `config` + `app`/`work`), no new module root, closed value sets live as StrEnum in
  `core/`, and registry-backed access flows through `ValidatedRegistryAuthority`.
- A hard CLI refusal on UNAUTHORIZED-but-computable modelos would contradict the
  owner-confirmed pre-calculation use case decided in
  `2026-05-21-work-verify-deadline-independence-adr`: operators legitimately run
  `work calculate` before a deadline is open. The gate must inform, not block, where an
  engine exists.

## Constraints

- The enrollment evidence type varies by modelo class, so a single calculation-only
  recorder cannot cover the full fleet. The recorder abstraction must admit both a
  calculation-driven year capture and a non-calculation explicit two-year-context
  registration, while preserving un-fakeability for both.
- Several modelos cannot express a real cross-year calculation today: 714 (Patrimonio
  wealth-base year-over-year), 151, and 721 declare no calculation surface in the registry
  at all, and 210 (IRNR) declares a calculation link whose engine path is not yet wired
  (see the engine-build sub-decision). These cannot be authorized by a test-only change;
  they require engine-build work before a genuine two-year calculation exists to record.
  This is a blocking dependency the plan must budget, not a gap the gate can paper over.
- The `>=2 distinct renta years` invariant must hold at the pydantic type boundary, not
  only in test assertions, so a malformed evidence record cannot construct.
- Registry cache correctness depends on the manifest being fingerprinted into the
  registry tree fingerprint per `aeat-registry-authority-flow`; a path-only cache that
  serves stale authorization is forbidden.
- This ADR has no prior research document; the design is owner- and gate-architect-locked
  rather than research-derived. The plan should carry any open implementation-grounding
  into a reference document where engine-build steps need source-level grounding.

## Implementation

A four-layer gate spine, each layer derived from the one above it so no layer can drift
from the source of truth.

**(a) Declarative manifest.** A single TOML file
`src/aeat/_data/registry/aeat/authorization.toml` is the sole source of authorization
truth. It is fingerprinted into the registry cache as a first-class registry input.
Default state is UNAUTHORIZED by **absence**: a modelo not listed is not authorized, and
an empty manifest authorizes zero modelos. Each entry declares, at minimum, the modelo
identity and its `renta_years` claim (the set of distinct annual periods the enrolling
evidence must exercise).

**(b) Derived per-revision capability.** A closed `StrEnum` and an authorization record
live in `core/access_gate/_authorization.py` — `core/` owns closed enums; `access_gate`
owns preflight gates. The per-revision capability is **derived at the boundary** by
`ValidatedRegistryAuthority` from layer (a). It is never authored independently per
revision. No new CLI root verb and no new module root are introduced.

**(c) CI meta-test.** `test_modelo_authorization_gate.py` is hard-cut with **no stored
baseline**. It enumerates all 30 modelos from `ValidatedRegistryAuthority`, and prints
`authorized N/30` plus the explicit UNAUTHORIZED id list on every run. Coverage can only
ratchet upward; there is no recorded number to silently regress against.

**(d) Runtime CLI surface.** A modelo that is UNAUTHORIZED but has a working engine still
**computes** on `work calculate`, emitting an ADVISORY banner that names its
unauthorized state — it is informed, not refused, honouring
`2026-05-21-work-verify-deadline-independence-adr`. No-engine stubs keep the existing
hard refusal at `work create` via the established `_guard_stub_modelo` path.

**The un-fakeable enrollment contract.** The manifest is a claim; the enrolling
end-to-end persona test is the verification. The test drives the **real** engine and
adapters for at least two distinct `filing_year` values. A recorder observes the years
actually exercised. The meta-test cross-checks that the recorded year-set equals the
manifest `renta_years` claim AND contains at least two distinct years. A stub records
nothing and goes red; a single-period test records one year and goes red. The
`>=2 distinct renta years` invariant is also enforced at the pydantic type boundary.
`_multi_year.py` already models the multi-year / prior-filing concept and is the natural
home for the recorder.

**Cross-modelo-class enrollment evidence.** No modelo is out-of-scope. The evidence
*type* varies by class, but every class spans at least two distinct renta years and every
class is recorded:

- **CALC-CROSS-RENTA** — engine plus cross-year carry (130, 100, 200, 202, 303, 131, …).
  The recorder captures two `filing_year`s via `calculate_modelo_revision`.
- **RECONCILIATION-CROSS-RENTA** — periodic→annual summary reconciled across two years
  (390, 180, 190, 193).
- **DATA-FIDELITY-CROSS-RENTA** — informativa year-over-year fidelity plus provenance,
  with no numeric oracle (347, 184, 721, 232, 349, 309, 308, 360, 369).
- **THRESHOLD/CONTINUITY-CROSS-RENTA** — structural exemption / obligation logic across
  two years (720 with the +€20k prior-year baseline, 840 with the €1M-per-year exemption,
  036 obligation-set continuity).

Because the data-fidelity, reconciliation, and threshold classes do not necessarily run a
numeric calculation, the recorder MUST support both (i) calculation-based year capture and
(ii) non-calculation explicit two-year-context registration. In the second mode the test
still drives the real adapters for two distinct years and the recorder still observes;
the meta-test still asserts `>=2 distinct` and manifest match. This is what preserves
un-fakeability for the non-calculating modelos.

**Engine-build sub-decision.** Some modelos cannot be authorized by a test-only change
because no genuine cross-year calculation exists yet to record; they require engine-build
steps the plan must budget explicitly. Two distinct shapes exist here, verified against
the registry application-link declarations under
`src/aeat/_data/registry/aeat/modelos/<id>/`:

- **No calculation surface at all** — 714 (Patrimonio wealth base year-over-year), 151,
  and 721 declare zero `surface = "calculation"` application-link in the registry today.
  These need a new engine built from nothing before any two-year calculation can run.
- **Calculation surface declared but engine wiring incomplete** — 210 (IRNR) declares a
  `modelo-210-2025-calculation` link whose `consumer` is the registry snapshot calculator,
  but the link's own authoring comment marks it the Phase 1 minimum declaration with the
  engine path still to be wired. So 210's authorization waits on completing that wiring,
  not on inventing an engine from scratch.

In both shapes the modelo cannot be authorized until a real two-year calculation exists to
record; the plan must budget the engine completion work and not treat these as test-only
enrollment.

**Migration.** All 30 modelos start UNAUTHORIZED. The campaign lifts them one at a time.
Partial rollout is represented honestly by the meta-test's `authorized N/30` line; the
system never reports a silent "all functional".

## Rationale

The four-layer spine exists so that authorization cannot be asserted in one place and
believed in another. Layer (a) is the only writable surface; (b), (c), and (d) are
derivations of it. The recorder cross-check is the load-bearing idea: it converts the
manifest from an honour-system claim into a verified one, exactly as the
`fixture-provenance-declared-in-sidecar` rule converted fixture provenance from an
allowlist into a sidecar declaration validated against the PDF `/Producer`. A claim that
cannot be independently verified is not evidence; the recorder is the independent
verifier, and the type-boundary invariant makes the minimum-two-years contract
unconstructable to violate.

Choosing ADVISORY-not-refusal at `work calculate` is grounded in the owner-confirmed
pre-calculation use case in `2026-05-21-work-verify-deadline-independence-adr`:
operators compute before deadlines open, so a hard block would break a sanctioned
workflow. The advisory keeps the operator informed without removing the capability. The
default-deny-by-absence posture and the `authorized N/30` honesty line follow the
project's standing refusal to silently over-declare, the same instinct behind the
`no-silent-under-declaration` discipline applied to the verify gate.

## Consequences

- **Honest fleet status.** At any moment the meta-test states exactly how many modelos
  are authorized and which are not. There is no surface on which a half-finished rollout
  can read as complete.
- **Un-fakeable enrollment.** A modelo can only become authorized by a test that drove
  real backends across two distinct renta years; stubs and single-period tests stay red.
  This raises the cost of enrollment deliberately — that cost is the point.
- **Engine-build debt is surfaced, not hidden.** The engine-build sub-decision forces the
  plan to budget real engine work — a new engine for 714 / 151 / 721 (zero calculation
  surface in the registry) and completion of the declared-but-unwired 210 calculation
  link. The pitfall is schedule: these modelos cannot be authorized quickly, and the
  `authorized N/30` line will visibly lag for them until the engine work lands.
- **Recorder dual-mode complexity.** Supporting both calculation-based and
  non-calculation year capture is more design surface than a calculation-only recorder
  would be. The alternative — exempting the non-calculating classes — was rejected
  against the owner mandate, so the complexity is accepted as the cost of full enrollment.
- **Boundary discipline preserved.** No new CLI root, no new module root, capability
  derived not authored, manifest fingerprinted into the registry cache. The gate adds a
  data file, a core enum/record, a derivation in the authority, a meta-test, and an
  advisory banner — and nothing that widens the architecture's root surface.

This ADR is the **foundational gate ADR** for the campaign: it owns the authorization
spine, the un-fakeable enrollment contract, and the cross-class enrollment ruling, and
nothing more. It deliberately does NOT absorb the per-mechanism governance decisions that
individual modelos need. Those land as **separate mechanism-specific ADRs that co-back the
same campaign plan**, each carrying its own research and legal grounding — for example the
353←322 monthly grupo aggregation mechanism (both modelos declare a real calculation
surface in the registry), the 720 prior-year asset baseline binding, and the engine-build
modelos covered by the sub-decision above (714 Patrimonio, 151, 721 with no calculation
surface; 210 IRNR with a declared-but-unwired calculation link). Multiple backing ADRs for
one plan are expected and encouraged: the
foundational gate here defines *how authorization is proven*; the mechanism ADRs define
*what each modelo's cross-year behaviour is*. Keeping them separate preserves per-mechanism
legal grounding and keeps this ADR stable as mechanisms are researched and decided
independently.

## Alternatives rejected

- **Manifest-only trust** (authorize by declaration alone, no recorder cross-check).
  Rejected: a declaration nothing verifies is fakeable; a stub could claim authorization.
  The recorder cross-check is the whole point of the contract.
- **Hard CLI refusal on unauthorized modelos.** Rejected: it contradicts the
  owner-confirmed pre-calculation use case in
  `2026-05-21-work-verify-deadline-independence-adr`. An ADVISORY banner informs
  without breaking a sanctioned workflow.
- **Out-of-scope exemption for structural / informativa modelos.** Rejected against the
  owner's non-negotiable "every modelo enrolls". Instead the recorder gains a
  non-calculation two-year-context mode so these classes enroll with real, recorded
  evidence.
- **Per-revision authorization flag authored independently.** Rejected for drift risk: an
  independently authored flag will diverge from the manifest. The capability is derived
  from the manifest at the boundary instead.

## Codification candidates

- **Rule slug:** `modelo-authorization-gate-default-deny`.
  **Rule:** A modelo's calculation backend is non-functional until its authorization is
  derived from the `authorization.toml` manifest and verified by an enrolling end-to-end
  test that a recorder confirms drove real backends across at least two distinct renta
  years; absence authorizes nothing and the per-revision capability is always derived,
  never authored independently.
