---
generated: true
tags:
  - '#index'
  - '#synced-history-consumption'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:95bf01fd1379a0fdc23043f5700d9e6079daca2e78fb44d283db19909ffef3cc'
related:
  - '[[2026-08-08-synced-history-consumption-P01-S01]]'
  - '[[2026-08-08-synced-history-consumption-P01-S02]]'
  - '[[2026-08-08-synced-history-consumption-P01-S03]]'
  - '[[2026-08-08-synced-history-consumption-P01-S04]]'
  - '[[2026-08-08-synced-history-consumption-P01-S05]]'
  - '[[2026-08-08-synced-history-consumption-P01-S06]]'
  - '[[2026-08-08-synced-history-consumption-P01-S08]]'
  - '[[2026-08-08-synced-history-consumption-P01-S09]]'
  - '[[2026-08-08-synced-history-consumption-P01-S10]]'
  - '[[2026-08-08-synced-history-consumption-P01-S21]]'
  - '[[2026-08-08-synced-history-consumption-P01-S22]]'
  - '[[2026-08-08-synced-history-consumption-P01-S24]]'
  - '[[2026-08-08-synced-history-consumption-P01-S26]]'
  - '[[2026-08-08-synced-history-consumption-P01-S27]]'
  - '[[2026-08-08-synced-history-consumption-P01-S28]]'
  - '[[2026-08-08-synced-history-consumption-P02-S07]]'
  - '[[2026-08-08-synced-history-consumption-P02-S17]]'
  - '[[2026-08-08-synced-history-consumption-P02-S18]]'
  - '[[2026-08-08-synced-history-consumption-P02-S20]]'
  - '[[2026-08-08-synced-history-consumption-adr]]'
  - '[[2026-08-08-synced-history-consumption-plan]]'
  - '[[2026-08-08-synced-history-consumption-pulled-fact-classification-reference]]'
  - '[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]'
  - '[[2026-08-08-synced-history-consumption-research]]'
---

# `synced-history-consumption` feature index

Auto-generated index of all documents tagged with `#synced-history-consumption`.

## Documents

### adr

- `2026-08-08-synced-history-consumption-adr` - `synced-history-consumption` adr: `Which pulled AEAT facts are calculation inputs` | (**status:** `accepted`)

### exec

