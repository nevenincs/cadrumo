---
tags:
  - '#plan'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_hash: 'sha256:ac21215d7b7fe1b73d8e8ebaf7bb530d607f018d3187643ffb54d70e0718c6d7'
tier: L2
related:
  - '[[2026-08-08-synced-history-consumption-research]]'
  - '[[2026-08-08-synced-history-consumption-adr]]'
---
# `synced-history-consumption` plan

## Description

## Steps

### Phase `P01` - Investigate what the sync reaches

Establish, by measurement rather than inference, which pulled AEAT facts reach the calculation engine and which are persisted and never read. The gap presents as a legally valid zero rather than as an error, so nothing here may rely on a blank or a refusal as its signal.

- [ ] `P01.S01` - Census every calculation input channel that could have consumed a pulled AEAT filing fact, derived from the LOADED snapshot through the registry authority and never from a directory listing or a file-shape glob, since directory-mode fragments hold most of the corpus. For each binding source kind, relation and cross-period carry, record whether a pulled filed observation is reachable, reaches it today, or is structurally excluded. Read each binding's source field before classifying an absent value, because a profile binding is not a ledger silent-zero and a deferred kind is not a gap. Gate: the census is a committed reference stating its denominator, and it reports the one wired channel as one row out of that total rather than as the headline; `src/cadrumo/application/calculations, src/cadrumo/application/aggregation, src/cadrumo/domain/calculations/registry`.
- [ ] `P01.S02` - Prove the silence rather than asserting it: land a regression showing a profile whose AEAT history was pulled produces the same engine output as a profile with no history at all, for at least one non-IVA-wallet channel the census marks reachable. Gate: the assertion compares two real runs through the production calculate path over one law-resolved revision rather than a hand-built expectation, and a companion mutation proves the two runs CAN differ, so the equality is not tautological; `src/cadrumo/application/calculations/tests`.
- [ ] `P01.S03` - Classify each census row as calculation input, reconciliation target only, or display only. Ground the classification in the existing non-official-evidence boundary: a pulled filing is evidence of what was declared and is not automatically an authorised input to a new computation, which is why local app filings are already held distinct from AEAT filing evidence. Gate: every row carries a stated rationale with legal or decision-record grounding, and no row is classified by analogy to a sibling modelo, since AEAT surfaces do not transfer between modelos; `no production files, classification only`.
- [ ] `P01.S04` - Investigate whether previous renta values are consumed, since Modelo 100 carries the longest cross-year dependency chain and the carry path is the one place a revision error compounds across years. Establish whether a pulled prior-year renta filing can feed the current year at all, and whether its stamped revision would survive the re-confirmation the carry path requires. Gate: the finding names which mechanism the carry would use from the one-mechanism-per-calculation-type taxonomy, or records that no row covers it and the taxonomy needs amending before any code lands; `src/cadrumo/application/calculations, src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `P01.S05` - Investigate whether a ledger-derived casilla on a pulled work unit should be back-derived from the pulled declared value, left empty with an advisory, or refused. Name each option's failure mode: back-derivation invents transactions that never existed and corrupts the evidence bundle, empty-with-advisory leaves a legally valid zero that reads as settled, and refusal blocks an onboarding flow the taxpayer needs. Gate: the recommendation preserves its rejected alternatives and their failure modes, including the paragraph that undercuts the recommendation; `no production files, investigation only`.
- [ ] `P01.S06` - Probe the over-payment direction deliberately, because the existing apparatus watches under-declaration and nothing watches a taxpayer paying too much. Establish whether a synced-but-unconsumed history can produce an over-declaration and whether any surface would signal it. Gate: the finding states plainly whether a signal exists, and if none does it opens its own row rather than being left as a note; `src/cadrumo/application/modelo, src/cadrumo/application/calculations`.

### Phase `P02` - Rule on consumption and open the implementing rows

Decide which pulled facts are calculation inputs, which are reconciliation targets, and which stay display only, then open every implementing row in the same action as the ruling so the debt the decision creates has an owner.

- [ ] `P02.S07` - Author the decision record ruling which pulled facts are calculation inputs, which are reconciliation targets and which stay display only, plus the mechanism each wired channel uses from the existing one-mechanism-per-calculation-type taxonomy, amending that taxonomy in the same change if no row covers a needed channel. Open every implementing row in the SAME action as the ruling, because a decision record ruling on code is not self-executing and the debt it creates otherwise has no owner while every later reader sees the ruling as in force. Gate: the record cites the census denominator and every ruling maps to an opened row id; `no production files, decision record only`.

## Parallelization

## Verification
