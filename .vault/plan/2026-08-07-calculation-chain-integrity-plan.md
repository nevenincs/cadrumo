---
tags:
  - '#plan'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:b57c5e89c29b35253dbce80662b91cf8417555ee29f3e6bba375026889190e97'
tier: L3
related:
  - '[[2026-08-07-silent-zero-regression-screen-research]]'
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-08-06-llm-invoice-read-reconciliation-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-07-calculation-chain-integrity-research]]'
---

# `calculation-chain-integrity` plan

## Steps

## Wave `W01` - Registry structural truth

A binding must declare where its aggregate lands. The M130 retenciones binding's target_casilla_id is the observation-match key, not the output casilla, which is hardcoded in application code as a parallel write path around the registry authority.

### Phase `W01.P01` - Declare the output casilla in the registry

Give the renta-income binding family a real output-casilla declaration so the registry states where an aggregate lands, then retire the hardcoded application-layer write path.

- [ ] `W01.P01.S01` - Read the linkage-design-audit T-05 hard-coded-constants prior art before designing anything, it may already prescribe this fix; `.vault/reference/2026-05-15-linkage-design-audit-reference.md`.
- [ ] `W01.P01.S02` - Give the renta-income binding family a declared output casilla so the registry states where an aggregate lands, distinct from the observation-match key; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.
- [ ] `W01.P01.S03` - Retire the hardcoded backend-inputs override once the registry declares the destination, removing the parallel write path around the registry authority; `src/cadrumo/application/aggregation/_modelo_bindings.py`.
- [ ] `W01.P01.S04` - Prove the retencion still reaches casilla 06 end to end after the override is retired, asserting the value not merely the wiring; `src/cadrumo/application/aggregation/tests/`.
- [ ] `W01.P01.S19` - Confirm no peer holds the retencion backend-inputs function before the first edit, the live over-claim and this structural fix are the same code site; `src/cadrumo/application/aggregation/_modelo_bindings.py`.

## Wave `W02` - Detection gates for the silent-zero class

Three mechanisms sit adjacent to a binding whose resolved value regresses to zero and each misses it for a different reason. Grounded by the silent-zero-regression-screen research; a decision record must precede any mechanism.

### Phase `W02.P02` - Decide the detection mechanism

Turn the research into an accepted decision record naming which mechanism ships, before any gate is built.

- [x] `W02.P02.S05` - Read the modelo-130-relation-regression ADR ruling on bound-casilla zero defaults as direct prior art, nothing in the research cites it; `.vault/adr/2026-05-26-modelo-130-relation-regression-adr.md`.
- [ ] `W02.P02.S18` - Read the relation-prefill zero-default authority before designing the screen, it is the single authority for which bindings are legitimately pre-satisfied with zero in a period and defines the screen's false-positive floor; `src/cadrumo/application/calculations/_relation_prefill.py`.
- [x] `W02.P02.S06` - Author the decision record selecting registry-build reachability as primary with the implies-nonzero coverage floor layered, rejecting prior-period comparison on its false-fire profile; `.vault/adr/`.

### Phase `W02.P03` - Build the chosen gate

Implement the decided mechanism with a mutation proof and an explicit statement of what it cannot catch.

