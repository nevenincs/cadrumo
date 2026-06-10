---
tags:
  - '#research'
  - '#llm-evidence-classification'
date: '2026-06-10'
related:
  - "[[2026-06-03-llm-ledger-classification-research]]"
  - "[[2026-06-04-llm-ledger-classification-adr]]"
  - "[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
  - "[[2026-04-17-attachment-service-adr]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
---



# `llm-evidence-classification` research: `Evidence-aware LLM ledger classification (Stage-3): feeding attached evidence into the classifier`

Stage-1 (suggest/apply/reject loop) and Stage-2 (saturate: select `IvaCategory`,
derive rate/base/amount from the registry) of LLM ledger classification have
landed. Both feed the classifier **only the transaction's scalar fields**
(date, amount, currency, counterparty, description). The
`llm-ledger-classification` research already named the open gap (finding F3:
"the classifier prompt is fed only the raw transaction fields — no attached
evidence, receipt, or invoice") and its Implication deferred it to "a separate
legally-grounded decision [to] extend the prompt and feed evidence for base/IVA
separation." This document is that separate decision's research.

The operator's question: can the LLM auto-classification pipeline **read attached
transaction evidence** (a purchase-invoice PDF, receipt image, email, or
Drive/URL document) to automatically (a) propose a transaction split, (b) select
the IVA category, and (c) select the purchase/spending category — turning the
mature-but-unused evidence backend into a classification input. This research
maps the bridge, verifies which providers and CLIs can actually read documents,
and surfaces the architectural fork against the accepted OCR-extraction
discipline.

## Findings

### F1 — Both halves are mature; the bridge between them does not exist

The evidence backend and the LLM classifier are each well-built, and entirely
disconnected.

- **Evidence backend (mature).** `aeat.domain.attachments` defines a typed
  `Attachment` (kinds `INVOICE_PDF`, `RECEIPT_IMAGE`, `EMAIL_MESSAGE`,
  `DRIVE_DOCUMENT`, `CONTRACT_PDF`, `BANK_STATEMENT`, …; sources `LOCAL_FILE`,
  `GMAIL`, `GOOGLE_DRIVE`, `URL`, `INLINE`), content-addressed by SHA-256, stored
  encrypted at `FINANCIAL` sensitivity. `aeat.application.ledger._evidence`
  defines `PurchaseInvoiceEvidence` carrying `media_kind` (PDF/IMAGE),
  `supplier`, `invoice_number`, `taxable_base`, `iva_rate`, `iva_amount` — the
  exact fields an invoice read would populate, **today entered by hand**. A
  transaction carries `purchase_invoice_evidence_id` and `attachment_ids`, with
  immutable `evidence_provenance` lineage. CLI CRUD is complete
  (`evidence add/list/view/update/remove`, plus `attach` and `doclink`).
- **LLM classifier (mature, text-only).** Two stacks: the HTTP SDK adapter
  `aeat.adapters.outbound.llm` (providers `ANTHROPIC`, `OPENAI`, `GEMINI`,
  `LOCAL`) and the subprocess classifiers in `aeat.domain.transactions._llm`
  (`claude`, `agy` for Antigravity, `codex` — the *default* available providers).
  The request shape (`LLMRequest.prompt: str` / `ProviderRequest`) is **text-only**:
  no file, image, document, or base64 content-block field anywhere. The
  classifier renders a text prompt from the transaction's scalar fields and pipes
  it to the provider.
- **The gap.** `attachment_ids` / `purchase_invoice_evidence_id` are persisted on
  the transaction but **never read by the classifier**. No code path passes
  evidence bytes, an evidence file path, or even evidence-derived text into any
  classification prompt. Closing this is the whole of Stage-3.

### F2 — The response schema covers two of the three goals; transaction splitting is the real hole

`LLMClassificationResponse` emits `classification`, `confidence`, `reason`,
`category` (`SpendingCategory`), `iva_category` (`IvaCategory`), and `business_pct`.
Mapped against the operator's three goals:

- **Purchase category — supported.** `category` already selects from the closed
  `SpendingCategory` allow-list, hallucination-guarded by `parse_response`. Only
  the *input* (evidence) is missing.
- **IVA category — supported, numbers stay derived.** Stage-2 added `iva_category`
  selection and derives `iva_rate`/`taxable_base`/`iva_amount` from the registry.
  Evidence-reading slots in as a richer input; it MUST NOT change who emits the
  number (see F7).
- **Transaction splitting — largely absent.** The only "split" the LLM can express
  today is `business_pct`, a single business/personal proportion on one
  transaction. A real invoice-driven split — one receipt with several line items
  at different IVA rates or categories, becoming several child transactions — has
  **no LLM proposal path**. The split primitive itself exists
  (`split_transaction` / `merge_transactions`, CLI `split`/`merge`), but it is
  manual (operator supplies child amounts), and on split the children inherit
  **no** classification and **no** evidence links by design. An evidence-driven
  N-way split is the largest net-new capability and needs its own response schema
  (a list of proposed children, each with amount + category + iva_category +
  evidence citation) plus a new application path that calls `split_transaction`
  from a reviewed suggestion.

### F3 — Provider and CLI document-reading capability matrix (the external unknown)

Verified against current provider documentation (Anthropic PDF-support and
Files-API docs; Gemini and OpenAI docs via Context7, 2026-06-10):

- **Anthropic (Claude API).** All active models (Opus 4.8/4.7/4.6, Sonnet 4.6,
  Haiku 4.5) read PDFs via a `document` content block, sourced as base64, a Files
  API `file_id` (beta `files-api-2025-04-14`), or a URL. Limits: 32 MB request
  payload, 600 pages (100 on the 200k-context Haiku). Each page is processed as
  **both** extracted text (~1,500–3,000 tokens/page) **and** a rasterised image
  (image token cost), so scanned/visual invoices work. Images via an `image`
  block (base64/URL/file_id). No per-PDF surcharge — standard token pricing.
- **Gemini.** PDF up to 50 MB / 1000 pages, inline base64 or File API; 258
  tokens/page; performs OCR on scanned PDFs. Native image input.
- **OpenAI (gpt-5.x).** PDF via Files API `file_id` (`purpose="user_data"`) or
  base64 `input_file` (Responses API) / `file` (Chat Completions). Native image
  (vision) input.
- **Local / Ollama (`LLMProvider.LOCAL`).** Vision-capable local models exist, but
  there is no portable native-PDF path; treat the `LOCAL` provider as text-only
  for evidence — it must take the text-extraction route (F5) or be excluded from
  evidence-reading.
- **Subprocess CLIs — the app's defaults.** The `claude` CLI exposes a `read`
  tool that reads "text, images, **PDFs**" directly from a **file path**; `codex`
  and `agy` similarly read local files. This matters: the default classifiers are
  agentic CLIs, so the simplest bridge for them is to pass the **decrypted
  evidence file path** in the prompt and let the agent read it — no content-block
  plumbing, no base64. This is a materially different (and easier) integration
  than the HTTP SDK content-block path, and the two default surfaces may warrant
  different bridges.

**Implication:** every provider the app supports except `LOCAL` can read PDFs and
images directly; the limiting factor is the app's request schema, not provider
capability. The "which models can read PDFs" unknown the operator flagged
resolves to: *all of them but the local one*, via three different wire shapes
(Anthropic `document` block, Gemini inline/File-API, OpenAI `input_file`) plus
the file-path route for the CLI agents.

### F4 — Architectural fork: LLM multimodal reading vs the accepted OCR-extraction discipline

The accepted `purchase-invoice-ocr-extraction-discipline` ADR governs
operator-uploaded invoice extraction, but it assumes a **deferred deterministic
OCR engine** (Tesseract-family or cloud OCR) producing confidence-gated
structured fields, with seven OCR-specific silent-failure classes, engine-version
pinning, per-field confidence thresholds, and a corpus round-trip discipline that
substitutes confidence-threshold assertions for exact-match. It explicitly
*defers* the engine choice to implementation. LLM multimodal document reading is a
**different extraction technology** that the ADR did not contemplate, and the fork
must be resolved before any plan:

- **Option A — LLM multimodal reading is the extraction engine.** The "OCR engine"
  the discipline deferred is realised as a multimodal LLM call. The discipline's
  confidence-gate and provenance machinery still apply in spirit (a low-confidence
  read must surface, not silently persist a wrong decimal), but its determinism
  assumptions are even weaker than OCR's, so the corpus discipline (assert
  `confidence >= threshold`, never exact strings) transfers directly and arguably
  fits better.
