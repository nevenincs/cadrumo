---
tags:
  - '#adr'
  - '#modelo-200-pyg-page-qualified'
date: '2026-11-14'
modified: '2026-11-14'
body_schema: 'body-v2'
body_hash: 'sha256:9cd0dc8ccf7d4abc17da8bd41212e3ceef84015af5eafb70fbf53130ae396a7d'
related:
  - "[[2026-09-02-registry-declaration-hardening-identifier-grammar-adr]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
  - '[[2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference]]'
---

# `modelo-200-pyg-page-qualified` adr: `Modelo 200 PyG casillas become page-qualified, with a stored-id migration` | (**status:** `proposed`)

## Problem Statement

The Modelo 200 record designs print the same box number on several pages with different
meanings. In the 2023 design, `[00255]` is "Cuenta de pérdidas y ganancias (I) - Operaciones
continuadas - Importe neto de la cifra de negocios" and also the Banco de España "Fondo de comercio
negativo", the aseguradoras "Prestaciones y gastos pagados" and the inversión colectiva
"Dividendos". `[00279]` is "Otros gastos de explotación" on the PyG page and a cooperativas
compensation line elsewhere. The 2024 and 2025 designs repeat the pattern
(`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_200/files/15-200-ejercicio-2023-actualizado-15-07-2024-10-4-mb-xls.xls.extracted.md:725`,
`:759`, `:3835`, `:5639`, `:6150`, `:6836`). The registry declares these PyG lines with bare
numeric ids, so a bare id cannot name the PyG line, and the loader requires page qualification for
a number printed on more than one page.

The consequence is that the sociedad-limitada persona's cuenta de pérdidas y ganancias cannot be
entered or checked. Its expectations mark `00255` (30800.00) and `00279` (5400.00, carried
negative per the Manual práctico de Sociedades 2024 sign convention) as not sourced. The four
sociedad M200 rows therefore stay `unverified` in the persona table: backend 286/290, by PRIME's
02:04 ruling (option b).

This record lays out option (a) for the operator. PRIME and CALC-IVA recommend deferring it.

## Considerations

- Renaming a casilla id is an identity change, not a rename. Continuity chains,
  previous-filing selectors, export field references and record row mappings move in the same
  change, with an operator-reviewed preview (`2026-09-02-registry-declaration-hardening-identifier-grammar-adr`).
- Page-qualified ids are an existing compound grammar (2009 casillas use it), so no new grammar
  is needed. Modelo 200 must declare that it uses the grammar for the PyG role.
- Stored data keys on casilla ids: persisted calculation revisions, operator overrides, work
  inputs, prior-filing observations and bindings. A bare-to-qualified change without migration
  orphans every stored Modelo 200 calculation that holds a PyG value.
- The registry is delta-keyed. Each PyG line is declared once at the earliest edition that
  prints it identically, and later editions inherit it.
- `2026-06-03-m200-internal-casilla-discipline-adr` governs the internal M200 working figures.
  The PyG lines are printed official boxes, not internal casillas, so that record is unaffected.
- The PyG figures come from the company's closed accounts. Like `00501`, they are entered as work
  inputs from those accounts, never derived from the ledger by inference.
- Unproven evidence: parked ref `refs/calc-iva/pyg-wip` (`9de3e98698`, 87 files). It carries
  page-qualified PyG ids `DP200007:00255` and others across the 2022-2025 casillas, constructs,
  bindings and manifests, 29 new same-number declarations, regenerated layouts and persona work
  inputs. No registry gate, test or persona row was run on it.

## Considered options

### (a) Page-qualify the PyG lines and migrate stored ids

Declare every PyG line page-qualified (`DP200007:00255` and so on) at its earliest identical
edition. Retire the bare-id declarations. Ship a versioned migration that rewrites stored
calculation revisions, overrides, work inputs, observations and bindings from the bare ids to
their page-qualified ids. Where a stored value cannot be attributed to exactly one page, the
migration refuses that row instead of guessing.

### (b) Keep 00255 and 00279 not sourced (current ruling)

The four rows stay `unverified` and say so. No persisted schema changes. This is the state PRIME
ruled at 02:04.

### (c) Qualify only the persona-needed boxes

Rejected. It leaves the other colliding PyG numbers ambiguous and needs the same migration
machinery, so it saves no cost.

## Constraints

- No stored value may change meaning. The migration must be proven by a test that compares every
  calculated casilla value before and after on real stored revisions, plus a refusal test for an
  ambiguous row.
- Export layouts, the form layout and the completeness manifest are regenerated from their owners
  for the affected editions, never hand-edited.
- Every Modelo 200 edition in the support envelope is proven, enumerated from the registry
  envelope (no year list).
- Acceptance does not raise any filing grade. The 2024 grade change (`refs/calc-iva/m200-2024-grade`)
  keeps its own review bar: own-year export round trip, cited formulas, own-year oracle,
  ACCEPTANCE review and PRIME approval.

## Implementation

If accepted: one L1 plan with these Steps.

1. The page-qualified PyG declarations and the grammar declaration, rebased from `pyg-wip` and
   proven by `just check-registry`, `just check-registry-gate`, `just check-bindings` and the
   edition-delta minimality lanes.
2. The stored-id migration with a dry-run preview and the before/after equality test.
3. The persona work inputs for the PyG and the retirement of the not-sourced expectation blocks.
4. The four sociedad M200 rows rerun through backend, CLI, TUI and window.

## Rationale

Option (a) is the only path that lets the four rows verify the PyG instead of declaring it
unsourced, and it resolves every colliding PyG number at once rather than box by box. Its cost is
a persisted identity migration, which the identifier-grammar decision requires to be explicit
and operator-reviewed. That cost is why it needs the operator's acceptance.

Recommendation: defer (keep option b). The four rows are backend-only (the TUI column already
passes them), and the migration touches every stored Modelo 200 calculation. It should be
scheduled when Modelo 200 grade work resumes, not inside the frontend-priority phase.

## Consequences

- If accepted: the four sociedad M200 rows can move from `unverified` to verifiable. Backend
  286/290 can reach 290/290 once each year's filing grade also passes its own review. Every other
  colliding PyG number is addressed the same way. The gasto por impuesto lines (`00326`, `00327`,
  `00500`) then need persona facts.
- If deferred: nothing changes. The rows keep stating why they are unverified, and `pyg-wip`
  stays parked as unproven evidence.
- Reconsider when Modelo 200 filing-grade work is scheduled, or when another persona needs a PyG
  line that collides across pages.
