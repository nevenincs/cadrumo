---
tags:
  - '#adr'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-llm-evidence-classification-research]]"
  - "[[2026-06-04-llm-ledger-classification-adr]]"
  - "[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
  - "[[2026-04-17-attachment-service-adr]]"
---



# `llm-evidence-classification` adr: `Evidence-aware LLM ledger classification (Stage-3): on-host/local-first reading; cloud only behind a consent gate; splitting in scope` | (**status:** `accepted`)

> **DECISION 2026-06-10 (operator ruling, binding).** The first draft treated taking
> decrypted sensitive evidence out of secure storage (a decrypted temp file for the
> CLI agents, and/or base64 transmission to a cloud provider) as a tunable "privacy
> boundary." That was wrong. Two bindings now govern this ADR:
>
> 1. **Secure-storage-only persistence (absolute).** All sensitive financial data —
>    every purchase invoice and every incoming or outgoing business invoice, and any
>    decrypted evidence bytes — persists only inside the encrypted secure-storage
>    backend via the runtime wrapper that maps to the active profile bucket. Nothing
>    sensitive is ever persisted outside it: no temp files, no scratch dirs, no
>    plaintext side stores, no logs. Decrypted bytes exist only transiently in
>    process memory. This is the prior-ADR-enforced invariant, not a new choice.
> 2. **On-host reading is the default and the only posture acceptable for serious
>    use.** Evidence is read by on-host processing only: the in-tree `pdfplumber`
>    text-layer plus an on-host/local vision model (Ollama at localhost, in-memory
>    base64 images — never a temp file). Cloud providers (the `claude`/`codex`/`agy`
>    subprocess agents and the HTTP providers) may read sensitive evidence **only**
>    behind an explicit, per-invocation consent gate in which the operator
>    acknowledges that their sensitive data will leave the machine and be uploaded.
>    That gate is default-off and is **not acceptable for gestors or any real serious
>    usage**; it exists only as a deliberate, recorded, individual-user exception.
>
> This reverses the first draft's "lean on cloud LLMs (Option A)" headline. The
> headline is now: lean on on-host/local reading; cloud is a gated, acknowledged
> exception, never the default.

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
- **Sensitive evidence lives only in secure storage — and the feature's premise
  collides with that.** Every purchase invoice and business invoice persists only
  in the encrypted secure-storage backend (active profile bucket via the runtime
  wrapper); nothing sensitive is ever persisted outside it. But "have a model read
  the invoice" requires the bytes to reach a model. The cloud `claude`/`antigravity`/
  `codex` subprocess agents and the HTTP providers (Anthropic/OpenAI/Gemini) all
  transmit the bytes off-host, and the subprocess route additionally needs a file on
  disk for the agent's `read` tool — a flat violation. This is not a tunable
  boundary; it is the decisive feasibility question for the whole feature (see
  Constraints and "Operator ruling required"). Stage-1/2 never hit this because they
  sent only scalar transaction fields, which are not the sensitive document.
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
- **Secure-storage-only persistence (hard, absolute, non-negotiable).** All
  sensitive financial evidence persists exclusively in the encrypted secure-storage
  backend via the runtime wrapper mapped to the active profile bucket. No code path
  may write decrypted evidence — or any sensitive financial data — anywhere outside
  secure storage: no temp files, no scratch directories, no plaintext side stores,
  no logs. Decrypted bytes may exist only transiently in process memory and must
  never be persisted. This eliminates the decrypted-temp-file design entirely. It
  also means the existing `PurchaseInvoiceEvidence` `source_path` field (a pointer
  to a cleartext file on operator disk) is NOT a valid byte source for this feature;
  evidence bytes must be read from secure storage, and bringing invoice bytes fully
  into secure storage is a precondition if any are not already there.
