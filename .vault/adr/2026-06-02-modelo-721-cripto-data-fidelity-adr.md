---
tags:
  - '#adr'
  - '#modelo-721-cripto-data-fidelity'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-721-cripto-data-fidelity-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - "[[2026-06-02-modelo-720-prior-year-baseline-adr]]"
---



# `modelo-721-cripto-data-fidelity` adr: `modelo 721 cripto-exterior data-fidelity twin of 720 and legal-registry correction` | (**status:** `accepted`)

## Problem Statement

The multi-year-renta authorization gate requires every one of the 30 modelos to
enroll via an end-to-end test that drives real backends across at least two distinct
renta years. Modelo 721 (declaración informativa sobre monedas virtuales situadas en
el extranjero) exists in the registry only as empty directories under
`modelos/721/revisions/2023-y-siguientes/`; it has no manifest, no casillas, no
bindings, and no calculation engine. The foundational ADR places 721 in the
DATA-FIDELITY-CROSS-RENTA / THRESHOLD-CONTINUITY class and defers its mechanism to a
co-backing ADR. This is that ADR.

There are two coupled problems. First, **how does 721 acquire a real two-year
dependency** so it can enroll, given it computes nothing? Second, and blocking: the
in-repo legal registry a 721 casilla author would trust,
`src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml`, is marked
`review_status = "reviewed"` but was **authored against the wrong BOE document** — it
registers 721 under Orden HFP/887/2023 / `BOE-A-2023-18679`, when Orden HFP/887/2023
is `BOE-A-2023-17430` and approves the *custodian-side* models 172/173, not 721.
Modelo 721 is approved by **Orden HFP/886/2023 = `BOE-A-2023-17429`**. The file also
mis-anchors the statutory obligation (to `ley-11-2021:da-10` rather than
`ley-58-2003:da-18` letra d) and states the wrong first ejercicio (2022 rather than
2023). A registry built from this file would pull its fichero diseño from the wrong
order's layout. A `reviewed`-but-wrong source is more dangerous than an empty one,
because it actively misleads.

## Considerations

- **721 is the structural twin of 720.** Modelo 720 declares zero formulas — a pure
  informativa with a manifest, revision, casillas, a €50.000 threshold parameter, the
  `foreign_asset` row bindings, and (per the A3 ADR) the prior-year baseline plus
  advisory re-declaration mechanism. RD 1065/2007 art. 42-quater gives 721 the same
  two-threshold structure as 720's arts. 42-bis / 42-ter / 54-bis: >€50.000 initial
  obligation, re-declare only if the 31-December aggregate rose >€20.000 over the
  last-declared baseline. The A3 / 720 mechanism therefore transfers to 721 verbatim,
  with the asset-class axis replaced by a per-custodian axis.
- **The cross-year hook is the verified A3 shape.** `_PreviousModeloSelector` supports
  `filing_year_delta = -1` and the singular `source_output` + `op = "copy"` copy
  shape, and forbids any `grouping` key. 721's per-custodian baseline is authored the
  same way 720's three fixed per-category bindings replace a dynamic grouping kind.
- **The re-declaration trigger inherits A3's open design point.** No existing
  verification predicate operator expresses a cross-year-baseline delta; the closed
  operator set is single-filing only. The advisory must be ADVISORY (never blocking)
  per `no-silent-under-declaration`, and the new operator (or derived-casilla
  formulation) must register against `KNOWN_VERIFICATION_PREDICATE_OPERATORS` to
  preserve the silent-pass guard.
- **Scope is narrower than the prior research claimed.** Only crypto held abroad
  through a **third-party custodian** (foreign exchanges, custodial-wallet providers)
  is 721-declarable. Self-custody / exclusive-key cold wallets are out of scope. The
  per-record key is **custodian + token**, not the prior research's self-custody
  "Section C".
- **The legal defect is the load-bearing prerequisite.** Verified against the BOE:
  Modelo 721 = Orden HFP/886/2023 = `BOE-A-2023-17429`; Orden HFP/887/2023 =
  `BOE-A-2023-17430` = models 172/173. The obligation Ley 11/2021 created was letra d
  of the existing Ley 58/2003 DA-18 (the same DA-18 that grounds 720). First ejercicio
  is 2023 (filed Jan–Mar 2024), matching the existing scaffold's `2023-y-siguientes`
  anchor.

## Constraints