- **Option B — LLM reading complements OCR.** OCR (or text-layer extraction)
  produces the structured numeric fields under the existing gate; the LLM reads
  the same evidence only to *select* category/iva_category and propose splits
  (judgement, not numbers). This keeps the regulated-number path deterministic and
  confines the LLM to what it is allowed to do anyway (F7).
- **Option C — governed-by-ADR.** Evidence reading is folded under the OCR ADR's
  contract wholesale (same error class, same gates), with the LLM as one
  registered "handler".

Option B aligns most cleanly with the existing `llm-selects-system-derives`
constraint (F7) and the Stage-2 design: the LLM never originates the regulated
number, so its read feeding *selection* is low-risk, while numeric extraction —
where a misread decimal is dangerous — stays on the gated deterministic path. The
ADR should rule explicitly on whether evidence reading is a new technology under,
alongside, or outside the OCR discipline.

### F5 — A text-extraction alternative already exists in-tree

The app already ships deterministic text-layer PDF parsing under
`aeat.adapters.inbound` (the declaracion/justificante/borrador parsers built on
`pdfplumber`). For text-native (non-scanned) evidence, extracting the text layer
and injecting it into the **existing text-only prompt** is a low-risk first
increment that needs **no** provider schema change, **no** cache-key change, and
works on every provider including `LOCAL`. It fails on scanned/image-only invoices
(no text layer) — which is exactly where multimodal/OCR earns its place. This
suggests a natural staging: text-extraction injection first (cheap, universal),
multimodal reading second (for scanned/visual evidence and richer layout
understanding).

