---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:85fd1b6e67a876e04583406aeb12d0cd1f98161fbca3a6a6e99b4efc1d948175'
step_id: 'S56'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S56

## Outcome

**Not crossed, because the crossing is currently inexpressible** — established by measurement rather than by judgement. The prerequisite is a revision-shape decision that this Step does not own.

## The four regimenes are real and identifiable

Read from the loaded M390 snapshot, the regimen axis the Step refers to is visible in the casilla set:

- **régimen general** — `iva.anual.repercutido.{general,reducido,super-reducido}`
- **recargo de equivalencia** — `iva.anual.repercutido.recargo.{general,reducido,super-reducido}`
- **régimen simplificado** — `iva.anual.reconciliacion.devengada-simplificado-303`
- **inversión del sujeto pasivo** — `iva.anual.autorepercutido.intracomunitaria`

So the Step's framing is sound: these are axes to cross the rate against, not category members to fan out. The cash-accounting precedent it cites is the right shape.

## Why the crossing cannot land yet

Two measured facts, and together they block it:

- `CasillaDefinition` carries **no** validity dates. Its fields are id, number, section, data_type, semantic_role, binding, formula, legal_refs, source_refs and so on — `valid_from` / `valid_to` exist only on `ModeloRevision` (`_schema.py:1085-1086`).
- Modelo 390 has **one** revision. `2010-y-siguientes`, `valid_from=2010-01-01`, `valid_to=None`.

So any per-rate casilla added for the temporary 2%, 5% and 7.5% rates would be present for **every filing year from 2010 onward**. That is wrong in both directions: those rates did not exist for 2010 through 2022, and `W06.P08.S49` measured that the 2025 diseño **zero-mandates** exactly those boxes — casillas `[667]`-`[670]` carry `Nota 2: estas casillas deben estar rellenas a 0`.

Adding them now would model, for the current filing year, boxes AEAT has switched off.

## Why this is a decision rather than an implementation detail

Two shapes resolve it and they are not equivalent:

- **Split the M390 revision by year**, which is how AEAT itself versions the diseño — the corpus bundles separate 2016, 2017, 2018, 2019-2020, 2021, 2024 and 2025 workbooks. This matches the authority but multiplies the revision surface for a modelo currently carrying 22 casillas against 375 official boxes.
- **Effective-date casillas** within a revision, which is a schema change to `CasillaDefinition` affecting every modelo, not just this one.

Either is defensible; picking one in passing while authoring rate bindings is exactly the "implementation choice made in passing" that `W01.P01` had to revert once already in this campaign.

## Where this connects

This is the third finding in one chain, and they only make sense together:

- `S49` refuted widening `IvaRateKind`, because the temporary rates are effective-dated **values**, not tiers.
- `S53` landed those values on the rate table, and hit the same time-shape from the other side: the tier lookup is single-valued per tier per date, so the loader refuses a same-tier window collision.
- `S56` now finds the annual **form** has no way to say when a box is live.

The rate axis is time-aware at the value layer and time-blind at the casilla layer. That mismatch is the real work, and it is bigger than crossing an axis.

## Scope note

`src/cadrumo/_data/registry/aeat/modelos/390/` is deliberately unchanged. The row is re-scoped to name the blocker so the next reader meets the measurement rather than the instruction.
