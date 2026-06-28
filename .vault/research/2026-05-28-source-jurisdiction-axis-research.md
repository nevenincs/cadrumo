---
tags:
  - '#research'
  - '#source-jurisdiction-axis'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---



# `source-jurisdiction-axis` research: `aggregation classifier vs predicate`

Architecture decision memo for the deferred per-row source_jurisdiction aggregation gating in the M210 IRNR Phase 2 plan W02.P03 (open question). Two shapes are viable for the runtime gate: an aggregation-time classifier that emits typed issues per row, or a registry-authored predicate evaluated at the verification phase. This memo compares them and recommends the classifier.

## Context

The source_jurisdiction axis lands at the CLI create boundary in the cross-domain-continuity #258 chain. Each ledger row carries an ISO 3166-1 alpha-2 jurisdiction string; the CLI gate refuses non-resident profiles that omit the flag and impatriado profiles that omit the flag (TRLIRNR Art 2/10 and LIRPF Art 93.5 anchors). Resident-general profiles get a silent ES default per LIRPF Art 8.

At the aggregation surface, the resident-IRPF M130/M100 engine propagates the field but does NOT filter — the Art 8 universal-base presumption admits all source jurisdictions into the base. The deferred work is the IRNR M210 engine and the Beckham M151 engine: those two surfaces must enforce per-row regulatory scope rules that the CLI cannot enforce alone (the CLI gate stops the most common operator error; the aggregation gate is defence-in-depth against rows that reach the engine through other paths — imports, API surfaces, legacy catalogues, or audit-only foreign-source rows on non-resident profiles).

The two shapes:

- **Option A: Aggregation-time classifier.** Each engine's per-row classifier inspects `transaction.source_jurisdiction` and either emits a base-imponible observation or a typed aggregation issue. The shape mirrors the existing M130 income classifier in `_renta_income_ledger.py` and the existing TRABAJO_INCOME / UNSUPPORTED_DIRECTION issue pattern.

- **Option B: Registry-authored predicate.** A new operator on `KNOWN_VERIFICATION_PREDICATE_OPERATORS` (e.g., `source_jurisdiction_must_equal_es([])`) evaluated at the verification phase, surfacing a finding rather than gating the aggregation. Authoring shape would mirror the recent S376/S377/S378 `implies_nonzero` trio (register, runtime branch, anti-tautology suite).

## Option A — Aggregation-time classifier

Per-engine classifier branch inspects `transaction.source_jurisdiction` and emits one of:

- A base-imponible observation when the row is in scope.
- A typed issue with reason enum (`FOREIGN_SOURCE_OUT_OF_SCOPE` for M210, `BECKHAM_FOREIGN_SOURCE_SEGREGATED` for M151) carrying the transaction id, the original jurisdiction code, and the regulatory anchor.

Pros:

- **Typed payload.** The issue carries the transaction id and the rejected jurisdiction explicitly. An operator inspecting the calculate output sees which row was excluded and why, with the regulatory article cited via the locale string. The S399 IRNR catalogue entries (TRLIRNR Arts 2/10/24/25.1.a/25.1.f) are the citation surface.
- **Provenance-respecting.** Foreign-source rows on a non-resident catalogue are NOT silently dropped — they are emitted as issues and carried through the export pipeline for audit. This matters for the rare legitimate case where a non-resident operator stages a foreign-source row as informational provenance, never as IRNR base.
- **Pattern parity with the existing M130/M100 classifier.** The shape already lives in `_renta_income_ledger.py:_classify_income_transaction`. The S385 provenance pass-through threads `source_jurisdiction` onto `RentaIncomeObservation` using exactly this pattern; the W02 gating extends the same shape to the IRNR and Beckham observations. Implementor builds against a known-good template rather than a new authoring discipline.
- **Loud failure semantics.** If the classifier is wrong (semantic-modelling error), the wrong issue payload surfaces visibly to the operator. The operator can compare the issue against the registry catalogue and the regulatory text and report a defect.
- **Locale-routed messages via tr().** The issue-reason labels follow the established `aggregation.<modelo>.issues.<reason>_label` namespace and are populated via the locale CLI scaffold cycle.

