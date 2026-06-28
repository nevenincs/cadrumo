---
tags:
  - '#audit'
  - '#source-jurisdiction-axis'
date: '2026-05-28'
modified: '2026-05-28'
related: []
---



# `source-jurisdiction-axis` audit: `campaign summary`

Closing narrative audit document for the source_jurisdiction axis end-to-end campaign. The axis closed structurally in a single session under the cross-domain-continuity L4 epic and is now in production for all `aeat app ledger add` invocations. This document consolidates the audit trail for future auditors, captures the architectural decisions for future authors, and banks the process-rule lessons learned for the team-shared knowledge base.

## Campaign overview

The source_jurisdiction axis arose from four testimonial-persona discovery interviews under the cross-domain-continuity epic. Pedro (intra-community supplier) needed jurisdiction provenance on EU-counterparty invoices for the M349 row mechanism. Olivia (UK landlord moving residence between IRPF and IRNR) needed the axis at the boundary between resident-IRPF (Art. 8 universal-base) and non-resident-IRNR (Art. 25 Spanish-source scope). Felipe (Argentina-resident pensioner under TRLIRNR Art. 25.1.b) needed it for the IRNR base scope filter on non-EU/EEA residents. Khadija (Morocco-resident worker under the España-Marruecos convenio) needed it for the convenio-rate selection on third-country income.

None of the four personas could file correctly without per-row source-jurisdiction provenance. The cross-domain-continuity audit and the prior persona testimonials supplied the research substrate; the campaign substituted those for a formal research document per the L4 epic's open-ended persona-driven discovery posture.

Campaign scale this session: 13 implementation commits across 6 plan-Steps, 1 ADR, 1 research memo, 1 audit document (this one), 17 exec records, 3 plan amendments, plus the auto-generated feature index. The axis ships end-to-end through `Transaction` domain field, encrypted persistence boundary, CLI flag, profile-conditional resolver, write-side wiring, read-projection threading, and aggregation-time provenance pass-through.

## Commit chain

Grouped by canonical plan-Step ID:

- S381 (`b7c571297`) — Transaction domain field + LedgerTransactionPayload + LedgerTransactionReviewPayload + LedgerExportRow read-projection field, with the 2-character alpha-uppercase validator and grandfather-friendly None default.
- S382 (`40f3837b8`) — encrypted-envelope roundtrip + anti-tautology grandfather-contract proof test.
- S383 (`d75202aab` + `5cbd8e1c4`) — CLI `--source-jurisdiction` flag + ManualLedgerTransactionCommand and ManualLedgerTransactionPatch wiring + write-side closure through `_transaction_from_command` + locale strings via the locale CLI scaffold cycle.
- S384 (`c6e402eb3` + `5a7601f89` + four patch commits `ef3562e64` / `3f7427714` / `f6c8d1028` / `3802591f6`) — profile-conditional `_resolve_source_jurisdiction` helper + four CLI truth-table tests + locale refusal keys. The four patches addressed read-projection wiring, descriptor key path, IRNR axis tuple, and the UE-country workaround for the schema-catalogue mismatch on `representante_fiscal_nombre`.
- S385a (`0a153a83c`) — aggregation provenance pass-through onto RentaIncomeObservation in the M130/M100 resident-IRPF surface, with two anti-tautology tests proving Art. 8 universal-base mixing of ES + foreign-source rows.
- S386 (`2a9385f4d` + `27770c166`) — consolidating ADR + frontmatter hygiene wiring related: wiki-links.
- S385b deferred — tracked as task #62, downstream binding in the M210 IRNR Phase 2 engine plan Wave W02. Blocker chain: this plan W01 IRNR engine + Beckham M151 engine post-Path-B-stub.
- Plan amendments — W02 scoping note appended to the M210 IRNR Phase 2 engine plan (absorbed in `602b0cdfb`); architect-2 W02.P03 verdict captured via S398 slot repurpose + research-memo hygiene (`806326a18`).
- Index auto-generated (`b5f26fbaf`) via `vault feature index`.
- Retro exec records across `6efa1fc27` (10 records — S376/S377/S378 + S381-S386 + S399), `ee25c50b4` (4 records — S386b hygiene + S387 + S387.patch + S398 dual-narrative), `d13f125fb` (S398 repurpose), `281ceb607` (S385 closing review), and this audit document.