- **The legal-corpus correction MUST land before any casilla authoring.** This is the
  hard sequencing constraint. If the registry is populated while
  `monedas-virtuales.toml` still points at `BOE-A-2023-18679` / Orden HFP/887/2023,
  the fichero offsets will be authored against models 172/173's layout. The ADR
  mandates correcting the file against `BOE-A-2023-17429` (Orden HFP/886/2023),
  re-anchoring the obligation to `ley-58-2003:da-18` letra d, fixing the first-ejercicio
  notes 2022→2023, and re-registering the fichero-layout source (`aeat-dr-721`) and the
  `boe-modelo-721-2023-form` source against the correct order — as W06 step one.
- **No calculation engine.** 721 is a 720-twin: zero formulas. Any temptation to model
  a crypto valuation calculation is out of scope; the declarable value is the operator-
  supplied 31-December aggregate, not a computed figure.
- **No schema change.** The mechanism reuses the verified A3 binding and predicate
  shapes, which need no schema extension. The per-custodian fan-out is authored as
  fixed rows / bindings on the filing, not a new `RowSetGroupingKind` member.
- **The advisory MUST stay ADVISORY.** Growth ≤ €20.000 legitimately need not be
  re-declared. A BLOCKING_RULE would refuse legal filings.
- **Parent-feature stability.** This mechanism consumes (i) the previous-filing binding
  subsystem (mature), (ii) the verification-predicate subsystem (mature), (iii) the A3
  / 720 mechanism it twins (decided in the sibling ADR), and (iv) the foundational
  gate's non-calculation two-year-context recorder mode. 721 is a *consumer* of all
  four; it builds none of them. The only new surfaces are registry data, two registry
  threshold parameters, and (shared with A3) at most one advisory operator.

## Implementation

A legal-correction-first, registry-data-only mechanism in six parts; no calculation
engine and no schema change.

**(1) Correct the legal corpus (W06 step one).** In
`src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml`: replace the
`orden-hfp-887-2023:art-1/2/3` entries with `orden-hfp-886-2023:art-1/2/3`, all
`document_id = "BOE-A-2023-17429"`, permalinks and `corpus_ref`s re-pointed at
`BOE-A-2023-17429`; re-anchor the statutory obligation to `ley-58-2003:da-18`
(letra d) and retire/correct the `ley-11-2021:da-10` slug; fix the first-ejercicio
notes from 2022 to 2023; re-point the `boe-modelo-721-2023-form` / `-layout` sources
and register the `aeat-dr-721` fichero-layout source against the correct order. The
edit is the coder's; this ADR mandates it as the gating first step. The stale vault
research `2026-05-27-m721-informativa-criptomonedas-research` (which repeats all three
errors and overstates scope) is superseded by this ADR's research.

**(2) Build the 721 registry from scratch mirroring 720.** Author `manifest.toml`
(`id = "721"`, `tax_domain = "informative"`, `cadence = "annual"`), `revision.toml`
(anchor `2023-y-siguientes`, `period_selector = { year_from = 2023, periods = ["0A"] }`),
and the casilla set from the corrected HFP/886/2023 fichero diseño (declarante
section + per-custodian/per-token detail records). All `legal_refs`:
`["ley-58-2003:da-18", "rd-1065-2007:art-42-quater", "orden-hfp-886-2023:art-1",
"orden-hfp-886-2023:art-2", "orden-hfp-886-2023:art-3", "ley-58-2003:art-93"]`.

**(3) Two threshold parameters.** Mirror 720's threshold-as-registry-parameter pattern:
`modelo-721-asset-declaration-threshold-eur` (value 50000.00) and
`modelo-721-redeclaration-increment-threshold-eur` (value 20000.00), each grounded on
`rd-1065-2007:art-42-quater`. Keeping both as registry parameters gives the
threshold-logic oracle single authoritative values to assert against (satisfying
`no-tautological-calculation-tests`).

**(4) Prior-year per-custodian baseline binding.** A `previous_filing` binding with
`source_modelo = "721"`, `filing_year_delta = -1`, `period = "0A"`, a singular
`source_output` naming the per-custodian prior-year aggregate, and
`aggregation = { op = "copy" }` — the verified A3 copy shape. The per-custodian fan-out
follows 720's fixed-binding pattern, not a dynamic grouping.

