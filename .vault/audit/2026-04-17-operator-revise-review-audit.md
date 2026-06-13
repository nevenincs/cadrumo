---
tags:
  - "#audit"
  - "#kent-revise-review"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-17-export-first-roadmap-plan]]"
  - "[[2026-04-13-filing-complementaria-review-audit]]"
---

# kent-revise-review-audit

Companion audit to the `[[2026-04-17-kent-ux-journey-audit|first-file journey audit]]`. Kent has now filed at least once. Three scenarios in this round:

- **A:** Kent discovers a mistake in an *already-filed* return and must revise it.
- **B:** Kent runs the semi-autonomous pipeline and needs to know *what the tool decided vs. what it skipped or guessed*.
- **C:** Some transactions have no rule match, no invoice, no category — they need manual review with attached reasoning, and later may need to be revisited.

Raw facts for this audit: `aeat filing complementaria` exists; `FilingAmendment` + `CasillaChange` + `AmendmentKind` are modelled; `classified_by` distinguishes `auto` / `manual` / `rule:<id>`; a `ResolutionState` state machine (`PENDING` / `AUTO_HEALED` / `HUMAN_APPROVED` / `REJECTED`) exists — *but only* for `DivergenceRecord` inside the AEAT-sync module. There is **no** `confidence`, `requires_review`, `flagged`, `needs_review`, `pending_review`, `low_confidence`, `decided_by`, `decision_method`, `ClassificationDecision`, or `CategoryDecision` anywhere in `src/aeat/`. The only "review" concept that exists (`CasillaRecord.reviewed_by`, `Manual.reviewed_by`) is for corpus authors reviewing the *definitions*, not for Kent reviewing his own filing.

---

## scenario A — Kent amends an already-filed return

It is May 2026. Kent is reconciling last year's filings and notices that his Q4 2025 Modelo 130 missed a €1,200 deductible Seguridad Social payment. The original Modelo 130 was filed in January 2026 — before Kent started using this tool. He has the justificante PDF saved. He wants to file a complementaria.

### what the tool can do today

- `AmendmentKind.COMPLEMENTARIA` and `AmendmentKind.SUSTITUTIVA` are defined (`src/aeat/application/filing/_complementaria.py:30`). Only Modelos 130, 390, and pre-2024Q3 303 are routed.
- `FilingAmendment` is a pydantic frozen record carrying `amendment_id`, `submission_id`, `original_csv`, `original_model`, `original_period`, `amendment_kind`, `delta` (tuple of `CasillaChange`), `amended_draft`, `created_at`.
- `CasillaChange.reason` is a required, non-empty string per changed casilla. This is genuinely good — every delta carries a justification.
- `_validate_complementaria_liability` enforces that a complementaria may **only increase** liability (amended ≥ original), which matches Spanish tax law.
- `aeat filing complementaria build <delta_json>` takes an inline JSON or file with `original_submission_id`, `updated_inputs`, `reasons`. It loads the original draft from local disk (`_load_original_draft`), rebuilds the amended draft via the formula engine, computes the delta, validates, and persists.
- `aeat filing complementaria submit <amendment_id> [--live]` dry-runs by default.

### Kent's actual journey

**Step 1.** Kent runs `aeat submission list`. He sees an empty table. He never submitted *through this tool* — his January filing happened on the AEAT portal directly.

★ **Wall 21 — There is no way to import a previously-filed return that the tool did not originate.** `_load_original_draft` scans `var/drafts/` looking for `draft_id`. If the draft never existed in the tool, there is nothing to load. There is no `aeat filing import --from-justificante <pdf>` that reconstructs a `FilingDraft` from the PDF justificante, and there is no command that ingests casilla values from a user-provided spreadsheet to create a retroactive baseline.

**Step 2.** Kent tries to reconstruct. He runs `aeat justificante parse Q4-2025-modelo-130.pdf`. He gets back `modelo`, `period`, `csv`, `amount`, `presented_at`, `verification_url` — metadata only, no casilla-by-casilla values. The justificante PDF does not carry line items, and the parser does not attempt to extract them.

★ **Wall 22 — Justificante PDFs do not surface casilla values to the amendment engine.** This might not be achievable from the PDF itself (AEAT justificantes are a legal receipt, not a full filing record), but there is also no alternative path.

