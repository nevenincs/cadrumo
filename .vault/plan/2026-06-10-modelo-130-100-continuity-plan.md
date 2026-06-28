---
tags:
  - '#plan'
  - '#modelo-130-100-continuity'
date: '2026-06-10'
modified: '2026-06-10'
tier: L2
related:
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
  - '[[2026-06-10-modelo-130-100-continuity-research]]'
---
# `modelo-130-100-continuity` `Annual M100 fold-in of quarterly M130 pagos fraccionados` plan

### Phase `P01` - Ground and decide

Ground the M100 annual fold-in of M130 pagos fraccionados in AEAT instructions + the registry; decide the continuity design in a feature ADR

- [x] `P01.S01` - Research the M100 annual fold-in of M130 pagos fraccionados: identify the M100 casilla that credits pagos fraccionados ingresados, how the registry models the M130->M100 fold-in, and whether the Wave-C cross-period carry infra (filed observations + previous_filing resolver) is the mechanism or a dedicated annual aggregation is needed; `.vault/research; registry M100/M130 TOML; application/calculations`.
- [ ] `P01.S02` - Author the feature ADR deciding the M130->M100 continuity design (carry-reuse vs dedicated fold-in aggregation; `target casilla; cross-period evidence/provenance; no-silent reconciliation); `.vault/adr`.

### Phase `P02` - Implement the fold-in continuity

Wire the four filed M130 quarterly results into the M100 annual pagos-fraccionados casilla via the decided mechanism

- [ ] `P02.S03` - Implement the fold-in: credit the four filed M130 quarterly results into the M100 annual pagos-fraccionados casilla via the decided mechanism, grounded in AEAT M100 instructions (no fabricated casilla routing); `registry M100; application/modelo; application/calculations`.
- [ ] `P02.S04` - Carry provenance + binding/persistence wiring so each credited M130 result is traceable on the M100 revision; `reuse the single resolver/persistence primitives (no parallel write path); `application/modelo; application/calculations`.

### Phase `P03` - Verify end-to-end

E2E autónoma M130 Q1-Q4 filed -> M100 annual with pagos fraccionados credited correctly; real adapters, anti-tautology

- [ ] `P03.S05` - E2E test: autonoma profile files M130 Q1-Q4 (real adapters, isolated store) then the annual M100 credits the summed pagos fraccionados in the correct casilla; `assert exact reconciliation, anti-tautology, no mocks/skips; `application/modelo/tests; entrypoints/cli/tests`.
- [ ] `P03.S06` - Verify the annual declaration reconciles the year's advance payments and surfaces a non-silent alert on any pagos-fraccionados mismatch; `grounding-confirm the casilla values against an AEAT worked example; `verification; tests`.

## Description

> **STATUS — PAUSED at P01.S02 (2026-06-10).** This plan is BLOCKED behind two foundational
> calculation-engine ADRs decided per operator directive: (1) a binding ADR codifying the
> calculation **aggregation-mechanism taxonomy** (which mechanism is canonical per calculation
> type — the relation-vs-previous_filing overlap this plan surfaced is a symptom), and (2) an
> overview ADR for a deterministic **period→revision resolution engine** (revision is fixed by
> law per (modelo, year, period), never a hardcoded choice). The P01.S02 mechanism/target-revision
> decision is subsumed by those ADRs and must not be taken here until they land. P01.S01
> grounding is complete and stands. Resume P01.S02+ only after both foundations are accepted.

The annual Modelo 100 (Renta / IRPF) is the operator's actual tax filing; the four
quarterly Modelo 130 pagos fraccionados are advance payments that the annual declaration
must credit so the year reconciles. The autónomo E2E pipeline has never driven this
fold-in — the quarterly M130 results are filed but never folded into the M100 annual
casilla for pagos fraccionados ingresados, so the most load-bearing leg of the filing is
unproven. This plan grounds, decides, implements, and end-to-end verifies that fold-in.

A concrete mechanism hypothesis to test in Phase 1: the cross-period carry infrastructure
landed in the `modelo-iva-routing-carry` Wave C (local `file` now persists each filed
revision's observations under a non-official `source_kind`, and `PreviousFilingSourceResolver`
is enrolled in the calculate mesh) may already be the vehicle — the four filed M130 results,
persisted as observations, could feed the M100 annual fold-in through `previous_filing`
without a new write path. Phase 1 confirms whether that carry reuse is correct or a
dedicated annual aggregation is required, grounds the target M100 casilla against AEAT
instructions (no fabricated routing), and records the decision in a feature ADR. Phases 2-3
implement and prove it E2E. This plan is the resourced home for the work tracked as the
CRITICAL backlog item; the broader autónomo pipeline (other profiles) and the unrelated
backlog (short-hash resolution, the Stream-3 deferral triage, the M100 drift-test orphan
params) stay tracked in the harness task list and earn their own plans when picked up.

## Steps







## Parallelization


## Verification