## Architectural decisions

Three load-bearing architectural decisions emerged from the campaign and are documented in the source-jurisdiction-axis ADR:

**CLI-create-boundary gating over aggregation-boundary gating.** The profile-conditional default and refusal logic could have lived on the per-modelo aggregation surfaces. It lives instead at the CLI create surface, in a single helper called before the persistence-bound command is constructed. Three reasons: the error surfaces before the row reaches the encrypted catalogue; the refusal is operator-facing prose routed through tr() rather than a deferred per-modelo issue; single-point-of-enforcement vs N-fold per-modelo duplication. The CLI gate is the most common operator's protection; the aggregation gates that S385b will eventually add are defence-in-depth.

**Classifier shape over predicate shape for deferred S385b per-row gating.** The architect-2 W02.P03 verdict endorsed the classifier route. Reasons banked in the classifier-vs-predicate research memo: per-row typed-issue payload preserves provenance; pattern parity with the S385a RentaIncomeObservation wiring; loud failure mode where operators can read the rejected row's jurisdiction. The contrary instance is the S398 rollback — the M131 implies_nonzero predicate landed against a misunderstood formula DAG and would have silently refused legitimate Khalid-shape EO contribuyentes. The classifier shape's per-row typed issues would have made the same defect visible to operators, not just to architecture reviewers.

**Provenance-respecting filter (not silent-drop).** When the future S385b lands the IRNR and Beckham aggregation gates, foreign-source rows are NOT silently dropped from the catalogue read — they are emitted as typed `FOREIGN_SOURCE_OUT_OF_SCOPE` (M210) or `BECKHAM_FOREIGN_SOURCE_SEGREGATED` (M151) issues that carry the transaction id and jurisdiction code through to the export view for audit. This matters for the rare legitimate case where a non-resident catalogue stages a foreign-source row as informational provenance.

## Deferred work

Three follow-up tasks remain open at session close:

- **Task #62** — S385b IRNR/Beckham per-row gating. Bound downstream in the M210 IRNR Phase 2 engine plan Wave W02 (5 phases, 11 unchecked Steps). Implementor-Step checklist banked in the S385 closing-review record. Blocked on the M210 IRNR full engine (task #256) + the Beckham M151 engine replacing its Path-B refusal stub.
- **Task #60** — renta_taxpayer wizard-only policy. Surfaced by architect-2 during the S388 review cycle; out of scope for the source_jurisdiction axis but adjacent enough to warrant a tracked follow-up.
- **Task #61** — unused schema entries triage. The `representante_fiscal_nombre` schema gap discovered during the S384 patch3 cycle is one instance; a broader sweep may surface others. The S384.patch4 UE-country workaround is the holding pattern until #61 resolves.

## Lessons banked

Five process-rule candidate lessons emerged from the campaign and are flagged for promotion to the team-shared knowledge base:

**DAG-correctness must precede predicate authoring.** The S398 implies_nonzero rollback (`c159966df`) is the canonical instance. The author read the regulatory text "cuando C01 sea positivo" and bound a predicate against M131 without verifying the actual formula DAG. The DAG defines `C07 = add(C02, C04, C06)` — C01 is not a summand. A legitimate operator with C01 positive and the actual feeders zero would have been silently refused. The architecture-review pass caught it; the predicate's own diagnostics would have shown the same opaque BLOCKING_RULE finding regardless of whether the rule was right or wrong. Process-rule candidate: every predicate authoring must explicitly cite the formula DAG section it is bound against, and the architect-review checklist must verify the predicate's antecedent-and-consequent identifiers match the DAG.

