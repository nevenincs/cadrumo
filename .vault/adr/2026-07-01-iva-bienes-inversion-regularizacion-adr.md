---
tags:
  - "#adr"
  - "#iva-bienes-inversion-regularizacion"
date: "2026-07-01"
modified: '2026-07-17'
related:
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-21-m390-iva-carry-boxes-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
---

# `iva-bienes-inversion-regularizacion` adr: `Multi-year capital-goods IVA deduction regularizacion (LIVA arts 107-110): profile register + annual compute + bounded first slice` | (**status:** `accepted`)

## Problem Statement

The IVA regularizacion de deducciones por bienes de inversion (LIVA arts. 107-110) has its
legal grounding and its operator-facing casillas in place, but no computation mechanism.
At HEAD (`debf1b2c1`) the four legal entries `ley-37-1992:art-107/108/109/110` are grounded to
bundled consolidated LIVA text and reviewed; the M303 casilla 43 and the dedicated
`iva.regularizacion-inversiones` casilla exist as `input_kind = manual`, both grounded to arts.
107-110; the M390 annual regularizacion field (box 662-adjacent) exists. The operator today must
compute the annual adjustment externally and type in the cuota. Nothing carries the per-capital-
good state across filing years, nothing performs the art-109 comparison, and a taxpayer who owns
in-window capital goods and leaves casilla 43 blank under-declares (or over-declares) with no
surfaced finding. Issue #349 (P2) routes the missing multi-year machinery to research and this
ADR.

## Considerations

- The mechanism splits into regulatory constants (4-year movable / 9-year real-estate windows,
  the over-10-point regularization gate, the /5 and /10 divisors, the art-108 concept
  eligibility) and per-taxpayer facts (which capital goods are owned, their acquisition year,
  cuota soportada deducted, and initial-year definitive prorrata percentage). The two obey
  different authorities: constants belong in the registry, facts do not.
- A near-complete per-good record already exists for the income-tax amortization purpose:
  `AssetRecord` carries acquisition date, IVA decomposition, and a `deductible_iva_ratio`. But
  its class taxonomy is the LIS art. 12 coefficient set, not the LIVA mueble/inmueble window,
  and its population is a superset of the LIVA population. It is a cross-reference target, not
  the authority.
- Two proven cross-year persistence patterns exist in-tree: the profile assets ledger and the
  IVA-compensation history, both encrypted, bucket-local, and declared through the storage
  namespace registry. The register is authoritative primary input, not a rebuildable cache.
- The feed into casilla 43 / M390 has an exact structural precedent: the
  `iva_compensation_annual_partition` registry-declared source that reads a profile store and
  materialises an annual box via an application projection.
- The art-109 compute consumes the current-year DEFINITIVE prorrata percentage. That percentage
  is itself unmodelled and deferred by `2026-06-19-silent-zero-base-aggregation-adr` (the
  provisional-percentage-carry plus Q4-regularisation design of arts. 102-106). A fully-automatic
  casilla-43 feed therefore inherits that block; the annual per-good compute does not, if the two
  percentages are supplied as inputs.
- The art-110 disposal (transmision) case is a separate compute over the same register and is
  cleanly separable from the annual in-use path.

## Considered options

**Decision 1 - where the per-good register lives.**

- **Registry axis (rejected).** Encoding per-taxpayer owned goods in the registry TOML violates
  `aeat-registry-authority-flow` / `aeat-schema-central-config`, which reserve the registry for
  regulatory authority; taxpayer facts are not regulatory values.
- **Ledger-evidence extension (rejected).** Ledger evidence rows are per-transaction, per-filing
  contributions bound to a snapshot fingerprint (`ledger-derived-revisions-bundle-evidence`).
  The register is durable multi-year state independent of any one filing; forcing it into
  evidence rows is the wrong grain and would not survive across filing years cleanly.
- **Extend `AssetRecord` / the assets ledger as the authority (rejected as authority, kept as
  cross-reference).** Tempting because the record already holds acquisition date, IVA, and a
  deductible ratio; rejected because the LIVA window taxonomy, population, and per-year
  percentage series diverge from the income-tax amortization concern, and conflating the two
  couples two independently-evolving lifecycles.
- **New profile-scoped encrypted register (CHOSEN).** A dedicated domain model plus a new
  bucket-local `FINANCIAL` storage namespace, mirroring the assets-ledger and IVA-compensation-
  history patterns, carrying an optional cross-reference to an `AssetRecord` identifier to avoid
  double data-entry. Facts in the register, constants in the registry.

**Decision 2 - the art-109 annual comparison and its feed.**

- **Bounded mirror / per-period volume sum (rejected).** The silent-zero-base ADR already
  proved a per-period prorrata sum ships wrong regulated numbers; the same reasoning bars
  approximating the definitive percentage.
- **Hard mesh binding of casilla 43 now (rejected for the first slice).** Blocked on the
  deferred prorrata-definitiva source; wiring it now would resolve to a wrong or blank value.