Cons:

- **Per-modelo binding duplication.** Each engine that consumes ledger rows must add the classifier branch. The W02 plan lists M210 and M151 today; a future Beckham informativa or IRNR retención surface would add a third site. The classifier rule is the same shape each time; the duplication is shape-level, not logic-level.
- **No central registry surface.** Authoring teams cannot see the rule by reading the registry; they must read engine code. The cost is modest because the rule has a clear regulatory anchor that lives in the legal catalogue already; the engine-side code is mechanical filter behaviour.

## Option B — Registry-authored predicate

A new predicate operator on `KNOWN_VERIFICATION_PREDICATE_OPERATORS` (e.g., `source_jurisdiction_must_equal_es([])` or `source_jurisdiction_in(["ES"])`) evaluated by `_evaluate_predicate_expression` against the casilla values mapping. The predicate would have to be wired to per-row evaluation rather than the existing casilla-aggregate evaluation, which is a meaningful shape change.

Pros:

- **Centralised registry binding.** The rule is authored declaratively in the registry alongside the article references. A future audit reads the rule from the registry rather than from engine code.
- **Reuse potential.** The same predicate name could in principle be reused across modelos by binding it on different revisions.
- **Symmetry with the recent implies_nonzero / cap_le_when_positive surface.** The S376/S377/S378 authoring pattern is fresh and would be re-applied.

Cons:

- **Silent BLOCKING_RULE refusal shape.** Predicate evaluation produces a finding with a finding_kind such as BLOCKING_RULE. The operator sees "the predicate failed" without per-row context unless the predicate runtime is extended to emit per-row payloads — and once that extension lands, the predicate IS a classifier in shape, just with a different binding surface. The operator does not see which transaction was the offender; they see a registry-level rule-violation.
- **Brittle to DAG-misread incidents.** The S398 rollback (commit c159966df) is the canonical recent example. An `implies_nonzero(["01","07"])` predicate was authored against a misunderstood M131 formula DAG (C07 is `add(C02,C04,C06)`, NOT `add(C01,...)`). A legitimate Khalid-shape EO contribuyente with C01=50000 and the C02/C04/C06 feeders zero would have been falsely refused. The architect-2 review caught it before any operator hit the false-positive, but the failure mode is real and silent: every legitimate filer of that shape would see a refusal with no clue why the predicate fired. A `source_jurisdiction_must_equal_es` predicate carries the same risk: if it lands against a misread of TRLIRNR Art 25 scope (e.g. fails to account for legitimate audit-only foreign-source rows on a non-resident catalogue, or misreads which rentas types are in-scope), every legitimate Spanish-source row OR the legitimate audit rows are refused with the same opaque message.
- **No provenance payload.** Per-row jurisdiction provenance disappears at the predicate boundary. Even if the predicate is fixed later, catalogues evaluated under the wrong predicate carry no record of which rows were rejected and why.
- **New authoring surface required.** Per-row predicate evaluation is not the current shape of `_evaluate_predicate_expression` — predicates today consume `casilla_values: Mapping[str, Decimal]` (aggregated by casilla, not per-row). Wiring per-row evaluation would either (a) add a new evaluation pathway alongside the existing one, or (b) refactor the existing pathway to thread row context, which is wave-sized work outside the W02 scope.

## Tradeoff matrix