### F6 — Cache key, persistence, and provenance implications

- **Cache key.** `aeat.adapters.outbound.llm._cache` keys on a SHA-256 of
  `system + prompt` text plus an args hash; it has **no modality dimension**. If
  multimodal content blocks are added (Option A), the cache key MUST incorporate
  the evidence content hash (the `Attachment.sha256` is already a content address
  and is the natural key contribution), or two different evidence inputs under the
  same prompt text will collide. The text-extraction route (F5) needs no change
  because the extracted text lands in the prompt and is hashed already.
- **Persistence / provenance.** An evidence-derived suggestion MUST record which
  evidence it read. The transaction already has `evidence_provenance` and
  `classification_history` with a reserved `provenance` extension point; an
  applied evidence-read classification should stamp `classified_by = llm:<model>`
  and cite the `evidence_id`/`attachment_id` it consulted, so a later audit can
  answer "why is this casilla this value" from the bundled evidence — consistent
  with the ledger-derived-revisions-bundle-evidence discipline.
- **Decryption boundary.** Evidence bytes live encrypted at `FINANCIAL`
  sensitivity. Feeding them to a provider (or writing a temp file for a CLI agent
  to read) crosses a confidentiality boundary to an external service. This is an
  explicit privacy decision the ADR must make: which providers are permitted to
  receive decrypted financial evidence, whether the `LOCAL` provider is the only
  one allowed for unredacted documents, and how the decrypted-temp-file lifecycle
  for the CLI route is bounded. The OCR ADR's `real_operator_invoice_sanitised`
  PII-sanitisation obligation is a direct precedent.

