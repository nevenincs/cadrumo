---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---


# `registry-casilla-identity` execution summary

Implements the accepted and amended registry-casilla-identity ADR. Six
Phases, 33 Steps, all closed; every Phase and late amendment Step was
code-reviewed with verdict PASS. The registry can now represent
multi-segment AEAT modelos, the calculation-completeness gate protects
Modelo 200's cuota chain, typo-twin warning suppression is evidence
bound, and the Modelo 200 page-14 cuota formulas match the AEAT Manual
de Sociedades 2024.

## Outcome

- **Segment-scoped casilla identity** — `CasillaDefinition` carries an
  optional `segmento` field; the registry uniqueness invariant is
  `(segmento, number)` per modelo revision; single-segment modelos leave
  `segmento` unset and validate exactly as before. Reference resolution
  (validator and runtime graph) is segment-aware.
- **Calculation-completeness gate** — `RegistryValidator` enforces, per
  modelo with a manifest, that every casilla in the modelo's calculation
  closure (formula targets, transitive expression refs, binding/relation
  endpoints, verification operands) is declared, correctly
  `(segmento, number)`-identified, and carries `legal_refs` /
  `source_refs`. Semantics are `manifest-required ⊆ declared`. The gate
  is rollout-staged: a modelo with no manifest is not gated.
- **Modelo 200 Liquidación cuota chain registered** — the six casillas
  the old `id == number` model could not hold are now registered under
  segment-scoped identity: `DP200014:00552` (base imponible),
  `DP200014:00558` (tipo de gravamen), `DP200014:00562` (cuota íntegra),
  `DP200014B:00592` (cuota líquida), `DP200014B:00599` (cuota del
  ejercicio), `DP200014B:00611` (cuota diferencial) — each with labels,
  data types, and `legal_refs` / `source_refs` verified against the AEAT
  2024 Diseño de Registros. The M200 page-014 export binding and the
  M200 foundation construct were re-pointed off the ECPN occurrences.
- **M200 gate live** — the Modelo 200 calculation-completeness manifest
  is authored; M200 clears the live gate. All 26 modelos load valid.
- **Off-load-path Diseño coverage report** — the full-Diseño extraction
  is retained as a non-blocking advisory coverage inventory.
- **Singleton semantic-role warning policy** — typo-twin warning
  suppression is limited to an explicit singleton policy keyed by
  modelo, revision, casilla, semantic role, and exact `legal_refs` /
  `source_refs`. The policy covers the reviewed singleton pairs without
  suppressing true typo-like singleton roles by broad role prefix.
- **Modelo 200 cuota-chain correction** — the page-14 formula chain was
  corrected against the AEAT Manual de Sociedades 2024. Casilla `00599`
  now subtracts retenciones e ingresos a cuenta (`01766`, `01784`) from
  cuota líquida, while pagos fraccionados (`00601`, `00603`, `00605`)
  subtract at `00611`. The `01330`, `00562`, `00599`, and `00611`
  formulas are all segment-qualified and covered by manual-oracle tests.

Approximately 35 commits on `chore/eliminate-shims`; explicit-path
staging throughout in the shared worktree; no live AEAT write surface
touched.

## Open follow-up — resolved (2026-05-21)

The follow-up below has been resolved: the calculation-completeness
derivation is generalised and the gate is now live for every
calculation-bearing modelo.

Original follow-up: the manifest derivation produced manifests only for
Modelo 200 — the one modelo whose registry casilla `number`s are genuine
five-digit AEAT Diseño tags. The other calculation-bearing modelos
identify casillas by semantic slug or short ordinal, so the Diseño-tag
intersection was empty and no manifest was derivable for them.

Resolution. The derivation is now keyed on each closure casilla's own
registry `(segmento, number)` identity rather than on a five-digit
Diseño-tag intersection, so it is vocabulary-agnostic: it produces a
manifest for any calculation-bearing modelo regardless of whether its
casillas are Diseño tags, semantic slugs, or short ordinals. A new
identity-preserving closure walker (`calculation_closure_identities`)
resolves each calculation reference to the declared casilla it names and
keeps that casilla's full identity, so a multi-segment modelo's segment
is pinned by the calculation surface itself. For a multi-segment modelo
the derived segments are still verified against the AEAT Diseño de
Registros; for a single-segment modelo the registry identity alone is
authoritative.

A real defect surfaced and was fixed while generalising: the closure
walker had been folding *cross-modelo* binding `source_casillas` /
`source_output` into the closure. Those selectors name casillas on the
foreign `source_modelo`, not on the modelo being derived — the same
class of error the walker already excluded for `RelationDefinition.
source_output`. All 68 such selectors are cross-modelo; none are
within-modelo. They are now excluded, which is why the previous
Diseño-tag derivation surfaced them as undeclared "missing" tokens.

Outcome. Calculation-completeness manifests are now authored for every
calculation-bearing modelo revision — 39 manifest-bearing revisions
across 24 modelos (the Modelo 200 manifest is retained; the Modelo 100
2025 manifest was re-derived, confirmed identical, and converted off
`manual_extraction`). The load-blocking calculation-completeness gate is live for
every one of them: each manifest's closure casillas are declared, at the
correct `(segmento, number)` identity, and carry `legal_refs` /
`source_refs`. No modelo's closure revealed a missing or ungrounded
calculation casilla — zero findings. Modelo 308 and Modelo 360 carry no
calculation surface (empty closure) and correctly remain manifest-less.
All 26 modelos load valid; `test_modelo_parity_coverage` is green.

## Verification

All review verdicts PASS (P01, P03, P04, P06, P05 independently
reviewed; P02 reviewed in-phase; S32 and S33 reviewed as late amendment
Steps). The full registry suite was green at rollout;
`test_modelo_parity_coverage` confirms all 26 modelos load valid; the
`(segmento, number)` identity gate has a load-bearing anti-tautology
proof. The latest continuation verified the focused S32 semantic-role
tests, the singleton warning regression, and plan structure validation.
