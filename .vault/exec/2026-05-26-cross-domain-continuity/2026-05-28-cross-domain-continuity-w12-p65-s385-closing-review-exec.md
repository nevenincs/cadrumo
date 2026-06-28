---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S385
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
  - "[[2026-05-28-source-jurisdiction-axis-research]]"
---

# `cross-domain-continuity` `W12.P65.S385` (closing review)

Closes the audit-trail thread for the canonical W12.P65.S385 plan-Step. The implementation work shipped as S385a (provenance pass-through, commit 0a153a83c, exec record at `2026-05-27-cross-domain-continuity-W12-P65-S385.md`). The architect-2 W02.P03 verdict on the deferred portion (S385b, task #62) was rendered after the implementation record landed and is captured here so a future plan-reader can follow the full audit thread from the original Step decomposition through the deferral and into the M210 Phase 2 plan W02 binding.

## The S385 / S385a / S385b lifecycle

The canonical W12.P65.S385 plan-Step originally scoped three pieces of work that the grounding sweep determined could not all land together:

- **Provenance pass-through at the resident-IRPF aggregation surface** — viable immediately; the M130/M100 income classifier in `_renta_income_ledger.py` exists today.
- **Per-row gating at the IRNR M210 aggregation surface** — not viable; the M210 aggregation engine does not exist yet (#256, currently at the Path-B refusal stub from #196).
- **Per-row gating at the Beckham M151 aggregation surface** — not viable; the M151 aggregation engine does not exist yet (currently at the Path-B refusal stub from #161).

The grounding sweep is recorded in the source-jurisdiction-axis ADR Implementation section under the S385 leaf description. The architect-2 verdict at the time was to descope S385 to the viable portion (the M130/M100 provenance pass-through) and to defer the M210 + M151 portions to a follow-up Step tracked separately. The viable portion shipped at 0a153a83c with the label S385a; the deferred portion received the label S385b and was filed as task #62.

## architect-2 W02.P03 verdict (Option A endorsement)

The deferred S385b work needed a downstream binding. It was placed in the M210 IRNR Phase 2 engine plan as Wave W02, with phases W02.P01 (M210 IRNR base imponible scope filter) and W02.P02 (Beckham M151 IRPF base segregation gate), plus a W02.P03 architecture-decision Step capturing the open question: should the per-row gating land as an aggregation-time classifier (mirroring the S385a / RentaIncomeObservation pattern) or as a registry-authored predicate (mirroring the S376/S377/S378 implies_nonzero authoring pattern)?

The architect-2 W02.P03 verdict came back endorsing Option A (classifier shape). The verdict reasoning aligns with the research memo at `2026-05-28-source-jurisdiction-axis-research.md` (e22dd26c7, frontmatter hygiene at 806326a18): the predicate-route silent-refusal failure mode is concretely demonstrated by the S398 implies_nonzero rollback (c159966df), and the classifier shape's per-row typed-issue audit trail is the safer default for a high legal-blast-radius regulatory gate. The verdict was captured in the S398-repurpose record at d13f125fb.

With Option A endorsed:

- W02.P01 + W02.P02 Step bodies in the M210 IRNR Phase 2 engine plan stand authoritative as drafted (aggregation-time classifier with typed `FOREIGN_SOURCE_OUT_OF_SCOPE` issues for M210 and `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issues for M151).
- W02.P03 closes by the verdict; no re-decomposition of W02 needed.
- W02.P04 (locale strings) and W02.P05 (cross-domain-continuity #62 closure + ADR Consequences update) follow naturally.

## Implementor-Step targets

When the W02 wave lands (blocked on the M210 IRNR engine landing from this plan's W01 + the Beckham M151 engine replacing its Path-B refusal stub), the implementor should:

1. **W02.P01.S01 + W02.P02.S01** — copy the `RentaIncomeObservation.source_jurisdiction` provenance-pass-through pattern from the S385a implementation onto the M210 and M151 observation models.
2. **W02.P01.S02 + W02.P02.S02** — author the per-row classifier branches with typed-issue emission. Anchor citations: TRLIRNR Art 25.1 for M210, LIRPF Art 93.5 for M151.
3. **W02.P01.S03 + W02.P02.S03** — author anti-tautology tests with provenance-mutation kill-the-mutant assertions. Pattern: build catalogue with ES + non-ES rows, assert (a) base sum includes only ES, (b) non-ES row produces typed issue with original jurisdiction preserved, (c) strict-inequality witness against the filter-removed mutant.
4. **W02.P04.S01** — populate `aggregation.irnr.issues.foreign_source_out_of_scope_label` and `aggregation.beckham.issues.foreign_source_segregated_label` across en/es/ca/hu via the locale CLI scaffold cycle.
5. **W02.P05.S01** — close task #62 and append a "Deferral resolved" subsection to the source-jurisdiction-axis-adr Consequences section listing the W02 commit SHAs.

## Why this record exists

A future plan-reader inspecting the W12.P65.S385 implementation record at `2026-05-27-cross-domain-continuity-W12-P65-S385.md` sees that the descope decision was made and that the deferred work moved to task #62 + W02. They do NOT see the architect-2 verdict that closed W02.P03 because that verdict was rendered after the implementation record landed. Without this closing-review record they would have to chase the verdict through the S398-repurpose record, the research memo, and the architect-2 review-cycle artefacts. This record consolidates the audit trail at the canonical S385 plan-Step ID so the implementor can read S385 → S385a (implementation) → S385 closing review (this record) → W02 (deferred work, classifier shape per verdict) without going through the cross-references.

The Step ID S385 carries this record's `step_id` frontmatter. Consistent with the S398 dual-narrative + repurpose precedent: multiple exec records may share a canonical Step ID when they document distinct lifecycles of the same Step. Vault tooling treats them as separate entries per filename; the dedup-on-step_id concern is meta-tracked for a future vault hygiene pass.

## Verification

- The S385a implementation record at `2026-05-27-cross-domain-continuity-W12-P65-S385.md` is intact and unchanged.
- The S385a commit at 0a153a83c is the implementation reference; the deferred work is tracked as task #62 with downstream binding in the M210 IRNR Phase 2 engine plan W02.
- The architect-2 verdict is documented in the S398-repurpose record at d13f125fb.
- The research memo at e22dd26c7 (with frontmatter hygiene at 806326a18) is the decision substrate.

## Gate evidence

- G1 no naked env reads: unchanged; closing-review record only.
- G2 typed pydantic at boundary: N/A.
- G3 user messages via tr(): N/A; vault-doc only.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: pure audit-trail consolidation.
- G6 no tautological tests: no tests touched.

## References

- S385a implementation record: `2026-05-27-cross-domain-continuity-W12-P65-S385.md` (the implementation leaf at 0a153a83c).
- ADR: source-jurisdiction-axis-adr (Implementation §S385, Consequences §S385b deferral).
- Research memo: `2026-05-28-source-jurisdiction-axis-research.md` (Option A endorsement substrate).
- S398-repurpose record: documents the architect-2 W02.P03 verdict that closes the deferred-work decision.
- M210 IRNR Phase 2 engine plan: Wave W02 carries the implementor-Step targets for the deferred S385b work.
- FU task: #62 (deferred S385b per-row gating; blocked on M210 engine + Beckham M151 engine).
