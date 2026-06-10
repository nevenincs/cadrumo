---
tags:
  - '#adr'
  - '#llm-evidence-classification'
date: '2026-06-10'
related:
  - "[[2026-06-10-llm-evidence-classification-research]]"
  - "[[2026-06-04-llm-ledger-classification-adr]]"
  - "[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
  - "[[2026-04-17-attachment-service-adr]]"
---



# `llm-evidence-classification` adr: `Evidence-aware LLM ledger classification (Stage-3): lean on the LLM multimodal read; splitting in scope` | (**status:** `accepted`)

## Problem Statement

LLM ledger classification landed in two stages: Stage-1 wired the classifier into
an operator suggest/apply/reject loop (business/personal + spending category), and
Stage-2 (saturate) added `IvaCategory` selection with registry-derived
rate/base/amount. Both feed the classifier **only the transaction's scalar
fields** — date, amount, currency, counterparty, description. The transaction
already carries `purchase_invoice_evidence_id` and `attachment_ids`, the evidence
backend is mature (typed `Attachment` and `PurchaseInvoiceEvidence`, encrypted at
`FINANCIAL` sensitivity, full CLI CRUD), yet **no classification path ever reads
that evidence**. Classification is therefore blind to the single richest signal an
operator has — the purchase invoice or receipt itself.

Stage-3 closes that gap: feed the attached evidence (purchase-invoice PDF, receipt
image, email, Drive/URL document) into the classify/saturate pipeline so the model
reads the document to (a) select the spending category, (b) select the IVA
category, and (c) propose an N-way split of one transaction into several children
(e.g. an invoice whose lines carry different categories or IVA rates). The
research established that modern LLMs read all the required formats well, and the
operator directed two decisions this ADR ratifies: lean fully on the LLM
multimodal read rather than standing up a separate OCR engine, and include
evidence-driven splitting in Stage-3.

## Considerations

- **The two production surfaces are asymmetric.** The application classify surface
  has its own `LLMProvider` StrEnum scoped to the subprocess CLIs
  (`claude` / `antigravity` / `codex`, probed on `PATH`), and `resolve_classifier`
  builds a `SubprocessLLMClassifier` for each. The HTTP-SDK adapter under
  `aeat.adapters.outbound.llm` carries its own separate `LLMProvider`
  (ANTHROPIC / OPENAI / GEMINI / LOCAL) but **is not wired into the classify
  path** today. So the production evidence-reading bridge is, first and foremost,
  about the subprocess CLI agents — which read a PDF/image/text file **directly
  from a file path** via their `read` tool. That is the lowest-friction transport
  and the one to build first.