**Step 3.** Kent tries to pull from AEAT directly. `aeat status expedientes` — exit 2, blocked on #8. Even if it worked, `fetch_expedientes()` returns an `Expediente` record with `status`, `presented_at`, `csv`, `justificante_url` — still no line items. No method on `StatusReader` fetches per-casilla values for a previously filed return.

★ **Wall 23 — Even when live AEAT reads work, there is no surface that fetches previously-filed casilla values.** For amendments to be usable at scale, the tool must be able to read what it is amending. This is a missing `StatusReader.fetch_filing_detail(modelo, period)` (or equivalent portal scrape) — the entire amendment flow is load-bearing on it.

**Step 4.** Kent falls back to hand-authoring. He writes a JSON file with the original casilla values (reading them off his retained filing worksheet) and pretends the tool originated it. He then writes a second JSON with the `updated_inputs` — the one changed casilla — plus a `_reasons` map. He runs `aeat filing complementaria build 130 2025Q4 delta.json`.

★ **Wall 24 — The complementaria build command is a pure-JSON pass-through with no wizard.** Kent must know the casilla codes of the delta, the correct format for `_reasons`, and the right shape of `updated_inputs`. An interactive wizard that walks "what changed? by how much? why?" does not exist.

**Step 5.** Amendment builds. `aeat filing complementaria submit <amendment_id>` dry-runs successfully. Under the export-first charter (#197), `submit` is hidden and deferred to 1.0.0.

★ **Wall 25 — The export-first C3 EPIC does not cover amendment export.** An export path for amendments — producing an AEAT-importable amendment file Kent can upload himself — is not in scope anywhere. The charter promises Kent a file he can upload; it forgets to promise him an amendment file.

**Step 6.** Suppose Kent had been filing Modelo 303 post-2024Q3 instead. `_resolve_amendment_kind` (`_complementaria.py:202`) raises `FilingAmendmentValidationError` immediately: *"modelo 303 period 2024Q3 uses autoliquidacion rectificativa, not complementaria"*.

★ **Wall 26 — Autoliquidación rectificativa (Modelo 303 Q3 2024 onwards) is explicitly rejected with no implementation path.** Every Modelo 303 filing after Q3 2024 — which is *every current 303* — cannot be amended through this tool. This is the correction most autónomos do multiple times per year.

**Step 7.** Suppose Kent's error was on Modelo 111 (retenciones) or Modelo 347 (operaciones con terceros). `_resolve_amendment_kind` raises `unsupported amendment modelo 111`.

★ **Wall 27 — Only three modelos (130, 390, pre-2024Q3 303) have amendment support.** The other 18 modelos in the registry cannot be amended at all.

### scenario A gaps in one line each

21. No retroactive import of returns not originated in the tool.
22. Justificante PDFs do not yield casilla values for amendment diffs.
23. No `StatusReader` surface fetches previously-filed casilla values from AEAT.
24. `aeat filing complementaria build` is a raw-JSON pass-through; no wizard.
25. The export-first charter does not cover amendment export.
26. Rectificativa (the current Modelo 303 amendment mechanism) is rejected, not implemented.
27. Only three of twenty-one modelos have any amendment flow at all.

---

## scenario B — Kent inspects what the semi-autonomous pipeline decided

It is early April 2026. Kent has run `aeat financial ingest` through `aeat financial aggregate` (in this audit we assume D11–D13 have landed and T1→T6 works). The tool reports the draft is ready. Kent wants to know: *what did you actually do?*

### what the tool can do today

- Every `Transaction` record carries `classified_by` ∈ {`"auto"`, `"manual"`, `"rule:<rule-id>"`} and `classified_at`. Good — Kent can sort by decision method.
- Every `LedgerEntry` (a casilla derivation step) carries `op`, `formula_id`, `operand_refs`, `operand_values`. Full formula-trace per casilla.
- Every `FilingDraft` carries `findings: tuple[FilingValidationFinding, ...]` with severity (ERROR / WARNING / INFO), a stable machine code, a trilingual message, and references to Manual rules.
- `WorkflowResult` carries `aborted_reason: WorkflowAbortReason | None` — a closed enum naming why the workflow stopped (e.g. `INBOX_BLOCKING_REQUERIMIENTO`).
- `DivergenceRecord` with `ResolutionState.PENDING` and a CLI (`aeat sync list-divergences --state pending`) **is** a review queue — but only for AEAT-vs-local sync divergences.

### what the tool cannot do

- No `confidence` field on any `Transaction`, `CasillaChange`, `LedgerEntry`, or derivation record.
- No `requires_review` / `flagged` / `low_confidence` / `needs_attention` flag on any data record.
- No `ClassificationDecision` / `CategoryDecision` / `AggregationDecision` named type that records *decided_by* + *decided_at* + *method* (rule-match / LLM / manual / fallback) + *confidence* + *reason* as a first-class audit object.
- No `FilingValidationFinding` surface at earlier pipeline stages: findings live on drafts only. There is no "findings for the catalogue," "findings for invoices," "findings for this quarter's categorisation pass."
- No distinction between **"UNCLASSIFIED because not yet processed"** and **"UNCLASSIFIED because the pipeline saw this row and could not decide"**. Both collapse into the same enum value.
- No unified review queue across transactions / invoices / categorisations / drafts. `aeat sync list-divergences` is the only real queue and it is scoped to remote-sync only.

### Kent's actual journey

**Step 1.** Kent runs `aeat financial txs list --unclassified`. He sees 49 rows. He does not know whether they are (a) rows the pipeline has not touched yet, (b) rows the pipeline tried and could not classify, (c) rows that failed validation, or (d) rows the pipeline deliberately skipped because they looked like transfers/personal.

★ **Wall 28 — `UNCLASSIFIED` conflates four distinct pipeline states.** Kent cannot distinguish "new" from "couldn't decide" from "deliberately skipped."

**Step 2.** Kent wants to see "rows the pipeline is not confident about." The tool has no confidence field. He cannot sort, filter, or surface low-confidence classifications.

★ **Wall 29 — No confidence scoring exists anywhere.** Classifications are binary: classified or not. A rule-match with two weak signals looks identical to a rule-match with one strong signal. The LLM path (when it lands) will have to invent its own confidence outside the record.

**Step 3.** Kent wants to see "rows the pipeline wants me to review." There is no flag. He cannot `aeat financial txs list --needs-review`.

★ **Wall 30 — There is no structured "needs review" signal on transactions, invoices, or attachments.** The closest concept is `DivergenceRecord.resolution_state`, which is for AEAT-vs-local sync only.

**Step 4.** Kent runs `aeat filing show draft.json --findings-only`. He sees three warnings on casilla 07 and casilla 12. Good — but these are draft-level findings. He wants to know which *transactions* contributed to those findings. There is no link.

★ **Wall 31 — Findings live on drafts only; no per-transaction or per-catalogue findings surface.** The pipeline can say "casilla 07 looks wrong" but not "transaction `abc123` contributed anomalously to casilla 07 because it was auto-classified BUSINESS despite matching a PERSONAL keyword."

**Step 5.** Kent wants a unified pipeline health view: "show me everything across the pipeline that needs my attention." There is no such command. He would have to run `aeat financial txs list --unclassified`, `aeat financial invoices unmatched`, `aeat financial invoices verify`, `aeat sync list-divergences --state pending`, `aeat filing show --findings-only`, and `aeat inbox next-deadline` — and mentally join the results.

★ **Wall 32 — No unified "pipeline review queue" dashboard.** Six commands × six output formats × no cross-reference ≠ a dashboard.

**Step 6.** Kent wonders what the pipeline did yesterday. `aeat workflow list` shows past runs with `aborted_reason`. Good at the run level. But he cannot ask "what rules fired today vs. yesterday?" or "which transactions had their classification change?" — there is no classification-change history.

★ **Wall 33 — Classification decisions are not versioned.** `Transaction.classified_at` is a single timestamp; if Kent re-classifies a transaction, the previous decision is lost. No `ClassificationHistory` record.

### scenario B gaps in one line each

28. `UNCLASSIFIED` conflates not-yet-seen / could-not-decide / skipped-intentionally.
29. No confidence scoring anywhere in the pipeline.
30. No `requires_review` flag on transactions, invoices, or attachments.
31. Findings exist only on drafts; no per-catalogue / per-transaction findings surface.
32. No unified review queue / pipeline health dashboard.
33. Classification decisions are not versioned.

---

## scenario C — Kent manually reviews, classifies, and notes

Kent works through his 49 UNCLASSIFIED rows. One is a Wise payment to `"Digital Ocean"` for €42 — professional cloud hosting, but the tool does not know his Digital Ocean droplet exists. He wants to classify it MIXED at 80% business with a one-line reason ("hosting for client X's demo site, 80% billed").

### what the tool can do today

- `aeat financial txs classify <id> --as MIXED --pct 0.8` works. The transaction's `business_classification` becomes `MIXED`, `business_pct` becomes `Decimal("0.8")`, `classified_by` becomes `"manual"`, `classified_at` gets a timestamp.
- `Transaction.notes: str` field exists — free-text, empty by default.

### what the tool cannot do

- `aeat financial txs classify` has **no `--notes` flag**. Kent cannot attach a reason via CLI. (This is confirmed: `--notes` exists on `aeat attachments` and `aeat sync resolve` but NOT on `aeat financial txs classify`.)
- No structured reason model: `notes` is an unstructured string. A future LLM summariser, a search tool, or a downstream classifier cannot extract intent from it.
- No way to link a manual classification decision to a reference attachment (PDF receipt, contract excerpt). The `attachments` module exists and can link a PDF to a transaction, but the classification decision does not reference the attachment.
- No "reviewed and intentionally excluded" state. If Kent looks at a row and decides "this is not a business transaction and should be invisible to the draft," his only mechanism is to leave it UNCLASSIFIED — which will re-surface in every `--unclassified` query forever. There is no `BusinessClassification.REVIEWED_EXCLUDED` or `excluded_reason`.
- `reviewed_by` / `reviewed_at` concepts exist twice in the codebase (`CasillaRecord`, `Manual`) but both refer to *developers reviewing the corpus definitions* — they are not available for Kent to sign off on his filing.

### Kent's actual journey

**Step 1.** Kent runs `aeat financial txs classify tx-abc123 --as MIXED --pct 0.8`. Succeeds. No reason captured.

★ **Wall 34 — `aeat financial txs classify` has no `--notes` / `--reason` flag.** Kent must edit JSON or write Python to record why he decided MIXED @ 80%.

**Step 2.** Kent has a Personal-looking Wise FX fee of €2.31. He decides it is *out of scope* — it should not even appear in his business draft. His options: (a) classify as PERSONAL (but then the tool still tracks it and totals for "personal expenses" grow), or (b) leave UNCLASSIFIED (and it re-surfaces forever).

★ **Wall 35 — No "reviewed and intentionally excluded" state.** The `BusinessClassification` enum forces a false binary: either you classify it or you ignore it, but "ignore it" has the same representation as "haven't looked at it." Kent cannot assert "I saw this, it is not relevant, stop asking me."

**Step 3.** Kent wants to attach a PDF receipt to a transaction as evidence. `aeat attachments link <tx-id> <file>` works — but the attachment links to the transaction generally, not to the classification decision. If Kent later re-classifies, the attachment remains associated with the transaction but there is no audit record saying "attachment XYZ was the evidence used for the MIXED@80% classification on date D."

★ **Wall 36 — Attachments attach to transactions, not to decisions.** There is no evidence trail per classification / re-classification.

**Step 4.** Later, in May 2026, Kent is preparing Q1 amendments. He wants to see *every transaction he personally classified this year*, with the reasons. He runs… there is no command. He could grep the catalogue JSON for `classified_by: "manual"` but there is no CLI surface.

★ **Wall 37 — No "my review history" view.** Decisions are made; no command surfaces them as an audit trail.

**Step 5.** Kent re-classifies tx-abc123 from MIXED@80% to MIXED@60% (he realises the client-work ratio was lower). `classified_at` overwrites. `classified_by` stays `"manual"`. The previous decision is lost. The free-text `notes` field may or may not have been updated — either way, the history is gone.

★ **Wall 38 — Re-classification overwrites rather than versions.** No `ClassificationHistory` chain. Kent cannot answer "did I ever classify this as BUSINESS at 100% and then change my mind?"

**Step 6.** Kent approves his Q1 draft. Two days later he runs `aeat financial ingest` on a late-arriving bank statement. Three new transactions land in the catalogue and get rule-classified BUSINESS. His existing Q1 draft is NOT marked stale. No command tells him "your approved draft is now out of date because the underlying catalogue changed."

★ **Wall 39 — No draft staleness detection.** This is a direct mirror of the export-first ADR's C4f sub-issue ("detect stale approval") — worth re-emphasising: the absence is not theoretical; it bites on the real amendment-season flow.

★ **Wall 40 — Corpus-author `reviewed_by` shadows user-filing `reviewed_by`.** `CasillaRecord.reviewed_by` and `Manual.reviewed_by` record developer review of definitions. A naive reader would assume these fields mean "Kent reviewed his filing," and the shadowing risks real confusion when a proper Kent-review concept lands.

### scenario C gaps in one line each

34. `aeat financial txs classify` has no `--notes` / `--reason` flag.
35. No "reviewed and intentionally excluded" transaction state.
36. Attachments link to transactions, not to decisions.
37. No "my classification history" CLI surface.
38. Re-classification overwrites history rather than versioning it.
39. No staleness detection on approved drafts when the catalogue changes.
40. Corpus `reviewed_by` shadows the missing user-filing `reviewed_by` concept.

---

## the walls, synthesised

This audit adds **20 new walls** (21–40) to Kent's original 20. They cluster into four themes:

- **Amendment (21–27):** The amendment engine is architecturally sound for drafts it originated, legally correct on the liability-increase check, and useless for the common case of revising a return the tool did not originate. Rectificativa is rejected outright. Seventy-five percent of the modelos in the registry cannot be amended at all.
- **Pipeline observability (28–33):** The pipeline is more autonomous than its introspection surface. `UNCLASSIFIED` conflates four states. There is no confidence, no flag, no needs-review queue, no per-transaction findings, no classification history. Kent has to reverse-engineer what happened from the bare catalogue.
- **Structured review and evidence (34–38):** `--notes` is missing from the one CLI command a user runs most. Decisions are not first-class records. Attachments link to transactions, not to the decision the attachment justifies. Re-classifying overwrites.
- **Staleness and shadowing (39–40):** Drafts do not detect catalogue churn after approval. The existing `reviewed_by` concept is about corpus authors, not Kent, and the shadowing is a latent footgun.

The single highest-leverage gap is **wall 23** — no surface fetches previously-filed casilla values from AEAT. It is the load-bearing dependency for every amendment use case that matters. Second-highest is **wall 29** — the absence of confidence — because a pipeline without confidence cannot honestly tell Kent what to review.

## what the tool does well (worth preserving)

- `CasillaChange.reason` being *required* is good. Keep that pattern — every structured decision record should have a required, non-empty reason.
- `classified_by` with the restricted shape `"auto"` / `"manual"` / `"rule:<rule-id>"` is a strong provenance primitive. Generalise it: `decided_by` on every decision record should use this same shape plus `"llm:<model-id>"` and `"fallback"`.
- `DivergenceRecord` + `ResolutionState` + `aeat sync list-divergences` is a working review queue for the sync domain. It is the template to generalise across catalogue / invoices / classifications / drafts.
- `FilingValidationFinding` with severity / code / trilingual message / rule references is an excellent findings model. Port it to non-draft records.
- The complementaria liability-increase validator is a correct, legally-grounded check. Keep the pattern — every amendment path should have an analogous domain-specific assertion.

## roadmap implications for the export-first charter

This audit adds new work to the export-first charter (#197) and to Batch 2. Recommendation:

- **Expand C4 (review EPIC)** to explicitly include: a unified review queue, `decided_by` / `decision_method` / `confidence` / `reason` on every decision record, a `--notes` flag on `aeat financial txs classify`, staleness detection, a new `BusinessClassification.REVIEWED_EXCLUDED` state.
- **Add a new EPIC C13** — `aeat revise`: retroactive-filing import, justificante-to-draft partial reconstruction, amendment wizard, amendment export, rectificativa support, per-modelo amendment kinds beyond 130/390/303.
- **Add a new EPIC C14** — pipeline observability: `ClassificationDecision` record type, confidence scoring, unified "needs review" queue, per-catalogue findings surface, classification-history versioning.
- **Escalate wall 23 (fetch previously-filed casilla values)** to milestone 0.1.0-pre-alpha. Without it, amendments remain a toy.

## verdict

Kent can use the first-file pipeline (once the 20 first-audit walls are closed) to produce, review, and export a new Modelo 130. He cannot meaningfully revise one. He cannot meaningfully audit what the pipeline decided on his behalf. He cannot record *why* he disagreed with the pipeline when he overrode a classification. The infrastructure for each of these features exists in fragments — `CasillaChange.reason`, `classified_by`, `DivergenceRecord`'s resolution state machine, `FilingValidationFinding` — but none is generalised beyond its originating subsystem. The export-first charter correctly pulls live filing out of the near-term path, but it does not yet contain the revise/review work that turns an export from "a file" into "a file Kent can stand behind."