- **On-host reading by default; cloud only behind an explicit consent gate.**
  Holding bytes in memory to hand to a model is the compliant pattern only when the
  model runs on-host and the bytes never leave the machine. The default and
  serious-usage path is therefore on-host: the in-tree text-layer plus a local
  vision model. Transmitting decrypted invoice bytes to any cloud model — the
  subprocess CLI agents included — is permitted only through an explicit,
  per-invocation consent gate where the operator acknowledges the upload; that gate
  is default-off, must be re-affirmed each invocation (not a sticky setting), and is
  disallowed for gestor/professional contexts. The CLI-agent file-path route is
  doubly non-compliant (it both transmits off-host and writes a file to disk) and is
  excluded even under consent; the only consented cloud transport is in-memory HTTP
  base64. Whether a deployment is "gestor/serious" enough to forbid the gate
  entirely is a policy the consent surface must encode, not bury.
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
reading enabled, the application reads the transaction's linked evidence bytes
**from secure storage** (active profile bucket via the runtime wrapper) into process
memory only. Bytes are never written to disk and never persisted outside secure
storage. A precondition is that invoice bytes actually live in secure storage; the
existing `PurchaseInvoiceEvidence.source_path` (a pointer to a cleartext file on
operator disk) is not a valid byte source and must be replaced by an in-store byte
read (the `Attachment` store's `read_bytes`, or an equivalent secure-object read)
before reading is wired.

**On-host reader (default, serious-usage path).** The single internal
evidence-input representation (media kind, in-memory bytes, content hash) is fed to
an on-host reader:

- **Text-layer (text-native PDFs).** The in-tree `pdfplumber` extraction runs fully
  on-host over the in-memory bytes and yields text that flows into the existing text
  prompt — no new transport, works for every provider including a local model, and
  is the cheapest path.
- **On-host vision (scanned/image evidence).** For scanned PDFs and photos, pages
  are rendered to images on-host (e.g. via an in-process PDF rasteriser) and handed
  as in-memory base64 images to a local vision model. The `LocalAdapter` (Ollama at
  localhost) is extended to carry the Ollama `images` field on its chat message so a
  local vision model (e.g. a `llama3.2-vision`/`qwen2.5-vl`/`minicpm-v` class model)
  reads them. Nothing leaves the machine; no file is written.

**Cloud reader (consent-gated exception, never default).** A cloud read is reachable
only when the operator passes the explicit consent gate acknowledging the upload.
The only consented cloud transport is in-memory HTTP base64 through the outbound
adapter (Anthropic `document` / Gemini inline / OpenAI `input_file`); the CLI-agent
file-path route is excluded because it writes a file. The gate is default-off,
re-affirmed per invocation, recorded in provenance, and refused outright in
gestor/professional deployments.

**Cache.** Any evidence-derived input folds the evidence content address
(`Attachment.sha256`) into the LLM cache key so distinct documents never collide;
the plain text-layer route is hashed by the existing key unchanged.

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
do-not-apply. Evidence reading is opt-in per invocation and defaults to the on-host
reader. Selecting a cloud provider for evidence reading forces the consent gate: an
explicit per-invocation acknowledgement that sensitive data will be uploaded
off-host, default-off, refused in gestor/professional deployments, and recorded in
provenance. No sticky setting silently keeps the cloud path on.

## Rationale

Reading evidence with an LLM rather than building a separate deterministic OCR
engine is justified by verified capability across every required format, and is
*safe* because the precision safeguard the vendors demand — human review — is
already the spine of the Stage-1/2 contract. But "LLM reading" must obey the
secure-storage invariant, so the reader is on-host by default: the in-tree
text-layer plus a local vision model, fed bytes read from secure storage into memory
and never written to disk. This keeps sensitive financial documents on the machine
for serious use, which is the only acceptable posture for gestors and real usage. A
cloud read remains *technically* available but only as an explicitly consented,
recorded, individual-user exception — never the default — because uploading a
client's invoices to a third party is exactly the exposure the invariant exists to
prevent. The regulated euro figure is still not taken from any reader (on-host or
cloud): it is registry-derived, which is what keeps the result legally defensible
regardless of who read the document.

The accepted OCR-extraction discipline is therefore not superseded but
**re-targeted**: its confidence-surfacing obligation becomes "a low-confidence or
refused LLM read surfaces to the operator, never silently persists"; its
provenance obligation becomes the `llm:<model>` + cited-evidence stamping; and its
corpus discipline (assert behaviour, never exact extractor strings) fits an LLM
read even better than a deterministic engine. Build order follows the
secure-storage invariant: the on-host text-layer path lands first (cheapest,
covers text-native invoices, no new transport), then the on-host local vision
reader for scanned/image evidence; the consent-gated cloud path is last and
optional. Including splitting in Stage-3 reflects the operator's direction and is
coherent: an invoice with mixed lines is exactly where reading the document and
proposing a split are the same act of understanding.

## Consequences

- **Gain:** the heaviest part of the operator's burden — reading an invoice and
  turning it into a correctly categorised, IVA-classified, possibly-split set of
  ledger entries — becomes a reviewed one-keystroke suggestion grounded in the
  actual document, not the bank-line description alone.
- **Gain:** the mature-but-unused evidence backend finally feeds the pipeline it
  was built for; evidence provenance now threads from attachment through
  classification to (on filing) the bundled revision evidence.
- **The invariant forbids widening the trust boundary, and the design honours it.**
  Decrypted sensitive evidence is never persisted outside secure storage and, by
  default, never leaves the host: the serious-usage reader is on-host (text-layer +
  local vision). The cost is real — on-host vision quality depends on the local
  model and the machine, and a local vision model must be provisioned for
  scanned/image evidence. The cloud `claude`/`codex`/`agy` CLI agents cannot read
  sensitive evidence at all (they write a file and upload); only the consent-gated
  in-memory HTTP path can, and it is off by default and barred for gestor use.
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

- **Rule slug:** `evidence-read-never-emits-regulated-numbers`.
  **Rule:** When an LLM reads attached evidence (PDF, image, email, document) to
  classify a transaction, it may select the spending category and IVA category
  from registry-grounded allow-lists and propose split boundaries, but the
  persisted `iva_rate` / `taxable_base` / `iva_amount` MUST stay registry-derived;
  an invoice-printed amount is an advisory cross-check only, never the persisted
  value (capability to read a number is not permission to emit it). Extends
  `llm-selects-system-derives-tax-numbers` to the evidence-reading case.
- **Rule slug:** `sensitive-financial-data-persists-only-in-secure-storage`.
  **Rule:** All sensitive financial data — every purchase invoice and every
  incoming or outgoing business invoice, and any decrypted evidence bytes — persists
  only inside the encrypted secure-storage backend via the runtime wrapper mapped to
  the active profile bucket. No code path may write or persist sensitive data
  anywhere outside secure storage (no temp files, no scratch dirs, no plaintext side
  stores, no logs); decrypted bytes may exist only transiently in process memory and
  must never be persisted. (This is the existing, prior-ADR-enforced invariant,
  restated here because this feature is exactly where an agent is tempted to break
  it.)
- **Rule slug:** `off-host-evidence-upload-requires-explicit-consent-gate`.
  **Rule:** Evidence reading runs on-host by default (in-tree text-layer plus a
  local vision model). Transmitting sensitive evidence to a cloud model is permitted
  only behind an explicit, per-invocation consent gate in which the operator
  acknowledges the upload; the gate is default-off, re-affirmed each invocation (no
  sticky enable), recorded in provenance, refused in gestor/professional
  deployments, and never reachable via a file-writing transport (CLI-agent route
  excluded; in-memory HTTP only).

## Operator ruling (resolved 2026-06-10)

The secure-storage invariant forced one question: may decrypted sensitive invoice
bytes ever be transmitted off-host to a model, or must evidence reading run entirely
on-host? The operator ruled **on-host only by default — never off-site for serious
use** — with a narrow, explicitly-consented cloud exception:

- **On-host is the default and the only posture acceptable for gestors / real
  serious usage.** Evidence reading uses the in-tree on-host text-layer extraction
  plus an on-host/local vision model (Ollama at localhost, in-memory base64 images).
  An on-host vision model must be provisioned for scanned/image evidence. This is the
  primary build target.
- **Cloud is a consent-gated exception only.** A cloud read requires an explicit
  per-invocation consent acknowledgement that sensitive data will leave the machine
  and be uploaded. Default-off, recorded, and disallowed for gestor/professional use.
  Only the in-memory HTTP transport is eligible; the file-writing CLI-agent route is
  excluded entirely.
- **Local-model support is a first-class investigation/build item** (Ollama vision +
  on-host PDF rasterisation), not an afterthought.

The downstream research finding and the implementation plan are corrected to match
this ruling (on-host reader Waves replace the temp-file/cloud-first design; the
consent gate is its own Phase).