- **Verified document-reading capability.** All non-local providers read native
  and scanned PDFs, images, and text with structured-extraction quality; the CLI
  agents read all of these from a path. The documented vision limitations
  (low-quality / rotated / sub-200px text, approximate counting, "use human
  oversight for high-stakes") are real but are already mitigated by the existing
  suggest → review → apply/reject contract.
- **The regulated-number rule is non-negotiable and orthogonal to capability.**
  The Stage-2 `llm-selects-system-derives-tax-numbers` discipline holds: the LLM
  may select `iva_category` from the registry-grounded allow-list, but the
  persisted `iva_rate` / `taxable_base` / `iva_amount` are derived from the
  registry rate and the transaction gross. An invoice printing "Base 100, IVA 21"
  is the most tempting place to break this; the printed figure is an advisory
  cross-check only.
- **Evidence is encrypted at `FINANCIAL` sensitivity.** Feeding it to a provider
  (base64 over HTTP) or writing it to a temp file for a CLI agent crosses a
  confidentiality boundary to an external service. This is a new safety decision,
  not present in Stage-1/2 which only ever sent scalar transaction fields.
- **Splitting today is manual and 2-way.** `split_transaction` exists but takes
  operator-supplied child amounts; the LLM can only express a single
  `business_pct`. Evidence-driven N-way splitting is genuinely new surface.
- **An accepted ADR governs invoice extraction.** The
  `purchase-invoice-ocr-extraction-discipline` ADR assumed a deferred deterministic
  OCR engine. This ADR resolves that deferral by choosing the LLM read instead, so
  it must state precisely how that discipline re-targets rather than silently
  contradict it.

## Constraints

- **`llm-selects-system-derives-tax-numbers` (hard, legal).** The response schema
  MUST make it structurally impossible for the model to emit `iva_rate`,
  `taxable_base`, or `iva_amount`. Evidence reading does not relax this. Where the
  invoice-printed IVA disagrees with the registry-derived IVA, raise a non-blocking
  advisory (per the no-silent-under-declaration discipline), never overwrite the
  derived value.
- **Human-in-the-loop is mandatory.** Every evidence-derived classification and
  every proposed split is a *suggestion* the operator reviews and applies or
  rejects. The model never silently persists. A low-confidence or refused read MUST
  surface to the operator rather than degrade silently — this is how the documented
  vision limitations are made safe and is the re-targeted form of the OCR
  discipline's confidence-surfacing obligation.
- **Privacy boundary (new, blocking for the multimodal transports).** Decrypted
  `FINANCIAL` evidence may leave the process only along an explicitly permitted
  path. The decrypted-temp-file lifecycle for the CLI-agent route MUST be bounded
  (written to a private location, removed promptly, never logged). The set of
  providers permitted to receive unredacted evidence is an operator-configurable
  decision surfaced through `Settings`; the default posture and whether `LOCAL`
  (text-only, on-host) is the only unredacted path are decided at implementation
  under this constraint.
- **Parent stability.** Builds on stable Stage-1/2 plumbing (suggest/apply,
  the manual-command write path with its validators and the `gross == base + iva`
  invariant), the `SubprocessLLMClassifier` + `resolve_classifier` registry, the
  evidence backend (`Attachment` / `PurchaseInvoiceEvidence`, encrypted via
  `SecureObjectRepository`), and `split_transaction` / `merge_transactions`. No
  new top-level package; all work sits under `application/ledger`,
  `domain/transactions`, and the outbound LLM adapter.
- **Cache correctness.** The LLM cache keys on prompt-text + args hashes only; any
  multimodal input MUST fold the evidence content address (`Attachment.sha256`)
  into the key or two different documents under the same prompt collide.
- **Frontier note.** Multimodal document reading is a current frontier capability;
  provider request shapes (Anthropic `document` block, Gemini inline/File-API,
  OpenAI `input_file`) are stable as of 2026-06-10 but evolve — the bridge
  abstraction must isolate per-provider wire shapes behind one internal interface.

## Implementation

Stage-3 layers onto the existing classify/saturate flow without disturbing the
Stage-1/2 contract.

**Evidence resolution.** When the operator runs classify/saturate with evidence
reading enabled, the application resolves the transaction's linked evidence
(`purchase_invoice_evidence_id` and/or `attachment_ids`) to its bytes and media
kind through the evidence backend, decrypting through the existing secure-object
path. The resolved evidence is the new classification input.

**A unified multimodal abstraction over two transports.** A single internal
evidence-input representation (media kind, bytes/handle, content hash) is rendered
into whichever transport the resolved provider needs:

- **CLI-agent transport (primary, built first).** For the subprocess providers
  (`claude` / `antigravity` / `codex` — today's production surface), the evidence
  is materialised to a bounded-lifetime decrypted temp file and its path is
  injected into the prompt for the agent's `read` tool. This is the
  lowest-friction route and exercises the whole flow end-to-end on the default
  surface.
- **HTTP-SDK transport (multimodal content blocks).** For the outbound-adapter
  providers, the request gains a typed multimodal content path rendered as the
  provider's document/image block — Anthropic `document` (base64 / Files-API
  `file_id` / URL), Gemini inline or File-API, OpenAI `input_file`. Wiring the
  HTTP-SDK adapter into the classify path is net-new (it is unused there today).
- **Text-layer fast-path / `LOCAL` fallback.** The in-tree `pdfplumber` text
  extraction is retained for clean text-native PDFs (cheap, no image tokens) and is
  the only path for the text-only `LOCAL` provider; extracted text flows into the
  existing text prompt and is hashed by the existing cache key unchanged.

**Cache.** The LLM cache key incorporates the evidence content address
(`Attachment.sha256`) for multimodal inputs so distinct documents never collide;
the text-layer route needs no change.

**Reading for selection (Stage-3a).** The classify/saturate prompts are extended
to instruct the model to read the attached document and select the spending
`category` and `iva_category` from their registry-grounded allow-lists, guarded by
the existing `parse_response` hallucination check. Numbers stay derived: the
saturate path looks up the rate and derives base/amount exactly as Stage-2 does.
A new advisory compares the invoice-printed IVA (if the model reports it as a
*read observation*, not a persisted field) against the registry-derived IVA and
surfaces a mismatch. Applied classifications stamp `classified_by = llm:<model>`
and cite the consulted `evidence_id` / `attachment_id` in the
`classification_history` provenance and `evidence_provenance` lineage.

**Reading for splitting (Stage-3b).** A new response schema lets the model propose
an N-way split: a list of children, each carrying a proposed amount, spending
`category`, `iva_category`, and a citation back to the evidence line it derives
from. The application path validates the proposal (children sum to the parent
gross, signs match — the same invariants `split_transaction` already enforces) and,
on operator apply, drives `split_transaction` from the reviewed suggestion. Each
child's regulated euro figures are registry-derived per the constraint above;
evidence provenance is stamped on every child. Reject leaves the parent untouched.

**Operator surface.** The Stage-1/2 verbs are preserved: suggest previews the
evidence-grounded classification (and the proposed split); `--apply` persists;
manual flags override any field and re-stamp manual provenance; reject is
do-not-apply. Evidence reading is opt-in per invocation, and the permitted-provider
privacy posture is read from `Settings`.

## Rationale

Leaning on the LLM multimodal read (Option A) rather than building a separate
deterministic OCR engine is justified by verified capability across every required
format, and is *safe* because the precision safeguard the vendors demand —
human review — is already the spine of the Stage-1/2 contract. Standing up a
second extraction technology (Tesseract/cloud OCR with engine-version pinning,
per-field confidence gates, and a corpus round-trip suite) would duplicate effort
to produce structured fields the LLM already reads, while the truly dangerous part
— the regulated euro figure — is *not* taken from either reader: it is
registry-derived. That separation is what makes leaning on the LLM both rich and
legally defensible.

The accepted OCR-extraction discipline is therefore not superseded but
**re-targeted**: its confidence-surfacing obligation becomes "a low-confidence or
refused LLM read surfaces to the operator, never silently persists"; its
provenance obligation becomes the `llm:<model>` + cited-evidence stamping; and its
corpus discipline (assert behaviour, never exact extractor strings) fits an LLM
read even better than a deterministic engine. Building the CLI-agent file-path
transport first matches the production reality that the classify surface is
subprocess-CLI-only today, delivering the whole flow on the default surface before
the net-new HTTP-SDK wiring. Including splitting in Stage-3 reflects the operator's
direction and is coherent: an invoice with mixed lines is exactly where reading the
document and proposing a split are the same act of understanding.

## Consequences

- **Gain:** the heaviest part of the operator's burden — reading an invoice and
  turning it into a correctly categorised, IVA-classified, possibly-split set of
  ledger entries — becomes a reviewed one-keystroke suggestion grounded in the
  actual document, not the bank-line description alone.
- **Gain:** the mature-but-unused evidence backend finally feeds the pipeline it
  was built for; evidence provenance now threads from attachment through
  classification to (on filing) the bundled revision evidence.
- **New safety surface:** decrypted financial evidence now leaves the process to
  an external model. The privacy boundary (permitted providers, temp-file
  lifecycle, whether `LOCAL` is the only unredacted path) is the principal new risk
  and must be settled before the multimodal transports ship. This is a genuine
  widening of the trust boundary versus Stage-1/2's scalar-only prompts.
- **Honest limitation:** LLM reads can be wrong on poor scans, rotated pages, or
  tiny fonts; the operator review gate is load-bearing, not decorative. The
  printed-vs-derived IVA advisory catches a class of misreads but not all.
- **Pitfall to avoid:** letting a confidently-read invoice number become the
  persisted regulated value. The schema must keep that structurally impossible; the
  read informs selection and advisory cross-checks only.
- **Pathway opened:** once evidence flows into the classifier, the same plumbing
  serves evidence-grounded verification, M349/M347 counterparty extraction, and
  richer reconciliation — all gated by the same review contract.

## Codification candidates