**(5) ADVISORY re-declaration predicate.** Per custodian, surface an ADVISORY finding
when the prior-year baseline resolved a non-zero value, the current-year custodian
aggregate exceeds the baseline by more than the €20.000 parameter, and the custodian
is absent from the current declaration. Holds trivially when the antecedent baseline is
≤ 0 (first-time declaration never trips it). Grounded with `legal_refs`. The evaluator
choice (new operator vs derived casilla) is inherited from the A3 ADR and resolved
once for both modelos; whichever path is chosen must register against
`KNOWN_VERIFICATION_PREDICATE_OPERATORS`.

**(6) Two-year enrollment test.** A real-adapter test (no mocks) cloning
`test_modelo_130_carry_forward_continuity.py`: Year N declares a custodian at €60.000
(> €50.000); Year N+1 firing leg €85.000 (+€25.000 > €20.000 → advisory fires); Year
N+1 control leg a custodian growing ≤ €20.000 (advisory does not fire). Asserts the
per-custodian baseline auto-resolves N→N+1 and the recorder observes two distinct
renta years.

## Rationale

Twinning 720 is chosen because 721's statutory structure (art. 42-quater) is identical
to 720's (arts. 42-bis/ter/54-bis), and the A3 mechanism was already verified
constructable against the live schema. Reusing it verbatim avoids re-litigating the
binding and predicate shapes and keeps the two informativas governed by one mechanism,
reducing drift. The per-custodian axis is the only substantive difference and needs no
new schema because, like 720's closed asset-class set, the custodians on a filing are
authored as fixed rows rather than a dynamic grouping kind.

Correcting the legal corpus first is non-negotiable because the registry's fichero
offsets are derived from the diseño de registro in the order's BOE document; building
against `BOE-A-2023-18679` / Orden HFP/887/2023 would encode the layout of models
172/173. The `reviewed`-but-wrong stamp is the exact trust-but-verify failure the
project's source-hygiene and fixture-provenance disciplines guard against, here at the
legal layer: the declaration ("this is 721's order") was trusted without the
cross-check ("does this BOE document actually approve Modelo 721?"). The ADR converts
that into a mandated correction with an external (BOE) cross-check.

The ADVISORY-not-blocking posture and the registry-parameter thresholds follow the
A3 ADR and the `no-silent-under-declaration` / `no-tautological-calculation-tests`
disciplines: the under-declaration is made non-silent without refusing legal
zero-growth filings, and the oracle asserts against statutory constants rather than a
re-derived formula.

## Consequences

- **721 enrolls with a real, statute-grounded two-year oracle.** The strongest oracle
  class available to an informativa, matching 720.
- **A reviewed-but-wrong legal source is corrected before it propagates.** Catching it
  at the ADR stage prevents a registry built against models 172/173's layout — a defect
  that would have been expensive to unwind after casilla authoring.
- **One mechanism governs two modelos.** 720 and 721 share the prior-year-baseline +
  advisory shape, so a future change to the mechanism touches both consistently.
- **Dependency on the A3 evaluator decision and the foundational recorder mode.** 721
  cannot fully land until A3's predicate-operator choice is resolved and the
  foundational gate's non-calculation recorder mode exists. 721 builds neither.
- **Scope-narrowing risk.** Excluding self-custody is correct per art. 42-quater, but
  the casilla author must not import the prior research's "Section C" self-custody
  fields. The corrected fichero (from HFP/886/2023) is the authority; the test must
  assert the declarable population is custodian-mediated only.
- **The correction touches a shared legal file.** `monedas-virtuales.toml` may also be
  read by any future 172/173 work; the W06 edit must add the correct 721 order without
  disturbing unrelated entries, and should flag the file to the legal-corpus
  source-registry owner so the `reviewed` stamp is re-applied after correction.

This is a mechanism ADR co-backing the multi-year-renta campaign plan, twinning the A3
/ 720 mechanism. It owns 721's cross-year behaviour and the legal-corpus correction it
depends on, and nothing more.

## Codification candidates

- **Rule slug:** `reviewed-legal-source-must-cross-check-the-document-identity`.
  **Rule:** A legal-corpus entry may carry `review_status = "reviewed"` only if the
  reviewer cross-checked that the cited BOE `document_id` and order number actually
  approve the modelo/obligation the entry claims — a `reviewed` stamp without that
  document-identity cross-check is the failure mode that mis-registered Modelo 721
  under models 172/173's order.

  This candidate generalises the trust-but-verify discipline already codified for
  fixtures (`fixture-provenance-declared-in-sidecar`) to the legal-source layer. Promote
  it if a second reviewed-but-wrong legal entry is found; otherwise it stands as
  documented rationale here and in the superseding research.