**Architect briefs must verify precedent matches data shape, not just parameter family.** Surfaced by coder1-2 during the S388 bracket_table review. A "use the M100 bracket_table parameter" brief is ambiguous when M100 carries multiple bracket-table parameter families with different shapes. The architect must specify the exact precedent file path so the implementor builds against the right shape. Process-rule candidate: architect briefs should include the verbatim file path of the canonical-precedent parameter file the implementor should mirror.

**PM dispatch briefs must read plan-body action statements verbatim, not paraphrase from memory.** Three distinct PM dispatch confusions surfaced this session on the M210 chain. Two were on the PM side (conflating S388 and S389); the third was the S400 planning gap that architect-2 caught via plan-body inspection. Process-rule candidate: PM dispatch briefs quote the Step's action statement verbatim from the plan body, and the implementor's first action on receiving the brief is to confirm the quoted statement matches the current plan body.

**Vault-doc authoring requires grounding against actual code state, not assumed implementation.** The pre-session fabricated-records incident (9 untracked exec records with hallucinated `SourceJurisdiction` enum content and wrong phase IDs) demonstrated the failure mode. Recovery required deletion of all 9 records and re-authoring grounded against actual file state. Process-rule candidate: every vault-doc claim about code (file path, class shape, function signature, enum variant) must be verified against the current tree via Read/Grep before the doc commits. The retro-authoring batch following the incident applied this discipline and the records sample clean.

**Explicit-pathspec on every commit in shared worktrees.** The WIP-absorption incident at `602b0cdfb` showed how `git commit -m "msg"` without an explicit pathspec absorbs the entire staged index, including peer-agent in-flight work. Net effect that time was benign because the absorbed WIP was the most useful in-flight piece, but the absorption was unintentional and reproduces the pattern in memory rule `explicit_path_staging_in_parallel_worktree`. Process-rule candidate (reaffirmed): every commit in this shared worktree MUST use `git commit -m "msg" -- <explicit-pathspec>` form.

## Closing assessment

The persona-driven open-ended posture under the cross-domain-continuity L4 epic produced a complete TIER 1 axis end-to-end in a single session. The full chain — domain model field → strict-pydantic boundary → encrypted persistence with grandfather contract → CLI flag with profile-conditional gating → aggregation-time provenance — landed under continuous audit-record cadence and survived 4 architect-review cycles plus 1 successful predicate rollback when the architect caught a structural defect post-landing.

The campaign demonstrates that the posture works when three conditions hold: (a) fresh-context implementors are available for the next-Step cycles; (b) the architecture-review loop is tight enough to catch structural defects before they ship downstream (the S398 catch was within hours of the predicate landing); (c) the audit-record discipline is sustained throughout, not deferred to a closure pass that becomes the next session's tech-debt.

Commit-velocity summary for the session window:

- 17 commits attributed to this campaign (S381 through S386 chain + retros + plan amendments + index gen + audit doc).
- 17 exec records authored covering every code / ADR / hygiene / plan-edit / closing-review commit shipped under the campaign.
- 1 consolidating ADR (source-jurisdiction-axis).
- 1 research memo (classifier-vs-predicate, with the W02.P03 verdict substrate).
- 1 audit document (this one).
- 1 W02 plan-wave amendment scoping the deferred per-row gating.
- 1 S400 plan-Step insertion closing a planning gap surfaced by architect-2.
- 1 S398 plan-Step repurpose from the rolled-back predicate to the FU-#226 corpus-blocker tracker.
- 1 auto-generated feature index emitted via `vault feature index`.

Around forty distinct documented improvements in the session window. The throughput is itself a positive-control signal for the open-ended persona-driven posture and is banked as a baseline for future campaigns operating under the same epic.
