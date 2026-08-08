---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:79141d1bbdf268dcd58bc11bb39306a8aa6be2a0d360233a476b742596fd9396'
step_id: 'S22'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Advise the suffered-retencion carries that S21 correctly excluded, with the remedy their own case needs rather than the one S21 refused. S21 narrowed its bound-carry advisory on taxpayer_files_source, on the sound ground that telling a taxpayer their filing is missing is wrong advice when the payer files it, and that narrowing must stay. Measured against the loaded authority, the set it excludes is not theoretical: 19 bound-casilla carries whose source the taxpayer does not file, all Modelo 100 casillas 0596 fed by Modelo 111 and 0597 fed by Modelo 123, across the 2020 through 2025 revisions, every one declared direct_annual_settlement so it settles straight into the liquidation. A retencion suffered and not credited is tax the taxpayer already paid and pays again, so the silence runs in the OVER-declaration direction that nothing in this apparatus watches. The remedy is not a filing to capture. It is a value the taxpayer holds on an income certificate, which is exactly why the wrong-remedy advisory had to be excluded and why the right-remedy one is still missing. Note the countervailing design position before changing anything: a blank retencion is a legitimate zero for a taxpayer who had none, and the export-completeness rule already treats optional operator-input retenciones that way, so an unconditional advisory would fire on every filer with no withholding. A candidate discriminator is the declared IRPF income categories, since a filer declaring rendimientos del trabajo almost certainly suffered withholding. Gate: the advisory fires for a filer whose declared facts imply withholding and whose retencion carry is absent, stays silent for a filer whose facts imply none, names the income certificate rather than a filing to capture, and a mutation removing the discriminator makes it fire on the silent case

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/domain/calculations/registry`

## Description

- Pinned the excluded set exactly rather than by its total, since the remedy differs per casilla.
- Tested the candidate discriminator instead of adopting it, in both directions the row asks about.
- Looked for the mechanism a recommendation would use before proposing one, and found the registry already ships it and this modelo already declares two instances of it.
- Established, per casilla, whether the antecedent that mechanism needs exists today.
- Built nothing. The row is investigate-and-recommend and the discriminator is a design choice.

## Outcome

THE SET IS 19 AND IT IS THREE POPULATIONS, NOT ONE. Casilla 0596 fed by Modelo 111 accounts for 12, two per revision across 2020 through 2025. Casilla 0597 fed by Modelo 123 accounts for 6, one per revision. One more, casilla 1577 fed by Modelo 184, accounts for the last. All are bound casillas declared not-required, which is the present-or-zero shape, and all are declared `direct_annual_settlement`, so each settles straight into the liquidation.

THE CANDIDATE DISCRIMINATOR FAILS, IN ONE DIRECTION ONLY, AND THAT IS DECISIVE. The declared IRPF income categories are six: actividad economica, trabajo, capital inmobiliario, capital mobiliario, ganancias patrimoniales and pension. The ruling-out direction holds well: a filer declaring no trabajo and no pension has no rendimiento subject to the Modelo 111 withholding that feeds 0596. The ruling-IN direction does not hold at all, and its failure is a tax fact rather than a modelling gap: withholding on rendimientos del trabajo is scaled to the payer's projected annual withholding rate, which is legitimately ZERO below the withholding thresholds, so an employee or a pensioner under those thresholds declares trabajo income and correctly reports no retencion. An advisory keyed on the category alone would therefore fire on exactly the low-income filers least able to dismiss it, which is the alert-fatigue failure this campaign has now refused three times.

So the category is usable as an additional SUPPRESSOR and unusable as the firing signal. Recommending it as the discriminator would have been wrong, and the row asked for it to be tested rather than adopted, which is why it was.

THE MECHANISM ALREADY EXISTS AND NEEDS NO NEW MACHINERY. An ADVISORY `implies_nonzero` verification predicate fires precisely when its antecedent is strictly positive and its consequents are zero, holds trivially when the antecedent is at or below zero, and is already evaluated on the live path into a typed diagnostic naming the positive antecedent and the unpopulated boxes. Modelo 100 for 2024 declares exactly two verification predicates, both ADVISORY, and one of them is already of this shape. Neither covers 0596 or 0597. So the recommendation is to declare a predicate, not to build a channel.

AND THE ANTECEDENT EXISTS FOR ONE POPULATION BUT NOT THE OTHER, WHICH SPLITS THE RECOMMENDATION.

For 0597, capital mobiliario, the antecedent exists. The revision carries computed casillas holding capital-mobiliario income, so a predicate whose antecedent is one of those and whose consequent is 0597 is expressible today with no registry addition beyond the predicate itself. Six of the 19 are covered this way.

For 0596, rendimientos del trabajo, the antecedent DOES NOT EXIST. Searching the revision for a casilla naming trabajo income and excluding retenciones and reductions returns seven casillas, and every one of them is a deduction, an increment or an accessory item. Not one is a rendimientos-del-trabajo income total, and none is computed. So there is nothing in the revision to put on the left-hand side of the predicate, and the twelve carries that matter most cannot be advised through this mechanism as the registry stands.

THAT IS THE MISSING SIGNAL, NAMED. Modelo 100 for 2024 declares no computed rendimiento-neto-del-trabajo total. Either the revision gains one, which is a registry-grounding change with its own legal refs and is not this row's to make, or a different signal is needed for the trabajo half. The ledger is the obvious candidate and was deliberately not assessed here, because whether a taxpayer's ledger is populated enough for its silence to mean anything is the same underivable precondition another row is already blocked on.

THE REMEDY WORDING IS CONSTRAINED, and this is the part most likely to be got wrong by whoever implements it. An uncredited suffered retencion is corrected by entering the figure from the payer's income certificate. It is NOT corrected by capturing a filing: the taxpayer never filed Modelo 111, 123 or 184, and the pull cannot fetch a return filed by somebody else about them. Any surface that tells this operator to pull something repeats the wrong-instruction defect this campaign has now hit four times, most recently an advisory telling a Sociedades filer to capture a period they cannot obtain.

## Verification

    uv run --no-sync python -c "<join over the loaded authority>"
    total: 19
    by casilla: {'0596': 12, '0597': 6, '1577': 1}
    by source modelo: {'111': 12, '123': 6, '184': 1}
    revisions: ['2020', '2021', '2022', '2023', '2024', '2025']

    uv run --no-sync python -c "<M100 2024 predicates and casilla labels>"
    M100/2024 verification predicates: 2
      implies_nonzero(["0500", "0595"])                              ADVISORY
      deduccion_requires_adquisicion_before([...])                   ADVISORY
    any predicate mentioning 0596 or 0597 at all: False
    0596  req=False kind=bound  Por rendimientos del trabajo
    0597  req=False kind=bound  Por rendimientos del capital mobiliario

    computed casillas naming capital mobiliario: ['0041', '0060', '0436', '1283', '1601', '1602']
    casillas naming trabajo income excluding retenciones: 7, all manual, none an income total

Every figure is read off the loaded registry authority rather than from a directory listing or from prose, and the casilla semantics are taken from each casilla's own official label rather than inferred from its number.

The one-directional failure of the category discriminator is argued from tax law rather than measured, and is marked as such: no probe here demonstrates a real filer with trabajo income and a lawful zero retencion, because the tree holds no such fixture. The measurable half is that the registry declares no link between an income category and a withholding expectation anywhere, so nothing in the tree supports using it as a firing signal either.

No pytest lane was run and no production code was changed. This row is an investigation and its output is a recommendation.

## Notes

WHAT I DID NOT ESTABLISH. Whether casilla 1577, fed by Modelo 184, has an available antecedent. It is one carry of the nineteen, its source is the attribution-of-income regime rather than a withholding return, and treating it as a third case without measuring it would be the analogy this campaign forbids. It needs its own look before any predicate is declared for it.

WHY THIS IS NOT SIMPLY A REGISTRY OMISSION TO FILE. The absent trabajo-income total may be correct for this modelo: the official Renta return does not necessarily carry a single rendimiento-neto-del-trabajo box that a predicate could read, and inventing one to make an advisory expressible would put a casilla in the registry that AEAT's own form does not model, which is the failure the export-parity discipline exists to prevent. Establishing whether AEAT models such a total is a diseño question, and it is the precondition for the trabajo half rather than a detail of it.

THE COUNTERVAILING DESIGN POSITION STANDS AND IS NOT OVERRIDDEN HERE. A blank retencion is a legitimate zero for a filer who had none, and the export-completeness discipline already treats optional operator-input retenciones that way. Nothing in this recommendation makes a blank retencion an error. The proposal is an ADVISORY that fires only when the same return declares the income the withholding would have accompanied.