| Axis | Option A (classifier) | Option B (predicate) |
|---|---|---|
| Typed payload | Yes — issue carries tx id + jurisdiction code + anchor | No — finding has no per-row context unless predicate runtime is extended |
| Audit-trail shape | Operator-readable issues survive into the export view; provenance preserved | Single BLOCKING_RULE finding; provenance lost at the predicate boundary |
| Failure-mode loudness | Loud and per-row — operator sees which row was excluded and why | Silent and aggregate — operator sees "predicate failed" with no row context. S398 demonstrates the failure mode is real |
| BLOCKING-vs-ADVISORY semantics | Issue-reason-driven (typed enum); could be ADVISORY for audit-only rows and BLOCKING for true scope violations | Predicate finding_kind is a single value per predicate; per-row severity nuance is hard to author |
| Runtime cost | One classifier branch per row, same shape as the existing M130 classifier | One predicate evaluation per casilla, plus the new per-row evaluation pathway |
| Future maintainability | Per-engine branches need touching when the regulatory scope changes; each touch is mechanical and reviewable | Single predicate authored in registry; but every misread of the regulatory text affects every modelo bound to it (the S398 blast-radius lesson) |
| Pattern parity | Mirrors S385 RentaIncomeObservation provenance pass-through and the W12.P65 family of design choices | Mirrors S376/S377/S378 implies_nonzero pattern but with a different evaluation surface |
| Authoring discipline | Implementor writes engine code with a clear regulatory anchor citation | Implementor authors registry rules without the engine-code touchpoint; harder to validate against the calculation engine |

## Recommendation

**Choose Option A — aggregation-time classifier.** Four reasons in priority order:

1. **Loud, per-row failure mode.** The S398 rollback (c159966df) is a concrete recent instance of the predicate-route failure mode. The `implies_nonzero(["01","07"])` predicate landed against a misunderstood M131 DAG and would have silently refused every legitimate Khalid-shape EO contribuyente. Architect-2 caught it before any operator hit it; the catch happened via DAG review, not via the predicate's own diagnostics — the predicate gave the same BLOCKING_RULE finding regardless of whether the rule was right or wrong. The classifier shape would have produced typed issues per-row that an operator could compare against expected behaviour, making the same defect visible to operators (and reportable as a bug) much sooner. For a regulatory gate with high legal blast-radius (refusing a legitimate filing is a real-world harm to the operator), the loud failure mode is the safer default.

2. **Provenance preservation.** The CLI gate already refuses the most common operator errors. The aggregation gate's primary value is defence-in-depth against rows that arrive through other paths — and those paths include legitimate audit-only foreign-source rows on non-resident catalogues. A classifier emits these as typed issues that carry through to the export view for audit; a predicate either accepts the row (wrong) or refuses the calculate (wrong). The classifier is the only shape that handles the legitimate edge case correctly.

3. **Pattern parity with S385.** The S385 provenance pass-through threaded `source_jurisdiction` onto `RentaIncomeObservation` using the classifier shape. Extending the same shape to M210 and M151 means the implementor builds against a known-good template, reviewer reads against a known-good template, and the test-pattern (anti-tautology mutating a row's jurisdiction and asserting filter behaviour) reads against a known-good template. The W12.P65 design choices are explicit in the source-jurisdiction-axis-adr; W02 should not introduce a different shape without a strong reason, and Option B does not present a strong reason that outweighs the pattern parity cost.

4. **Per-modelo duplication cost is small.** The W02 plan lists M210 and M151 today. Both are wave-sized engines (M210 is task #256, M151 needs replacement of the Path-B stub from #161). The classifier branch is a small slice of either engine and follows a mechanical shape; the cost of authoring it twice is dominated by the cost of authoring the surrounding engine. By contrast, the cost of building Option B's per-row predicate evaluation pathway is non-trivial wave-sized work outside the W02 scope.

The Option B predicate route is the right choice when: (a) the rule is genuinely casilla-aggregate rather than per-row (e.g., the existing all_nonzero, any_nonzero, cap_le_when_positive); (b) the rule applies uniformly across many modelos with the same anchor (a true universal rule); (c) per-row provenance is not load-bearing for the operator's audit. None of these conditions hold for the source_jurisdiction case: the rule is per-row, the M210 and M151 bindings are regulatory-distinct (Art 25.1 vs Art 93.5), and per-row provenance is exactly the value the classifier captures.

Architect-2 verdict requested on the W02.P03 question with this memo as substrate; if the verdict is Option A the W02.P01 / W02.P02 Step bodies are authoritative as drafted. If the verdict is Option B the W02 wave needs re-decomposition to add the per-row predicate evaluation pathway as a prerequisite Step.