- **Pure domain compute + advisory-surfaced proposed value, source kind DEFERRED (CHOSEN for
  first slice).** A pure `regularizacion` function grounded in arts. 107/109, enrolled as a new
  `bienes_inversion_regularizacion` source kind placed in `DEFERRED_SOURCE_KINDS` with a live
  advisory, feeding a proposed casilla-43 value the operator confirms. Promote to a live mesh
  binding once the prorrata-definitiva source lands.

**Decision 3 - the art-110 disposal case.**

- **Model now (rejected for first slice).** A distinct compute; bundling it enlarges the first
  slice without de-risking the core register.
- **Model the disposal fields, defer the compute (CHOSEN).** Carry the disposal event on the
  register record so no schema migration is needed later (`no-legacy-compatibility`), defer the
  single-final-regularizacion compute to a later slice.

**Decision 4 - cross-period carry and first-slice boundary.**

- **New carry machinery (rejected).** Unnecessary: durable profile state already survives across
  years; the carry is a read of the persisted acquisition-year snapshot.
- **Single-good annual compute as the bounded first slice (CHOSEN).** Register model + namespace
  + roundtrip, a CLI declare/list surface, the art-107/109 single-good annual compute with
  external-oracle tests, and a no-silent-under-declaration advisory; defer multi-good mesh
  binding, the disposal compute, and the automatic prorrata feed.

## Constraints

- **Deferred parent feature.** The current-year definitive prorrata percentage (LIVA arts.
  102-106) is unmodelled and explicitly deferred by `2026-06-19-silent-zero-base-aggregation-adr`.
  The automatic casilla-43 feed depends on it and MUST NOT be force-fitted with a per-period
  approximation. The first slice is designed to stand without it (percentages supplied as inputs;
  advisory rather than binding).
- **Legal figures re-confirmed against bundled corpus.** Per
  `legal-grounding-verifies-bundled-authoritative-corpus`, the over-10-percentage-point threshold
  and the /5 and /10 divisors MUST be re-read verbatim from the bundled
  `corpus/normatives/html/ley-37-1992-art-107.html` and `-art-109.html` before any figure is
  compiled into the registry; a bundled figure is a strong default, not a substitute for
  confirming the number. Whether art. 108 carries a specific bienes-de-escaso-valor euro
  threshold is likewise a corpus cross-check at execution.
- **Secure storage only.** The register holds sensitive financial data and MUST persist only
  through the encrypted bucket-scoped secure-object substrate
  (`sensitive-financial-data-secure-storage-only`), never a plaintext side store.
- **Registry authority preserved.** New regulatory constants land in the registry authoring tree
  and ride the loader/compiler (`aeat-registry-authority-flow`); feature code reads the compiled
  snapshot, never inlines the windows or divisors as Python literals
  (`aeat-schema-central-config`).
- **No silent under-declaration.** When in-window goods exist in the register but casilla 43 is
  blank, the calculate path MUST surface at least an advisory Notice through the typed `Notice`
  channel (`no-silent-under-declaration`, `cli-notices-are-the-only-diagnostic-channel`), never
  a silent zero.
- **No dormant resolver.** The new `bienes_inversion_regularizacion` source kind MUST be either
  enrolled in the live mesh or registered in `DEFERRED_SOURCE_KINDS` with a live advisory - never
  a resolver that exists but is never called (`no-dormant-source-resolvers`).
- **Roundtrip discipline.** The register is authoritative primary state; it MUST carry a real
  save/load/equality roundtrip plus an anti-tautology proof (`aeat-roundtrip-discipline`), with
  every defaultable field populated non-default.
- **Spanish stems.** The domain concept is named with its Spanish stem
  (`bienes_inversion` / `regularizacion`) per `aeat-spanish-stem-naming`.
- **No tautological tests.** The art-109 compute is verified against an AEAT worked example or
  BOE-derived figures, never against numbers hand-computed from the same formula
  (`no-tautological-calculation-tests`).

## Implementation

A dedicated Spanish-stemmed domain model (a `BienInversionIvaRecord` aggregate under a
`domain/bienes_inversion` package, sibling to `domain/iva_compensation`) carries, per capital
good: a stable operator identifier, description, acquisition year, cuota soportada deducted,
the initial-year definitive prorrata percentage, an asset kind mapping to the 4-year (mueble)
or 9-year (inmueble) window, an art-108 concept eligibility flag, an optional `AssetRecord`
cross-reference, and an optional disposal event (year plus sujeta-no-exenta / exenta-no-sujeta
regime) carried but not yet computed. The record persists through a new bucket-local
`FINANCIAL` secure-object namespace declared in the storage namespace registry, read and
written through `SecureObjectRepository` exactly as the assets ledger and IVA-compensation
history do.

The regulatory constants - the 4/9-year windows, the over-10-point regularization gate, and the
/5 and /10 divisors - are authored in the registry (grounded in arts. 107 and 109, corpus
cross-checked) and read from the compiled snapshot; no window or divisor is a Python literal in
feature code.

