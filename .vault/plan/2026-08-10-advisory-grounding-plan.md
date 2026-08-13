---
tags:
  - '#plan'
  - '#advisory-grounding'
date: '2026-08-10'
modified: '2026-08-13'
body_hash: 'sha256:e24259e29239528738ecc4d88aad147fb8b6ca2612d159a5f40125cb0d2c38ba'
tier: L2
related:
  - '[[2026-08-10-advisory-grounding-adr]]'
  - '[[2026-08-10-advisory-grounding-reference]]'
---

# `advisory-grounding` plan

## Description

## Steps

### Phase `P01` - Mechanism and build-time validation

Give an advisory a typed place to declare the provisions it asserts, and make registry build refuse a declared id that does not resolve.

- [x] `P01.S01` - Give CalculationSourceDiagnostic a typed place for an advisory to declare the provisions it asserts itself, distinguished on the diagnostic from the casilla-derived path that the one existing correct instance uses. The two are not alternatives and neither replaces the other. Record the subject distinction on the type so a future author copying the casilla-derived instance onto an eligibility-rule advisory is stopped by the type rather than by convention; `src/cadrumo/application/, src/cadrumo/core/`.
- [x] `P01.S02` - Refuse at registry build any declared provision id that does not resolve to a legal-catalogue entry. This is the check the prose form could never carry. State a control proving the legitimate population still passes and do not close on the refusal firing. The disconfirming observation: if the control shows a legitimate advisory declaring an id that does not resolve, the catalogue is incomplete for that provision and this row must stop and report rather than relax the refusal; `src/cadrumo/domain/calculations/registry/, src/cadrumo/tests/`.

### Phase `P02` - Per-site adjudication

Decide, per site, which catalogue entry the message actually asserts. This is a tax review per site rather than a sweep, and the art-81 sites are gated.

- [x] `P02.S03` - HARD GATE, read before any conversion. Do not convert the art-81 advisory sites until the ley-35-2006 art-81 catalogue entry is repointed off the two-vintage excerpt, or exclude them explicitly from every conversion row. Casilla 0613 carries exactly one ref and its corpus target lacks the 81.2 turning-three extension, the 81.3 complemento-de-ayuda-para-la-infancia exclusion and the 150-euro increment, which are the clauses those advisories assert. Converting first makes them look grounded while citing a document that does not contain the rule, which is strictly worse than the prose because the prose claims no corroboration. Record in this row which of the two dispositions was taken; `src/cadrumo/_data/registry/aeat/legal/irpf.toml, src/cadrumo/application/modelo/`.
- [x] `P02.S04` - Adjudicate per site which catalogue entry each advisory message actually asserts, and declare it. This is a tax review against the provision the message states, never a lookup, and it does not parallelise into a sweep. Where the casilla already carries the exact provision the derivation is correct and should be used. Where the catalogue carries a finer entry the casilla does not reference, declare the finer one and record why the casilla's coarser ref was not used. Do NOT append the finer entry to the casilla legal_refs to make a derivation work, because a casilla's refs describe what establishes that box and an eligibility rule governing one of its inputs is a different subject. EXCLUDED FROM THIS ROW BY THE S03 HARD GATE, and the exclusion is not a deferral of convenience: the four Art. 81 guarderia advisory sites in the minimo-descendientes advisory module are _guarderia_shape_advisory, _segundo_ciclo_month_advisory, _cotizaciones_ceiling_advisory and _guarderia_madre_meses_advisory, carrying source kinds guarderia_spend_needs_monthly_detail, guarderia_segundo_ciclo_month_undeclared, guarderia_cotizaciones_ceiling_unbounded and guarderia_madre_meses_undeclared. Do not declare a provision on any of them. The ley-35-2006 art-81 entry still cites the two-vintage excerpt: the repoint is prepared under the legal-corpus-vintage plan and is waiting on an operator stamp, so declaring these ids now would resolve them against a document that does not contain the clauses the messages assert, which is worse than the prose because the prose claims no corroboration. Re-open them here only once that stamp lands; `src/cadrumo/application/modelo/, src/cadrumo/application/aggregation/`.

### Phase `P03` - Population C threading

Thread a registry object into the five modules that hold none, as its own change with its own blast radius.

- [x] `P03.S05` - Thread a registry object into the five modules that hold none, as its own change rather than inside a citation change. The invoice-devengo advisory, the retencion-rate advisory, the invoice source resolver and the prior-payment advisory hold no revision, snapshot or casilla definition anywhere. Every provision they cite has a catalogue entry, so this is threading rather than grounding. The disconfirming observation: if threading a revision into any of these modules would invert a dependency direction the architecture forbids, stop and report rather than route around it, because that would mean the advisory belongs at a different layer; `src/cadrumo/application/aggregation/, src/cadrumo/application/invoices/`.
- [ ] `P03.S06` - Read the twelve modules that assert no provision in either form and record, per module, whether that silence is proper. Nothing measured so far says they are proper and nothing contradicts it, so this row exists to convert an untested assumption into a stated finding. A diagnostic about wiring rather than law correctly carries no provision. The disconfirming observation: any module found asserting a regulatory claim through a channel the earlier regex could not see, such as a formatted or multi-line message, belongs in the P02 population and this row must say so rather than close on the count; `src/cadrumo/application/`.

## Parallelization

## Verification
