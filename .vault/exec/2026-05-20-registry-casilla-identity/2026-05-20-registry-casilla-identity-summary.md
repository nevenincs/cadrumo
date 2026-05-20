---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---

<!-- LINK RULES: [[wiki-links]] only in related: frontmatter; never in body.
     Name files/classes in inline backticks. -->

# `registry-casilla-identity` execution summary

Implements the accepted (amended) registry-casilla-identity ADR. Six
Phases, 31 Steps, all closed; every Phase independently code-reviewed
with verdict PASS. The registry can now represent multi-segment AEAT
modelos, and the calculation-completeness gate protects Modelo 200's
cuota chain.

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

Approximately 35 commits on `chore/eliminate-shims`; explicit-path
staging throughout in the shared worktree; no live AEAT write surface
touched.

## Open follow-up

The calculation-completeness manifest derivation tool currently produces
manifests only for Modelo 200 — the one modelo whose registry casilla
`number`s are genuine five-digit AEAT Diseño tags. The other 25
calculation-bearing modelos identify casillas by semantic slug or short
ordinal, so the Diseño-tag intersection is empty and no manifest is
derivable for them yet. This is a tooling-vocabulary gap, not a registry
defect: those modelos' calculation-closure casillas were verified
declared and legally grounded, and the gate stays correctly dormant for
them. Generalising the derivation tool to the semantic-slug vocabulary,
so the gate goes live for every calculation-bearing modelo, is the
recorded follow-up.

## Verification

All review verdicts PASS (P01, P03, P04, P06, P05 independently
reviewed; P02 reviewed in-phase). The full registry suite is green;
`test_modelo_parity_coverage` confirms all 26 modelos load valid; the
`(segmento, number)` identity gate has a load-bearing anti-tautology
proof. The M200 Liquidación cuota casillas now exist with correct
identity — unblocking the Modelo 200 cuota formula port.