### F7 — The hard constraint: evidence must not let the LLM emit regulated numbers

The Stage-2 ADR's codification candidate `llm-selects-system-derives-tax-numbers`
is binding: an LLM may *select* a registry-grounded category from a guarded
allow-list, but MUST NEVER emit `iva_rate`, `taxable_base`, or `iva_amount` —
those are looked up from the registry and derived arithmetically
(`gross == base + iva` to the cent). Reading an invoice that *prints* "Base 100,
IVA 21, Total 121" is the most tempting place to violate this: it is right there
on the document. The discipline holds regardless — the LLM may read the invoice to
*select* the IVA category and to *propose the split boundaries*, but the euro
figures for the persisted casillas are still derived from the registry rate and
the transaction gross. Evidence-extracted numbers may be used as a **cross-check**
(flag a mismatch between the printed IVA and the registry-derived IVA as an
advisory, per the no-silent-under-declaration discipline), never as the persisted
authority. This is the single most important guardrail for the whole feature.

### F8 — Modern LLMs read documents well across every format the feature needs (capability backed; the OCR-engine fork largely dissolves)

The operator asked whether modern LLMs genuinely read docs, text, PDFs, and
images well enough to lean on them fully rather than building a separate OCR
engine. Verified against current provider documentation, the answer is yes, with
documented caveats:

- **Plain text / text files / extracted text** — trivially handled; this is the
  native modality. The in-tree `pdfplumber` text layer (F5) is one source of such
  text.
- **PDFs (native and scanned)** — first-class on Anthropic (each page processed as
  text *and* a rasterised image, so charts/tables/scans are understood; 600 pages,
  32 MB), Gemini (native vision over the whole document, 1000 pages, OCR on
  scanned, "extract into structured formats… transcribe preserving layouts"), and
  OpenAI (`input_file`). All three explicitly support charts, tables, diagrams,
  and forms — exactly an invoice's content.
- **Images (photos of receipts)** — native vision on all three; Anthropic accepts
  JPEG/PNG/GIF/WebP up to 10 MB / 8000×8000 px, high-resolution (2576 px long
  edge, ~4784 tokens) on Opus 4.7/4.8 and Fable 5, which is "particularly valuable
  for… document analysis".
- **The default CLI agents** read all of these from a file path directly (F3).

The documented **limitations** (Anthropic vision guide) are real but do not block
this use case — they shape the safeguards, which the design already has:
accuracy drops on "low-quality, rotated, or very small images under 200 pixels";
spatial reasoning and precise localisation are weak; object counting is
approximate; and the guidance is explicit — "carefully review and verify… do not
use for tasks requiring perfect precision… without human oversight." Two
mitigations are already in the architecture:

1. **Human-in-the-loop is the precision safeguard the vendors demand.** The
   Stage-1/2 contract is suggest → operator reviews → apply/reject. The LLM never
   silently persists; the operator confirms every classification. This is exactly
   the "human oversight" the limitations section requires, so leaning on the LLM
   for reading + selection is appropriate, not reckless.
2. **The number-derivation rule (F7) is a *legal* guardrail, not a capability
   limit.** "The LLM can accurately read '21,00 €' off the invoice" and "the LLM
   may emit the persisted regulated euro figure" are different questions. Even a
   perfect read does not change F7: the persisted casilla numbers stay
   registry-derived for legal defensibility, and the invoice-printed figure is a
   cross-check advisory. Do not let the verified reading capability erode this —
   capability and permission are orthogonal.

**Conclusion on the fork (F4):** the verified capability resolves the fork toward
**Option A** — lean on the LLM multimodal read as the evidence-extraction engine
rather than building/standing up a separate deterministic OCR engine. The
accepted OCR-discipline ADR's machinery does not vanish; it *re-targets*: its
confidence-surfacing and provenance obligations apply to the LLM read (a
low-confidence or refused read must surface to the operator, never silently
persist), and its corpus discipline (assert behaviour, never exact OCR strings)
fits an LLM read even better than a deterministic engine. The practical caveats
(downsample huge scans to keep small-font text legible; place the document before
the prompt; reject sub-200px crops) become prompt/preprocessing best-practices,
not a reason to defer to OCR. The text-layer route (F5) is retained only as a
cheap fast-path/fallback for clean text-native PDFs and for the text-only `LOCAL`
provider — not as a separate gated stage.

