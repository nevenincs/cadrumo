---
tags:
  - "#adr"
  - "#iva-complexity-hardening-scope"
date: '2026-07-01'
related:
  - "[[2026-07-01-iva-complexity-hardening-scope-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
superseded_by: '2026-07-07-iva-prorrata-complexity-adr'
modified: '2026-07-17'
---
# `iva-complexity-hardening-scope` adr: `Prorrata definitiva annual regularizacion (LIVA arts 105-106): provisional-carry + Q4 regularisation feeding M303 casilla 44 and M390` | (**status:** `superseded`)

## Problem Statement

The IVA prorrata substrate (`domain/iva/_prorrata.py`) computes general (art-102),
especial (art-103), and sectoral (art-9.1.c) percentages, and models the
PROVISIONAL/DEFINITIVA lifecycle (`ProrrataKind`). But nothing wires that substrate
into the calculate mesh as an aggregation source: there is no prorrata
`BindingSourceKind`, and M303 casilla 44 (Regularizacion prorrata por porcentaje
definitivo - Cuota) is `input_kind = "manual"`. A taxpayer with exempt-without-right
operations must compute the annual prorrata regularizacion externally and type the
cuota into casilla 44 and the M390 annual field, with no surfaced finding when it is
left blank. This is the arts-105-106 regularizacion-anual portion of umbrella child
#347; its general/especial/deductibility siblings (#346, and the compute half of
#347) are already modelled. Two prior ADRs
(`2026-06-19-silent-zero-base-aggregation-adr`,
`2026-07-01-iva-bienes-inversion-regularizacion-adr`) named this exact gap as the
deferred "prorrata-definitiva source"; the bienes-inversion first slice (#349) is
BLOCKED on it for its automatic casilla-43 feed.

## Considerations

- LIVA art-105 applies a PROVISIONAL deduction percentage across the year (normally
  the prior year definitive), and art-106 REGULARISES it at year-end against the
  current year actual annual volumes. The regularizacion cuota is the delta between
  input IVA deducted at the provisional percentage and at the definitive percentage,
  surfaced on M303 casilla 44 (final quarter/annual) and the M390 annual field.
- This is a cross-period structure: the provisional percentage is an input CARRIED
  from the prior year definitive, and the definitive percentage is computed from the
  full-year volumes. The closest in-tree precedent is the IVA-compensation wallet
  (cross-period carry with a profile-scoped store) and the
  `iva_compensation_annual_partition` registry-declared annual source.
- The `silent-zero-base-aggregation` ADR proved a per-period `base_amount_sum` binding
  ships a WRONG deducible percentage for any trader with exempt-without-right
  operations, because a single quarter volume computes neither the provisional nor the
  annual-regularised percentage. A faithful mechanism must carry the provisional
  percentage and regularise annually - it is genuine design, not a bounded mirror.
- The prorrata percentage itself needs the year annual volumes split into
  operaciones-con-derecho vs sin-derecho. Those volumes are exactly what the M303
  base bindings and the ledger IVA aggregation already project per period; the annual
  definitive percentage is their full-year rollup with the art-104 exclusions applied.
- Two facts obey different authorities: the regulatory constants (the +10% especial
  gate, the art-104 exclusion set, rounding) are registry values; the accepted
  provisional percentage and the prior-year definitive are per-taxpayer facts that
  belong in a profile-scoped store, mirroring the bienes-inversion register decision.

## Considered options

**Decision 1 - how the definitive percentage is produced.**

- Per-period volume binding (REJECTED). A `ledger_iva_aggregation base_amount_sum`
  binding on the current quarter volumes computes a wrong percentage for any
  exempt-without-right trader; the silent-zero ADR ratified this as a correctness
  defect, not a bounded mirror.
- Annual con-derecho/sin-derecho volume rollup feeding `compute_prorrata_general`
  (CHOSEN). Reuse the existing prorrata substrate: aggregate the full-year operation
  volumes (already projected per period), apply the art-104 exclusions, and call the
  substrate to produce the DEFINITIVA percentage. The substrate already exists and is
  the authority; the new work is the annual volume rollup, not the math.

**Decision 2 - the provisional percentage carry.**

- Recompute provisional from the current year (REJECTED). Art-105 requires the
  PROVISIONAL percentage to be the prior year definitive (or an AEAT-approved figure),
  not a current-year estimate.
- Profile-scoped carry of the prior-year definitive percentage (CHOSEN). Persist each
  year definitive percentage in a profile-scoped encrypted store (the
  bienes-inversion / IVA-wallet pattern), and read the prior year value as this year
  provisional. The store is authoritative primary input, roundtrip-tested.

**Decision 3 - the casilla-44 / M390 feed.**

- Hard mesh binding now (REJECTED for the first slice). Blocked on nothing further than
  the annual rollup, but the safer first slice keeps casilla 44 operator-confirmable.
- New `prorrata_regularizacion` `BindingSourceKind`, DEFERRED-registered with a live
  advisory (CHOSEN for first slice). The calculate path emits a proposed casilla-44
  value plus an advisory Notice with the per-percentage breakdown when the register
  holds a prior-year definitive and the year has sin-derecho volumes; promote to a
  live mesh binding once proven. This mirrors the bienes-inversion first-slice shape
  exactly and satisfies `no-dormant-source-resolvers`.

**Decision 4 - scope of the first slice.**

- Bundle sectoral-separation regularizacion and the art-104-bis financial-operation
  exclusions now (REJECTED). Enlarges the slice without de-risking the core carry.
- Whole-entity provisional-carry + annual-definitive regularizacion as the bounded
  first slice (CHOSEN); defer per-sector regularizacion and the art-110-adjacent
  disposal interactions, with the store shaped to admit them without migration
  (`no-legacy-compatibility`).

## Constraints

- Parent-feature stability: the general/especial/sectoral prorrata substrate
  (`2026-05-12` ADR) is accepted and stable; this ADR consumes it and does NOT
  re-open it. The annual VOLUME projection (con-derecho vs sin-derecho) is the new
  dependency and must be grounded in the same ledger IVA aggregation the M303 bases
  use, applying the art-104 exclusions.
- No wrong regulated numbers: the definitive percentage MUST come from the substrate
  over annual volumes, never a per-period approximation (`aeat-safety-legal-gates`,
  the silent-zero ADR codification rule).
- Registry authority: the +10% especial gate, art-104 exclusion set, and rounding
  live in the registry authoring tree, corpus-cross-checked
  (`legal-grounding-verifies-bundled-authoritative-corpus`,
  `registry-calculation-legal-grounding`); feature code reads the compiled snapshot.
- Secure storage only: the per-year definitive-percentage carry holds taxpayer facts
  and persists only through the encrypted bucket-scoped secure-object substrate
  (`sensitive-financial-data-secure-storage-only`).
- No silent under-declaration: when a prior-year definitive percentage exists and the
  year carries sin-derecho volumes but casilla 44 is blank, the calculate path MUST
  surface at least an advisory Notice (`no-silent-under-declaration`,
  `cli-notices-are-the-only-diagnostic-channel`).
- No dormant resolver: the `prorrata_regularizacion` source kind is either enrolled in
  the live mesh or registered in `DEFERRED_SOURCE_KINDS` with a live advisory
  (`no-dormant-source-resolvers`).
- Roundtrip + non-tautological tests: the carry store carries a real
  save/load/equality roundtrip plus anti-tautology proof
  (`aeat-roundtrip-discipline`); the regularizacion cuota is verified against an AEAT
  worked example or Manual practico IVA figures, never numbers hand-computed from the
  same formula (`no-tautological-calculation-tests`).
- Spanish stems: the domain concept is `prorrata` / `regularizacion`
  (`aeat-spanish-stem-naming`).

## Implementation

The first slice adds three layers on top of the existing prorrata substrate. First, an
annual prorrata VOLUME rollup in the aggregation layer: a full-ejercicio window that
sums the year operaciones-con-derecho and operaciones-sin-derecho from the same ledger
IVA aggregation the M303 bases consume, applies the art-104 exclusions (subvenciones no
vinculadas, autoconsumos, sale of bienes de inversion), and feeds `ProrrataInputs` to
`compute_prorrata_general` to obtain the DEFINITIVA percentage. Second, a
profile-scoped encrypted carry store (the IVA-wallet / bienes-inversion-register
pattern) holding, per ejercicio, the definitive percentage and regime; the prior-year
record is read as the current year PROVISIONAL percentage per art-105. Third, a pure
domain function computes the art-106 regularizacion cuota as the delta between input
IVA deducted at the provisional percentage and at the definitive percentage over the
year deductible input IVA.

The feed is a new `prorrata_regularizacion` `BindingSourceKind` member. In the first
slice it is registered in `DEFERRED_SOURCE_KINDS`: the calculate path emits a proposed
casilla-44 value and an advisory Notice (with the provisional/definitive percentages
and the delta on `Notice.context`) when the carry store holds a prior-year definitive
and the year has sin-derecho volumes; casilla 44 stays operator-confirmable. The same
projection feeds the M390 annual regularizacion field. Once the mechanism is proven end
to end, the source kind is promoted to a live mesh binding following the
`iva_compensation_annual_partition` precedent, unblocking the bienes-inversion #349
automatic casilla-43 feed that consumes the same definitive percentage.

The regulatory constants (+10% especial gate, art-104 exclusion set, rounding) land in
the registry authoring tree grounded in LIVA arts 104/105/106, corpus-cross-checked,
and are read from the compiled snapshot. Deferred to later slices with the schema
shaped to admit them without migration: per-sector regularizacion, the art-104-bis
non-recurring-operation exclusions, and the automatic (non-advisory) casilla-44 mesh
binding.

## Rationale

The compute half of prorrata is done; the missing half is the cross-period carry and
annual regularizacion, which the silent-zero-base ADR proved cannot be approximated by
a per-period volume sum without shipping wrong regulated numbers. Reusing the prorrata
substrate for the math, the ledger IVA aggregation for the volumes, and the
IVA-wallet / bienes-inversion pattern for the carry keeps every layer on an established,
grounded surface rather than inventing a new one. The advisory-plus-DEFERRED first
slice mirrors the bienes-inversion decision: it satisfies no-silent-under-declaration
today without asserting a figure the mesh cannot yet ground automatically, and it opens
the exact source (`prorrata_regularizacion` / the definitive percentage) that #349 is
blocked on. The register-versus-registry split follows the registry-authority rules
(facts in the profile store, constants in the registry).

## Consequences

- Gain: the annual prorrata regularizacion becomes a tracked, evidence-backed,
  cross-year computation feeding both M303 casilla 44 and the M390 annual field; a
  trader with exempt-without-right operations is alerted rather than silently
  under- or over-declaring.
- Gain: unblocks the bienes-inversion #349 automatic casilla-43 feed, which depends on
  the same definitive-percentage source.
- Cost accepted: the first slice does not auto-populate casilla 44; the operator
  confirms the proposed value until the source kind is promoted to a live mesh binding.
- Difficulty: the annual volume rollup must apply the art-104 exclusions correctly and
  the +10% especial gate and rounding must be corpus-confirmed; a wrong figure ships a
  wrong regulated adjustment, so the grounding cross-check is a hard gate.
- Pitfall: a future agent may treat the DEFERRED `prorrata_regularizacion` source as a
  bounded per-period mirror to bind directly - the same force-fit the silent-zero ADR
  warns against. The advisory-plus-deferred registration and this ADR record why the
  binding waits for the proven annual mechanism.
- Pathway: promoting the source kind to a live mesh binding and adding per-sector
  regularizacion are incremental follow-ons on a schema shaped to accept them.

## Status

`proposed`. Scopes the arts-105-106 regularizacion-anual portion of umbrella child
#347. Recommends #346 and #348 CLOSE as largely-done (see the companion research
verdict table). Depends on the accepted general/especial prorrata substrate
(`2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`); its
definitive-percentage source unblocks `2026-07-01-iva-bienes-inversion-regularizacion-adr`.

## Codification candidates

- Rule slug: `prorrata-definitiva-is-annual-carry-not-per-period-sum`. Rule: the M303
  casilla-44 / M390 prorrata regularizacion MUST be computed from the prior-year
  definitive percentage carried as the provisional and the current-year annual
  definitive percentage over full-year volumes, never from a per-period base_amount_sum
  approximation. Deferred until the mechanism ships and the carry holds.