- `2026-08-08-synced-history-consumption-P01-S01` - Census every calculation input channel that could have consumed a pulled AEAT filing fact
- `2026-08-08-synced-history-consumption-P01-S02` - Prove the consumption rather than assuming it, in the direction S01 measured
- `2026-08-08-synced-history-consumption-P01-S03` - Classify each census row as calculation input, reconciliation target only, or display only
- `2026-08-08-synced-history-consumption-P01-S04` - Investigate whether previous renta values are consumed
- `2026-08-08-synced-history-consumption-P01-S05` - Investigate whether a ledger-derived casilla on a pulled work unit should be back-derived, left empty with an advisory, or refused
- `2026-08-08-synced-history-consumption-P01-S06` - Probe the over-payment direction deliberately
- `2026-08-08-synced-history-consumption-P01-S08` - Establish what a Sociedades filer's unpullable carries do on the consumption side
- `2026-08-08-synced-history-consumption-P01-S09` - Establish whether Modelo 200 and Modelo 202 can declare the authenticated filed-declarations read surface at all, keeping this separate from the consumption question S08 asks. The nine structurally excluded carry slots are a coverage gap in what the pull can FETCH, not a wiring gap in what the engine CONSUMES, and the two must not be ruled on as one. Determine from AEAT published material whether filed Sociedades declarations are exposed at the consulta view the reader is pinned to. If they are, the registry revisions are missing a live cross-reference and the nine become reachable. If AEAT does not expose them there, the nine are correctly unreachable and the honest output is a documented refusal naming the reason rather than a fix. Gate: the verdict cites AEAT published material rather than an inference from the registry silence, no live submission or remote mutation is performed, and either outcome lands as a change to the tree - a declared read surface or a recorded refusal - never as an open question
- `2026-08-08-synced-history-consumption-P01-S10` - Give the previous-filing channel a diagnostic
- `2026-08-08-synced-history-consumption-P01-S21` - Make the present-or-zero carry silence loud
- `2026-08-08-synced-history-consumption-P01-S22` - Advise the suffered-retencion carries that S21 correctly excluded, with the remedy their own case needs rather than the one S21 refused. S21 narrowed its bound-carry advisory on taxpayer_files_source, on the sound ground that telling a taxpayer their filing is missing is wrong advice when the payer files it, and that narrowing must stay. Measured against the loaded authority, the set it excludes is not theoretical: 19 bound-casilla carries whose source the taxpayer does not file, all Modelo 100 casillas 0596 fed by Modelo 111 and 0597 fed by Modelo 123, across the 2020 through 2025 revisions, every one declared direct_annual_settlement so it settles straight into the liquidation. A retencion suffered and not credited is tax the taxpayer already paid and pays again, so the silence runs in the OVER-declaration direction that nothing in this apparatus watches. The remedy is not a filing to capture. It is a value the taxpayer holds on an income certificate, which is exactly why the wrong-remedy advisory had to be excluded and why the right-remedy one is still missing. Note the countervailing design position before changing anything: a blank retencion is a legitimate zero for a taxpayer who had none, and the export-completeness rule already treats optional operator-input retenciones that way, so an unconditional advisory would fire on every filer with no withholding. A candidate discriminator is the declared IRPF income categories, since a filer declaring rendimientos del trabajo almost certainly suffered withholding. Gate: the advisory fires for a filer whose declared facts imply withholding and whose retencion carry is absent, stays silent for a filer whose facts imply none, names the income certificate rather than a filing to capture, and a mutation removing the discriminator makes it fire on the silent case
- `2026-08-08-synced-history-consumption-P01-S24` - Measure the carry-advisory volume rather than arguing it
- `2026-08-08-synced-history-consumption-P01-S26` - Carry the diagnostic subject onto the operator notice context
- `2026-08-08-synced-history-consumption-P01-S27` - Decide whether an unsatisfied previous-filing carry should refuse or advise
- `2026-08-08-synced-history-consumption-P01-S28` - Declare the trabajo net-income antecedent and the advisory predicate it enables, which is what makes the twelve casilla 0596 carries expressible. S22 established that the twelve suffered-retencion carries cannot be advised today because the revision carries no left-hand side for an implies_nonzero predicate, and that AEAT does model the concept: the bundled Manual practico de Renta 2024 Parte 1 page 234 runs a three-phase determination scheme terminating in rendimiento neto previo del trabajo, then rendimiento neto del trabajo, then rendimiento neto reducido del trabajo, indexed in the manual's own annex as an Esquema general. Whether the form carries a NUMBERED box for it is unsettled and does not need settling, because the antecedent must be declared internal_only. State that and state WHY in the fragment itself: an internal_only computed casilla is app-internal calculation support that production drops from the export layout, so it never enters the official numbered-box surface and cannot breach export parity, and without that comment a later reader sees a casilla with no official number and reads it as the export-parity defect this campaign has twice refused. Six fragments already declare internal_only including one on Modelo 100 itself, so the precedent is in the same modelo. Ground the casilla on the binding provisions the manual's scheme rests on rather than on the manual, which is AEAT material and good authority for structure but is not what establishes a compiled value. Ley 35/2006 articles 17, 18, 19 and 20 are all declared in the legal catalogue already. Then declare the ADVISORY implies_nonzero predicate whose antecedent is the new casilla and whose consequent is casilla 0596, matching the two ADVISORY predicates this revision already carries. Do the casilla, its construct and its bindings in ONE change, since the validator requires a construct's refs to cover its member casillas and its bindings and a partial sweep breaks registry load for everyone. Validate against a temp registry root rather than the shared path. Gate: the registry loads clean from a temp root, the predicate fires when the declared trabajo income is positive and casilla 0596 is zero, it holds silently when the income is zero so a filer with no trabajo income sees nothing, the diagnostic names the income certificate rather than a filing to capture because the taxpayer never filed Modelo 111, and a mutation removing the antecedent from the predicate stops it firing
- `2026-08-08-synced-history-consumption-P02-S07` - Author the decision record ruling which pulled facts are calculation inputs, which are reconciliation targets and which stay display only, plus the mechanism each wired channel uses from the existing one-mechanism-per-calculation-type taxonomy, amending that taxonomy in the same change if no row covers a needed channel. Open every implementing row in the SAME action as the ruling, because a decision record ruling on code is not self-executing and the debt it creates otherwise has no owner while every later reader sees the ruling as in force. Gate: the record cites the census denominator and every ruling maps to an opened row id
- `2026-08-08-synced-history-consumption-P02-S17` - Make the declared factual_evidence treatment actually gate consumption, since the registry draws the line and the resolver does not stand on it. classification.treatment is read at exactly one production site on the resolution path and folded into a requirement grouping key, so it discriminates bucketing and gates nothing, and a factual_evidence Modelo 193 retencion the taxpayer SUFFERED reaches the annual return by the identical path a direct_annual_settlement Modelo 130 pago fraccionado does. Per the ruling a factual_evidence carry is a reconciliation target and must not silently settle a casilla. The remedy must NOT be to blank the value, because a taxpayer is entitled to the retencion and a silent drop is the over-declaration direction this campaign already found unwatched. Surface it as a prefilled reconciliation value carrying its provenance and its treatment, distinguishable by a consumer from a settled figure. Gate: a factual_evidence carry and a direct_annual_settlement carry are distinguishable at the point a casilla value is produced, no value a taxpayer is entitled to is removed by the change, and a test drives one of each through the live calculate and asserts they are not interchangeable
- `2026-08-08-synced-history-consumption-P02-S18` - Declare a treatment for the seventeen carries that have none, because an undeclared treatment cannot later be cited as authority for having consumed the value. Fifteen previous_filing bindings and both iva_compensation_annual_partition bindings are governed by no dependency classification at all, spanning Modelo 100 negative-base carry, Modelo 130 prior pagos and negative results, Modelo 131 negative results across four revisions, Modelo 353 prior Modelo 322 figures, Modelo 720 prior-year valuation baselines and Modelo 390's two compensacion partition slots. Each declaration is grounded in that row's own provisions and never by analogy to a sibling modelo, since AEAT surfaces do not transfer between modelos and a Modelo 720 valuation baseline and a Modelo 130 negative result are not the same kind of carry. Gate: every one of the seventeen carries a declared treatment with its own legal refs and source refs resolving in the legal catalogue, no two are justified by the same transferred rationale, and the registry loads clean
- `2026-08-08-synced-history-consumption-P02-S20` - Establish the populated-enough scoping condition

### plan

- `2026-08-08-synced-history-consumption-plan` - `synced-history-consumption` plan

### reference

- `2026-08-08-synced-history-consumption-pulled-fact-classification-reference` - `synced-history-consumption` reference: `calculation input, reconciliation target, or display only`
- `2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference` - `synced-history-consumption` reference: `which pulled AEAT facts reach the calculation engine`

### research

- `2026-08-08-synced-history-consumption-research` - `synced-history-consumption` research: who consumes pulled AEAT filing history