- [ ] `W02.P03.S07` - Implement the reachability probe per binding source family, hung on the existing per-family module seam; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W02.P03.S08` - Mutation-prove the gate reddens on a binding retargeted to match nothing, and state in code what it cannot catch; `src/cadrumo/domain/calculations/registry/tests/`.

## Wave `W03` - The activity-type classification axis

RIRPF art. 95 fixes retencion rates on an axis the domain does not model. Three candidate placements already exist and must be reconciled rather than a fourth added. Unblocks M130 casilla 08, currently manual and silently zero for an agrarian-objetiva filer.

### Phase `W03.P04` - Reconcile the three candidate placements

Establish which of the profile field, the per-transaction marker, and the registry casilla is canonical, and record the ruling before any field is added.

- [x] `W03.P04.S09` - Reconcile the three existing candidate placements for the activity-type axis rather than adding a fourth, naming which is canonical; `src/cadrumo/domain/transactions/_models.py`.
- [x] `W03.P04.S10` - Record the placement ruling against the accepted silent-zero-base-aggregation ADR that already defers on this axis; `.vault/adr/`.
- [x] `W03.P04.S36` - Ground whether the AEAT tipo-de-actividad code set discriminates at the granularity art 95 needs including the one-percent engorde de porcino y avicultura carve-out, and if it does not, require the mapping to live in the registry rather than be inferred in code; `src/cadrumo/_data/corpus/aeat_official/`.

### Phase `W03.P05` - Land the axis and its dependents

Implement the canonical placement, then unblock the retencion regimen filter and M130 casilla 08.

- [ ] `W03.P05.S11` - Implement the canonical activity-type placement with its persistence roundtrip and anti-tautology proof; `src/cadrumo/domain/transactions/`.
- [ ] `W03.P05.S12` - Narrow the statutory-rate advisory to the rates a taxpayer can lawfully be subject to, restoring the flat-fee catch measured lost; `src/cadrumo/application/aggregation/_retencion_rate_advisory.py`.
- [ ] `W03.P05.S13` - Aggregate M130 casilla 08 agrarian volume from the ledger, currently manual and silently zero for an agrarian-objetiva filer; `src/cadrumo/application/aggregation/`.

## Wave `W04` - Decision-blocked dispositions

Fully grounded work correctly waiting on an operator ruling. No code moves here until the ruling lands.

### Phase `W04.P06` - Attach to the pending operator rulings

Track the classifier disposition and the shared-index decision against the records that already carry them, without opening competing ones.

- [ ] `W04.P06.S14` - Attach the classify_iva disposition to question one of the llm-invoice-read-reconciliation ADR rather than opening a competing record; `.vault/adr/2026-08-06-llm-invoice-read-reconciliation-adr.md`.
- [ ] `W04.P06.S15` - Fix the R13 wrong-clave mapping with its own M349-surface gate, required only if the ruling makes the classifier wireable; `src/cadrumo/domain/iva/_classification.py`.
- [ ] `W04.P06.S30` - Correct the pending ruling's premise, question one reasons from a single closed rate-to-category mapping while three exist and only one is the invoice-path mapping it means; `.vault/adr/2026-08-06-llm-invoice-read-reconciliation-adr.md`.

## Wave `W05` - Full-suite failure triage

The first trustworthy full-surface measurement produced a 22-item candidate-genuine worklist once environment buckets were separated.

### Phase `W05.P07` - Classify the candidate-genuine failures

Separate real defects from measurement artefacts with evidence, fixing anything this session's landings caused.

- [x] `W05.P07.S16` - Classify each candidate-genuine suite failure as defect, environment artefact, or caused by this session's landings, with evidence; `src/cadrumo/`.
- [ ] `W05.P07.S17` - Run the serial lane with workers disabled so the sixty held tests produce a result instead of an absence; `src/cadrumo/`.
- [ ] `W05.P07.S20` - Fix the installed-console help path constructing Settings and reaching the former-product database refusal, help must never need database access and the refusal must route through the translated error boundary instead of leaking a traceback; `src/cadrumo/entrypoints/cli/`.
- [ ] `W05.P07.S21` - Diagnose the ledger evidence-extract extra-forbidden regression on recargo_amount, lines, iva_breakdown and iva_category before fixing either side, getting the direction wrong would paper over a data-loss regression as test staleness; `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_extract_cli.py`.
- [ ] `W05.P07.S22` - Land the mechanical ratchet and rationale-marker fixes confirmed new since the pre-tonight baseline, each completing an already-argued intent rather than making a new decision; `src/cadrumo/`.
- [ ] `W05.P07.S23` - Rule whether the new einvoice XML parse error derives from the project error base or declares a bare-base rationale, a domain call not a mechanical fix; `src/cadrumo/adapters/inbound/einvoice/_xml.py`.
- [ ] `W05.P07.S31` - Classify the serial-lane perf-budget miss against a quiet baseline, measured P95 3.906 CPU-s against a 3.0 budget on a box that ran a large agent fleet all night; `src/cadrumo/application/aggregation/tests/test_ledger_scale_benchmark.py`.
- [ ] `W05.P07.S32` - Classify the packaging cohort inventory drift, six errors share one root cause where a stray gitignore sits in the build output directory outside the declared manifest; `dev/packaging/`.

## Wave `W06` - Standing canonicalisation and dedup sweep

Operator directive 2026-08-07: RAG semantic search is exercised extensively and continuously for codebase canonicalisation and dedup, not as a per-change precondition only. Search by domain and topic to find where a concept canonically lives and whether a feature is already fragmented across layers, then confirm exact sites with a targeted pass. A feature can be fragmented without any single site duplicating another, which is why a duplicate check passes while the real defect stands.

### Phase `W06.P08` - Sweep the calculation chain for fragmented authorities

Run the sweep over the surfaces this campaign touches, where three parallel-authority findings already landed tonight.

- [ ] `W06.P08.S24` - Sweep the retencion derivation surface by meaning for parallel authorities, the advisory the binding and the hardcoded write path each encode part of one concept; `src/cadrumo/application/aggregation/`.
- [ ] `W06.P08.S25` - Sweep the IVA category and clave surfaces by meaning, subjection and operation-type are separate axes and a third encoding of either is the failure to find; `src/cadrumo/domain/iva/`.
- [ ] `W06.P08.S26` - Sweep the observation-to-casilla routing surface by meaning, a binding declares its match key in the registry while its destination lives in application code; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W06.P08.S27` - Record each sweep as a near-neighbour proven not to cover the case or a fragmented authority named, never as a bare no-duplicates-found; `.vault/audit/`.
- [ ] `W06.P08.S28` - Collapse the three hand-maintained rate-to-IVA-category tables onto one canonical rate-kind table plus the existing accessor, after the adjacent retencion work clears the shared module; `src/cadrumo/domain/iva/_classification.py`.
- [ ] `W06.P08.S29` - Promote the canonical rate-kind mapping or an accessor onto the domain iva facade before any application-layer consumer reads it, it is private today and cross-package code must not dot into it; `src/cadrumo/domain/iva/__init__.py`.
- [ ] `W06.P08.S33` - Rule whether the cash-accounting exclusion set is scoped by the LIVA art 163 duodecies Uno territorial clause or enumerates only its Dos carve-outs, six members are Dos letters and one is a Uno scope case with nothing distinguishing them; `src/cadrumo/application/aggregation/_iva_ledger.py`.
- [ ] `W06.P08.S34` - Check the OSS declaration path before adding the second not-subject member to the cash-accounting exclusion, doing so newly refuses OSS rows for a taxpayer who also uses cash accounting and that combination is live; `src/cadrumo/application/aggregation/`.
- [ ] `W06.P08.S35` - Answer whether an invoice with no declared operation type can legitimately need the five claves the category fallback cannot emit, if not the fallback is correct by scope and must say so; `src/cadrumo/application/invoices/_source_resolver.py`.