## Open decisions for the ADR

1. **Extraction-technology fork (F4/F8) — leaning Option A (operator steer
   2026-06-10).** Verified LLM document-reading capability resolves the fork
   toward leaning fully on the LLM multimodal read as the evidence engine rather
   than standing up a separate deterministic OCR engine. The ADR ratifies this and
   records how the accepted OCR-discipline ADR re-targets onto the LLM read
   (confidence-surfacing + provenance obligations retained; corpus discipline
   asserts behaviour not exact strings) rather than being superseded.
2. **Bridge shape per surface (F3):** HTTP SDK content-blocks for
   `ANTHROPIC`/`OPENAI`/`GEMINI` vs decrypted-file-path for the `claude`/`agy`/
   `codex` CLI agents — one unified abstraction over two transports.
3. **Splitting scope (F2) — IN SCOPE for Stage-3 (operator steer 2026-06-10).**
   Stage-3 includes evidence-driven N-way splitting: a new response schema (list
   of proposed children with amount + category + iva_category + per-child evidence
   citation) and an application path driving `split_transaction` from a reviewed
   suggestion.
4. **Text-layer fast-path (F5/F8):** is the `pdfplumber` text layer retained as a
   cheap fast-path for clean text-native PDFs and the only path for the text-only
   `LOCAL` provider, with multimodal as the primary engine? (Recommended yes.)
5. **Privacy boundary (F6):** which providers may receive decrypted financial
   evidence; is `LOCAL` the only unredacted path; decrypted-temp-file lifecycle for
   the CLI agents? This is the principal new safety decision the ADR must make.
6. **Cache-key extension (F6):** fold `Attachment.sha256` into the LLM cache key
   for multimodal inputs.
7. **Cross-check vs authority (F7/F8):** confirm evidence-printed IVA numbers are
   an advisory cross-check only, never the persisted value — verified reading
   capability does not relax this legal guardrail.

## Recommended staged path (for the plan, post-ADR)

Per the operator steer (2026-06-10): lean on the LLM multimodal read as the
primary engine, and include splitting in Stage-3.

- **Stage-3a — multimodal evidence reading (primary).** Add a typed multimodal
  content path to `LLMRequest`/the provider adapters for
  `ANTHROPIC`/`GEMINI`/`OPENAI`, and the decrypted-file-path route for the
  `claude`/`agy`/`codex` CLI agents; extend the LLM cache key with the evidence
  content hash. Feed the attached invoice/receipt/image/email directly into the
  suggest/saturate prompts so the model reads the document to select category +
  iva_category. Add the printed-vs-derived IVA cross-check advisory. Surface a
  low-confidence or refused read to the operator rather than persisting silently.
  The `pdfplumber` text layer (F5) is retained as a cheap fast-path for clean
  text-native PDFs and as the only path for the text-only `LOCAL` provider.
- **Stage-3b — evidence-driven N-way splitting.** New response schema (list of
  proposed children, each with amount + category + iva_category + per-child
  evidence citation) and an application path that drives `split_transaction` from
  a reviewed suggestion, preserving the suggest → review → apply/reject contract
  and stamping evidence provenance on each child. The model reads one invoice with
  multiple line items and proposes the child breakdown; the operator reviews and
  applies; child euro figures remain registry-derived per F7.

Throughout, the Stage-1/2 operator contract (suggest previews, `--apply`
persists, manual flags override and re-stamp provenance, reject = do-not-apply),
the human-in-the-loop precision safeguard (F8), and the
`llm-selects-system-derives` constraint (F7) are preserved unchanged.