A pure domain function computes, for one in-window good in a given regularization year, the
art-109 annual adjustment: it gates on the absolute difference between the current-year
definitive percentage and the acquisition-year percentage exceeding the grounded point
threshold, then computes (cuota at acquisition percentage minus cuota at current percentage)
divided by the window divisor. The two percentages are inputs, not derived here - keeping the
function independent of the deferred prorrata-definitiva design.

The feed is a new `bienes_inversion_regularizacion` `BindingSourceKind` member. In the first
slice it is registered in `DEFERRED_SOURCE_KINDS`: the calculate path emits a proposed
casilla-43 value and an advisory Notice (with the per-good breakdown on `Notice.context`) when
the register holds in-window goods, and casilla 43 stays operator-confirmable rather than a hard
binding. A CLI surface under the existing roots lets the operator declare and list tracked goods.
Once the prorrata-definitiva source exists, the source kind is promoted to a live mesh binding
that materialises casilla 43 (annual/4T) and the M390 regularizacion field from the register plus
the computed definitive percentages, following the `iva_compensation_annual_partition` precedent.

Deferred to later slices, with the schema shaped to admit them without migration: the art-110
disposal compute, the automatic prorrata-definitiva feed, and the multi-good live mesh binding.

## Rationale

The register-versus-registry split follows directly from the registry-authority rules
(research F3): the windows and divisors are regulatory values with a binding provision, so they
belong in the registry; the list of owned goods and their acquisition-year percentages are
taxpayer facts, so they belong in a profile-scoped encrypted store. Reusing the proven
assets-ledger and IVA-compensation-history persistence patterns (research F1, F2) keeps the
register on the established secure-storage substrate without inventing a new persistence shape,
and declining to overload `AssetRecord` avoids coupling the LIVA regularization lifecycle to the
income-tax amortization lifecycle whose taxonomy and population differ.

Choosing an advisory-backed proposed value over a hard mesh binding for the first slice is
forced by the deferred prorrata-definitiva parent (research F5): the silent-zero-base ADR proved
that approximating the definitive percentage ships wrong regulated numbers, so the automatic feed
must wait for that source, while the per-good annual compute - which only needs the two
percentages as inputs - can ship now behind an advisory. This satisfies no-silent-under-
declaration (the operator is alerted when in-window goods exist) without asserting a figure the
system cannot yet ground end-to-end. Carrying the disposal fields now but deferring their compute
keeps the schema forward-stable under `no-legacy-compatibility` while bounding the first slice to
the core register plus the single-good annual path.

## Consequences

- **Gain.** The capital-goods regularization becomes a tracked, cross-year, evidence-backed
  computation instead of an untracked manual box; a taxpayer with in-window goods is alerted
  rather than silently under- or over-declaring. The register is reusable by both M303 (casilla
  43) and M390 (annual regularizacion field).
- **Gain.** The register data model reuses established persistence and taxonomy patterns, so the
  first slice is a bounded, well-precedented change.
- **Cost accepted.** The first slice does not auto-populate casilla 43; the operator still
  confirms the proposed value. Full automation is gated on the separately-deferred prorrata-
  definitiva design, and this ADR deliberately does not attempt to unblock it.
- **Difficulty.** The art-109 figures (10-point threshold, /5 and /10 divisors) and the art-108
  concept threshold must be corpus-confirmed at execution; a wrong figure would ship a wrong
  regulated adjustment, so the grounding cross-check is a hard gate, not a formality.
- **Pitfall.** A future agent may see the deferred `bienes_inversion_regularizacion` source and
  treat it as a bounded mirror to bind directly - the same force-fit the silent-zero-base ADR
  warns against. The advisory-plus-deferred registration and this ADR record why the binding
  waits for the prorrata-definitiva source.
- **Pathway.** Once the prorrata-definitiva source lands, promoting the source kind to a live
  mesh binding and adding the art-110 disposal compute are incremental follow-ons on a
  schema already shaped to accept them.

## Codification candidates

- **Rule slug:** `capital-goods-register-is-profile-scoped-not-registry`.
  **Rule:** The per-capital-good IVA regularization register (owned goods, acquisition year,
  cuota deducted, initial prorrata percentage) MUST persist in a profile-scoped encrypted
  secure-object namespace, never in the registry authoring tree; only the regulatory constants
  (the 4/9-year windows, the over-10-point gate, the /5 and /10 divisors) live in the registry,
  grounded in LIVA arts. 107/109. Deferred until the mechanism ships and the split holds.

## Status

`proposed`. Closes the design portion of issue #349. Depends on the separately-deferred
prorrata-definitiva source (`2026-06-19-silent-zero-base-aggregation-adr`) for full automation;
the first slice ships independently of it. Sibling annual-IVA surface:
`2026-06-21-m390-iva-carry-boxes-adr`.
