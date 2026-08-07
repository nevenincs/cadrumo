---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b9a2b6982262691932babe8271a3fbf78c76c7918518d7e87464d3af0002dfbb'
related:
  - '[[2026-08-06-llm-invoice-read-reconciliation-research]]'
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-llm-invoice-read-reconciliation-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-13-llm-evidence-classification-adr]]'
  - '[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]'
---

# `unstructured-document-ingestion` adr: `Unstructured document ingestion: a transcription-anchored semantic pipeline` | (**status:** `proposed`)

## Problem Statement

A taxpayer points the product at an arbitrary document — a phone photograph of a
receipt, a flatbed scan, an image-only PDF, a text-layer PDF in any language and
layout, a spreadsheet or CSV export in an unknown dialect, plain text — and must
get back sanitized, classified, structured data fit for filing to the ledger:
counterparty identity, invoice identity, dates, amounts, the IVA decomposition
per rate, retención, recargo de equivalencia, suplidos, plus direction, invoice
class and category.

The measured state of the tree is that no such capability exists. The current
text extractor (`application/ledger/_evidence_draft.py`, the `_BASE_LABEL_RE` /
`_TOTAL_LABEL_RE` / `_IVA_AMOUNT_LABEL_RE` / `_TAX_ID_RE` / `_DATE_RE` family)
hard-requires Spanish decimal commas, day-first dates, literal Spanish labels
and a Spanish NIF/CIF shape. Driven against nine real third-party vendor PDFs
it recovers 0–1 of 8 fields, one document recovering zero; on the product's own
generated Spanish documents it reaches 5 of 8 — a ceiling that exists only
because those documents were written in the vocabulary the regex was built
from. An Irish VAT id on an intra-EU reverse-charge invoice — exactly the
Modelo 349 population — cannot be read at all. Worst, on the deliberately
defective control document `COM-2026-0005` (necessarily its text-bearing
entry, `OP-PUR-COM-2026-0005_layout-minimal` — a text-layer extractor cannot
read the `_camera-photo` twin) it returned a *valid NIF belonging
to a different entity on the same page* as the supplier tax id: not a failure
but a confident wrong answer, the precise class `no-silent-under-declaration`
exists to forbid. On the tabular side, `ledger import --provider auto` imports
1 of 7 corpus CSVs, and `ledger invoice import` demands fixed English column
names, refusing whole a real Spanish libro registro whose every field is
semantically present under different names and which carries retención, for
which the importer has no column at all.

The unifying observation, tested against the code rather than accepted:
every ingest lane accepts only data already in the product's own shape. The
XLSX provider maps headers through fixed per-bank layouts
(`adapters/inbound/financial/providers/_xlsx.py`, `_row_to_mapping`); the
invoice importer matches literal column names; the evidence extractor matches
literal Spanish labels. There are readers everywhere and a translation layer
nowhere. The operator's directive is unambiguous: real-world documents are
unsanitized and have no enumerable structure; the only dependable way to read
them is a natural-language parser that understands semantic correlation, in the
shape OCR/vision → text representation → categorization/classification. And the
operator's standing, unmet demand is that this functionality is *never tested*
— so the architecture must be independently measurable stage by stage, or it
does not answer the question.

A decision is needed now because `2026-08-06-llm-package-split-adr` deliberately
left the internal pipeline shape open (its D8), the measurement corpus that can
settle it now exists (302 documents, key v5, stage-separated oracles), and
peer campaigns (`2026-08-06-invoice-canonical-structure-adr`'s multi-line
writer, the direction threading of
`2026-08-06-llm-invoice-read-reconciliation-adr`) are converging on the seam
this record must define.

Out of this record's lane, decided elsewhere: canonical structured e-invoice
formats — Facturae 3.2.x, EN16931 CII/UBL, VeriFactu/SII — are read exactly by
deterministic parsers in the core and reach no model
(`2026-08-06-llm-package-split-adr` D7, the `DocumentShape` routing probe).
This pipeline begins where exact reading is impossible.

## Considerations

- **Layout variation is unbounded.** Millions of layouts, any language, any
  labelling vocabulary. Any design that enumerates document shapes is ruled out
  by operator directive; the variation must be absorbed by a model that
  understands semantics, never by per-format code.
- **The measured failure mode to eliminate is the confident wrong answer.** The
  `COM-2026-0005` result — a valid, checksum-passing identifier belonging to
  the wrong party — was produced by unanchored first-match selection. Prompt
  instructions are not a mechanism; the fix must be structural.
- **A peer measurement overturns an ADR's framing.**
  `2026-08-06-llm-invoice-read-reconciliation-adr` frames the counterparty
  defect as an extraction/prompt problem. A peer drove the reader against the
  corpus and measured 26 hit / 0 miss *at the reader*: the value is parsed
  correctly and discarded downstream. The defect class is projection through
  the intermediate contract, not reading.
- **The intermediate contract is a lossy waist.** `InvoiceDraft` sits between
  the richer `ParsedEInvoice` above it and the ~30-field canonical
  `domain/invoices/Invoice` below it. It now carries lines, a per-rate
  breakdown, party names and series, but no direction, no retención, no
  suplidos, no per-field provenance and no confidence axis — so even a perfect
  reader cannot deliver what filing needs through it.
- **The vision path is wired and unmeasured.** `llm/_evidence_draft_vision.py`
  already rasterises in memory, prompts for verbatim transcription, and
  re-grounds every returned string through deterministic validators (checksum
  tax id, day-first date parse, finite European decimal, ISO-4217). That
  grounded-revalidation discipline is correct and is kept; what it lacks is
  anchoring (nothing ties a grounded value to the document's own text), lines,
  retención, and any measurement.
- **The corpus is a stage-separated instrument.** `Y:\code\llm-invoice-smoke\corpus`,
  302 documents in three populations — 30 generated, 66 acquired-real, 206
  operator-corpus (merged at corpus v4) — key `GROUND_TRUTH.json` v5 sha256
  `e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593`
  (890,052 bytes; denominators below re-derived programmatically from that
  key, superseding a stale note that undercounted five of them):
  `stage1_reference_text` exact transcriptions (48 documents) isolate
  reasoning error from reading error; 7 matched scan/original twin pairs
  isolate reading error (`PUR-RECARGO-IMG-014` was retired with its original
  at v4); 130 documents exercise the vision path; `null` truth means an
  emitted value is a fabrication, a hard error; the `COM-2026-0005` control —
  two entries, `OP-PUR-COM-2026-0005_camera-photo` and
  `OP-PUR-COM-2026-0005_layout-minimal` — must never score clean; category is
  scorable over a 59-document denominator (the 30 generated documents with
  intrinsic lanes plus the operator entries carrying one; the 66
  acquired-real stay `category_scorable: false`); every Spanish rendered
  document is generated, so Spanish OCR accuracy carries a stated optimism
  bias (its `GAPS.md` §1). The tree is read-only and not a git repository.
  Two instrument facts an implementer must not discover the hard way: the
  twin→original link is prose in the `notes` field (`"VISION-PATH TWIN of
  <ID>"`), so any harness resolving pairs depends on a regex over prose until
  the corpus grows a structured field; and the key's internal
  `schema_version` is a permanently stale `"1.0"` that has never tracked
  v1→v5 — results cite the sha256, never the schema field.
- **The confidentiality posture is settled and binding.** Decrypted bytes live
  transiently in process memory only; no temp files, caches or logs; on-host
  inference needs no consent gate; off-host transmission of real taxpayer
  documents is explicitly consented, per-invocation, gestor-barred
  (`sensitive-financial-data-secure-storage-only`,
  `2026-06-10-llm-evidence-classification-adr` operator ruling,
  `2026-08-06-llm-package-split-adr` D9/D10). The corpus itself is
  public/synthetic and carries no taxpayer data.
- **The engine substrate exists.** `cadrumo.llm` carries `LLMClient`, a
  provider enum with a LOCAL (Ollama) transport, multimodal image inputs keyed
  by content hash, and pricing/caching plumbing. The package-split ADR deletes
  the cloud subprocess family and mandates a hardware-capability probe (its
  D5, D6). The GPU being contended today is a deployment fact, not an
  architectural constraint.
- **Regulated numbers are never model-derived.** The accepted
  `llm-selects-system-derives-tax-numbers` discipline holds: a reader recovers
  what is *printed*; persisted regulated figures are registry-derived; a
  printed-vs-derived divergence is an advisory or a blocking finding, never a
  silent overwrite.
- **Refusal has a cost too.** The operator forbids both silent wrong values
  and the refusal of legitimate documents (the CSV importer refusing a whole
  file over one unknown column is the measured failure of refuse-whole).

## Considered options

- **A — Harden the regex/heuristic extractor: more labels, more languages, more
  formats.** Rejected outright: it is the enumerate-shapes design the operator
  forbids, its measured ceiling on its own home vocabulary is 5 of 8, and
  first-match heuristics are the mechanism that produced the confident wrong
  answer.
- **B — One-shot multimodal extraction: image or text in, typed fields out, no
  intermediate representation.** Simplest wiring; roughly what the current
  vision path does. Rejected: it is structurally unmeasurable stage by stage —
  a wrong field cannot be attributed to reading or to reasoning, the corpus's
  twin and reference-text oracles have nothing to attach to, and anchoring has
  no artefact to anchor against. It fails the operator's central testing
  demand regardless of how well it scores.
- **C — Staged semantic pipeline: acquisition to a faithful transcription,
  semantic extraction over the transcription, deterministic grounding and
  verification, closed-set classification (chosen).** Matches the operator's
  stated shape; every stage has a corpus oracle; the transcription artefact is
  what makes anchoring — the anti-fabrication mechanism — enforceable by
  deterministic code.
- **D — Cloud-scale document-AI service.** Categorically rejected: off-host by
  construction, colliding with the confidentiality guarantee and with the
  package-split ADR's deletion of the cloud path.
- **For tabular inputs, a sub-choice:** per-row semantic extraction (each row
  through the model) versus **schema-level semantic mapping** (the model maps
  column headers to closed field roles once; deterministic code copies every
  cell). The second is chosen: it touches each value with deterministic code
  only, making per-row fabrication structurally impossible, and it costs one
  model call per file instead of one per row.

## Constraints

- **Confidentiality (absolute).** All processing of real taxpayer documents is
  in-memory and on-host by default; any persisted intermediate (transcription
  cache, drafts) writes through the core's encrypted secure storage; the
  inference subpackage holds no storage handle
  (`2026-08-06-llm-package-split-adr` D3/D9/D10, which this record inherits
  unchanged).
- **Regulated numbers stay registry-derived**; readers recover printed values
  only (`llm-selects-system-derives-tax-numbers`, reaffirmed by
  `2026-06-10-llm-evidence-classification-adr`).
- **Human review is mandatory.** Every extracted draft and classification is a
  suggestion crossing the operator confirm boundary; the D-K plausibility gate
  of `2026-08-06-invoice-canonical-structure-adr` stays at the core boundary.
- **Typed boundaries.** All model output crosses into the core as strict
  pydantic v2 payloads with closed StrEnum axes in `core/`; free text never
  crosses the seam as an interchange value (package-split D4).
- **Local model quality is the frontier risk.** The default local vision model
  is bound to a consumer-hardware constraint
  (`2026-06-13-llm-evidence-classification-adr`); the corpus vision cells
  measured so far are three documents each — no accuracy claim about local
  models is available yet, which is why acceptance floors below are set from a
  measured baseline, not invented here.
- **The corpus is external, read-only, and not a git repository.** In-repo CI
  gates cannot depend on it, and CI cannot invoke live local inference (live
  local inference has destabilised the development host; the GPU is shared).
  The measurement design must be honest about this split.
- **Parent stability.** The package-split ADR is `proposed`; its D5 (cloud
  deletion) and D7 (structured parsing) are in flight. This record couples to
  its boundary decisions and to the accepted canonical-invoice ADR; if the
  package-split record moves materially, the coupling points named here are
  the review checklist.

## Implementation

### D1 — The canonical pipeline, and why the seams sit where they do

Four stages behind the existing shape probe, one waist, one confirm boundary:

```
bytes → [S0 shape probe]  → structured? → exact parsers (peer-owned, no model)
      → [S1 acquisition]  → DocumentTranscription (faithful text representation)
      → [S2 extraction]   → anchored candidate fields (semantic, model)
      → [S3 grounding]    → InvoiceDraft (deterministic verification)
      → [S4 classification] → direction/class/category suggestions (closed sets)
      → operator confirm (existing boundary, unchanged)
```

**S1 — acquisition.** Produce a faithful reading-order text representation of
the document, printed forms preserved (`2.420,00`, not `2420.00`). For a
text-layer PDF or plain text this is deterministic and exact. For an image or
scan-only PDF it is the local vision model in *transcription* role: read the
page, emit the text, interpret nothing. The output is one typed record,
`DocumentTranscription`: reading-order text, page count, source content
address, and its own origin (`TEXT_LAYER` exact vs `VISION` with model
identity and revision). This record is the `NormalizedDocument` seam the
package-split ADR specified obligations for without building: it is a single
typed record (not a tagged union), it inherits the `EvidenceInput`
serialization tripwires, and its cache — the extracted-document cache that
ADR's D9 authorises — persists only through the core's encrypted secure
storage, keyed by source content address plus transcriber identity.

**S2 — semantic extraction.** A local text model reads the transcription and
emits candidate fields as a strict typed payload. This stage is where layout
variation is absorbed: no labels, no locale assumptions, no format branches —
the model correlates semantically, which is the only approach that survives
"millions of layouts". Every candidate field carries its **anchor**: the
verbatim printed form as it appears in the transcription. Identity fields
(party tax ids, party names) additionally carry **role evidence**: the
transcription context that assigns the value to a party role. The payload is
`extra="forbid"`, closed key set; the model structurally cannot add fields.

**S3 — grounding and verification, all deterministic.** Every candidate is
verified by real code before it becomes a draft field:

- *Anchor check:* the anchor must actually occur in the transcription, and the
  typed value must equal the deterministic parse of that anchor (the existing
  finite-European-decimal, day-first-date, checksum-tax-id, ISO-4217
  validators, kept verbatim from `llm/_evidence_draft_vision.py`). A value
  the model emitted that is not present in the document's own text is
  **rejected by construction** — fabrication of numbers, dates and
  identifiers absent from the page is structurally impossible at this seam.
- *Role resolution:* when a document presents more than one checksum-valid tax
  identifier, the field resolves only if role evidence deterministically
  assigns exactly one candidate to the requested role (and the taxpayer's own
  identifier, known from the profile, is excluded from counterparty
  candidacy). Otherwise the field is `AMBIGUOUS`: surfaced with all
  candidates, never first-match. This is the structural elimination of the
  `COM-2026-0005` failure mode.
- *Arithmetic closure:* the canonical identities
  `total = base + cuota + recargo + suplido` and
  `cash = total − retención` are checked over the per-rate breakdown and the
  printed totals. A mismatch is a typed discrepancy finding carried on the
  draft — on either `COM-2026-0005` entry (the defects are shared document
  content across both renderings) the printed 890.00 against a computed 927.22
  surfaces as a blocking finding at confirm, and its `B1234567X` fails the
  check character and never grounds at all.
- *Per-field degradation:* a candidate that fails grounding drops to `None`
  with a visible advisory naming what was seen and why it was rejected. The
  document is never refused whole because one field failed; it is refused
  whole only when nothing grounds. A grounded-but-inconsistent total is a
  blocking finding the operator must resolve at confirm. This is where this
  record lands on refusal versus wrong value: **no silent wrong numbers, no
  whole-document refusals for partial failure** — degradation is per-field,
  loud, and operator-resolvable.

**S4 — classification.** Direction, invoice class and category are judgments,
kept behind the fact/judgment seam. Direction: when the taxpayer's own
identifier appears on the document, direction is *derived deterministically*
(own NIF in the issuer role → issued; in the recipient role → purchase or
received) and cross-checked against the verb-supplied `--kind`, a divergence
surfacing as a finding; when it does not appear, the model's suggestion is
exactly that, and the operator's kind decides. Class and category are
closed-set selections from registry-grounded allow-lists under the accepted
suggest/review/apply contract — the document proposes, the operator disposes.
The extraction stage never invents a category and the classification stage
never touches an amount.

**Why these seams.** S0/S1 is the exactness boundary (decided by the peer
ADR). S1/S2 is the reading/reasoning boundary — placed exactly where the
corpus can measure each side independently (twins measure reading; reference
text measures reasoning), and where the cacheable custody artefact lives.
S2/S3 is the probabilistic/deterministic boundary — everything downstream of
S3 is real code testable in CI without a model. S3/S4 is the fact/judgment
boundary — facts are grounded, judgments are selected from closed sets and
reviewed. Each seam exists because something must be independently measured
or enforced there; none exists for layering aesthetics.

### D2 — This record closes the package-split ADR's D8, and supersedes its precondition

`2026-08-06-llm-package-split-adr` D8 left one-shot versus two-stage open,
requiring a stage-isolation measurement before any ADR adopts two-stage. This
record adopts the staged shape and **supersedes that precondition**, on two
grounds it could not have weighed: the operator has since directed the staged
shape explicitly ("OCR/vision → text representation →
categorization/classification"), and the decisive criterion is not the
relative accuracy D8 wanted measured but *measurability itself* — a one-shot
design cannot be stage-measured at all, so no measurement outcome could
justify it against the operator's testing demand. The stage-isolation run
remains valuable and becomes the pipeline's *baseline measurement* rather
than its gate.

The obligations D8 attached to the staged shape are carried, not dodged: the
injection hazard of promoting hostile document text across a stage boundary
is bounded by S2's closed output schema (anchored candidates only, no free
text crosses), by S3 grounding every value against the transcription, by S4
selecting from allow-lists, and by an injection regression gate (below). The
`NormalizedDocument` custody obligations land in S1 as specified.

### D3 — The regex extractor is deleted; the corpus gate is the anti-drift ratchet

The Spanish-label regex family in `application/ledger/_evidence_draft.py` is
deleted, not demoted: measured 0–1 of 8 on real documents and the source of
the confident-wrong answer, it is exactly the per-format code the operator
forbids, and `no-legacy-compatibility` forbids keeping it as a fallback. The
text-layer path becomes S1-exact → S2 semantic, same as the vision path from
S2 onward. The deterministic *validators* it shares with the vision path
(checksum, date, decimal, currency) are the S3 grounding vocabulary and are
kept.

What stops the design drifting back toward hardcoded shapes: the corpus
acceptance gate spans nine languages and both directions, and a
label-vocabulary reader structurally cannot clear the non-Spanish set — the
gate is the ratchet, not a style rule. Additionally, no new code branch on
document layout, label text or language is admissible in S1–S3; the only
sanctioned shape branch in the whole pipeline is the S0 exactness probe,
which routes *toward more exact* reading, never toward a layout heuristic.

### D4 — Anti-fabrication is anchoring plus closure, by construction

Stated as one mechanism because it will be reviewed as one: **no value
reaches the draft unless deterministic code can point at where the document
says it** (anchor check), **no identity resolves without unique role
evidence** (role resolution), and **no monetary set is accepted silently out
of closure** (arithmetic identities). Prompt instructions remain (they reduce
noise) but carry zero enforcement weight. The honest limit is stated rather
than glossed: on the vision path the transcription is itself model-produced,
so anchoring bounds S2 fabrication to S1 transcription error — which is
precisely the quantity the twin oracle measures, and why the S1/S2 seam
exists. A fabricated value must now survive two independent model errors that
agree, instead of one unanchored guess, and the fabrication rate is measured
per stage rather than asserted.

### D5 — Per-field provenance, and structural rather than numeric confidence

Every draft field carries a typed provenance envelope: an origin StrEnum in
`core/` (`EXACT_STRUCTURED`, `TEXT_LAYER`, `VISION`, `TABULAR_MAPPED`,
`OPERATOR`), the anchor (verbatim printed form), the grounding outcome, and
any ambiguity candidates. No numeric model self-confidence is persisted —
a model's confidence estimate is not evidence and would be theatre; the
trustworthy axes are *how the value was obtained* and *what verification it
passed*, which are facts. The envelope travels to every operator-facing CLI
JSON payload (parity with casilla `legal_refs`/`source_refs` grounding,
per `aeat-calculation-grounding`) and into the confirm provenance stamps, so
an exactly-read value stays distinguishable from a model-read one from the
byte source to the operator's screen and into the persisted record's
`classified_by`/evidence lineage. An operator override re-stamps `OPERATOR`
provenance; nothing ever silently launders a vision-read value into an
exact-looking one.

### D6 — The intermediate contract: `InvoiceDraft` is widened; the waist becomes loss-forbidden

One waist, no parallel model, no bypass. `InvoiceDraft` is widened with:
direction suggestion (typed, nullable), retención (rate and amount), suplidos,
the per-field provenance envelopes of D5, the discrepancy findings of D3, and
the transcription content address that ties the draft to its S1 artefact. The
counterparty rename decided by `2026-08-06-llm-invoice-read-reconciliation-adr`
rides along. The parsers, the vision path and the tabular lane all project
into this one record, and it crosses the existing confirm boundary unchanged.

The waist additionally becomes **loss-forbidden**: a projection-parity gate
asserts that every field the draft carries survives to the confirm-surface
payload the operator sees. This is the fix lane for the measured projection
defect — the peer's 26 hit / 0 miss at the reader proves values are read and
then discarded downstream, so the gate sits on the projection, where the
defect lives. **This record supersedes, in part,
`2026-08-06-llm-invoice-read-reconciliation-adr`:** its framing of the
counterparty defect as an extraction/prompt problem is corrected to a
projection defect on the measurement above, and its text-path remedy of
Spanish-label anchoring is superseded by D3 (label anchoring is per-format
code). Its direction-threading decision and the counterparty rename survive
and are consumed here; its two named open operator rulings (the
domestic-versus-not discriminator, the transcribed taxable base on the
standalone path) remain open and are *not* decided by this record.

### D7 — Tabular inputs: same pipeline, schema-level semantic mapping

A CSV or spreadsheet is already a text representation, so the tabular lane
enters at S2 with a different semantic task: **column-role mapping**. A
deterministic S1 normalises dialect (delimiter, decimal convention, encoding,
preamble and summary rows — the corpus's nine CSV exports span exactly these
axes) into a typed table. The model then maps the observed header vocabulary
onto a closed `FieldRole` StrEnum in `core/` — once per file, never per row —
and deterministic code copies every cell value under that mapping. The model
never touches a cell value, which is the tabular anti-fabrication: role
assignment is an allow-list selection (injection-resistant the way
classification is), and values are moved only by real code. Ambiguous
headers resolve exactly like ambiguous identities: surfaced with candidates,
operator-resolvable, never guessed. Unknown columns map to `UNMAPPED` and are
reported; the file is never refused whole for carrying a column the product
does not know — the measured libro registro header (every field present, not
one name matching, plus retención) must map fully, and does under this
design because retención is a role, not a column name.

Semantic field mapping is thereby **one capability** — role assignment over a
closed vocabulary, owned by `cadrumo.llm` — with two consumers: the invoice
book importer, and the bank-statement lane, where it enrols strictly *after*
the exact fixed-layout providers (exact-first routing, the same control as
the S0 probe: a known bank export never reaches a model). Redesigning
statement auto-detection beyond that fallback enrolment is deferred, named
below. Row-level grounding is unchanged S3: per-row arithmetic closure where
the table carries base/cuota/total, checksum ids, date and decimal parsing
under the *detected* dialect.

### D8 — The engine abstraction, and how confidentiality survives it

The pipeline binds to `LLMClient` and the `LLMProvider` enum only, with
role-named model settings (a transcription vision model, an extraction text
model, a mapping model — each defaulting sensibly, each overridable). It is
local-only per the package-split ADR's D5; whether the local runtime serves
the model on GPU or CPU is Ollama's deployment concern, invisible at this
seam — today's GPU contention constrains *when measurement runs*, never the
architecture. The hardware floor is declared and probed through that ADR's
D6 capability probe, refusing with a typed shortfall rather than thrashing.
Confidentiality survives by inheritance, not re-argument: images and text
move as in-memory base64/strings through the existing client, the subpackage
holds no storage handle (D3 of the split ADR), every persisted intermediate
routes through core secure storage (D9), and the persistence gates keep
scanning the code (D10/D11). Nothing in this pipeline adds a file-writing
transport, and the S1 cache is encrypted by construction.

### D9 — Stage-by-stage measurement: the map from stage to oracle

Every stage has a named oracle in the corpus (key v5, sha256
`e2db6a49...`; every reported result names its key hash — the sha256, never
the key's internal `schema_version`, which is permanently stale at `"1.0"`;
every Spanish OCR
figure carries the `GAPS.md` §1 optimism-bias caveat verbatim):

| Stage | Oracle | Metric | Bite evidence |
|---|---|---|---|
| S1 vision transcription | 48 `stage1_reference_text` transcriptions; 7 matched twin pairs (linked today only by prose `notes`, see Considerations); the 130 vision-path documents | printed-form recovery of key amounts/ids; twin delta = isolated reading error | a twin whose original scores and whose scan does not is reading error made visible |
| S2 extraction | run over `stage1_reference_text` (perfect text) against field truth | field accuracy over non-null truth; fabrication = any value where truth is `null`, hard error | `null`-truth fields exist throughout; both `COM-2026-0005` entries (`_camera-photo`, `_layout-minimal`) must surface findings, never score clean |
| S3 grounding | property tests + the two `COM-2026-0005` entries | anchor rejection, role ambiguity, closure findings | mutation-proven: alter one grounded amount, the closure gate must red |
| S4 classification | the 59 category-scorable documents (30 generated + operator entries with intrinsic lanes); direction cross-check is deterministic | confusion matrix over the scorable set; acquired-real excluded by `category_scorable: false` | scoring the acquired-real set would measure a labelling convention — excluded by design |
| Tabular mapping | operator corpus: 6 `csv_dialect` descriptors, 9 CSV exports, the libro registro header | full-role recovery per file; unmapped-column reporting | the current importer's 1-of-7 is the baseline the gate must beat |
| End-to-end | twins through the full pipeline | draft equality between twin and original | any divergence localises to S1 by construction |

Two honest lanes, because the corpus is external and CI cannot run local
inference:

- **The measured lane (offline).** Model-bearing stages (S1 vision, S2, the
  mapping call) are measured by a harness run against the corpus with the
  fleet quiesced, results persisted with the key hash, model identity and
  revision — the discipline the package-split ADR's own figure-tracing
  established. Acceptance floors are set from the *first measured baseline*
  at plan time, not invented in this record; the one floor set here by
  construction is that the anchored-fabrication rate on S3-passing fields is
  zero, because a counterexample is a grounding bug, not a model quality
  question.
- **The gate lane (in-repo CI).** Everything deterministic runs as real-code
  gates on bundled fixtures: anchor enforcement, role-ambiguity surfacing,
  arithmetic closure, projection parity across the waist, strict-schema
  refusal of malformed S2 payloads, dialect normalisation, and an injection
  regression gate feeding a transcription containing instruction-shaped text
  and asserting the S2→S3 boundary passes no unanchored value and no
  out-of-schema key. Fixtures are a licence-clean bundled subset (the corpus
  documents carry verified Apache-2.0/BSD-3/EUPL-1.2 provenance;
  `COM-2026-0005` is operator-authored) with provenance sidecars per
  `fixture-provenance-declared-in-sidecar`. No mocks, no skips; model calls
  do not occur in this lane because no gate in it needs a model — that is
  what the S2/S3 seam is *for*. Every gate is proven by mutation before it
  is trusted.

## Rationale

The staged shape wins on a knockout: it is the only option that can be
measured stage by stage, and unmeasurable designs are non-answers to the
question as posed. The operator's directive independently mandates the same
shape, and the corpus was built with oracles at exactly these seams — twins
for reading, reference text for reasoning, `null`-truth for fabrication, a
poisoned control for the harness itself. Where D8 of the package-split ADR
worried that adopting two-stage without measurement repeats a conflation,
this record answers that the choice is not being made on unmeasured accuracy
but on measurability, and then makes the measurement the pipeline's first
deliverable.

Anchoring wins over confidence scores and prompt discipline because it is the
only mechanism among them that *deterministic code can enforce*. The measured
catastrophic failure was not a low-quality read but a structurally
unconstrained selection; the remedy is to make the unconstrained selection
inexpressible. The per-field provenance envelope follows the same logic:
facts about how a value was obtained, rather than a model's opinion of
itself.

Widening `InvoiceDraft` rather than replacing it keeps one waist and honours
no-parallel-write-paths; making the waist loss-forbidden is what converts the
peer's projection measurement into a standing guarantee. Schema-level mapping
for tabular data wins because it removes the model from the value path
entirely — the strongest anti-fabrication position available anywhere in this
design — at the cost of one closed vocabulary to maintain, which is a
`core/` enum under normal review.

## Consequences

**Gains.** Every input class the operator named — photograph, scan, image
PDF, arbitrary text PDF, spreadsheet, CSV, plain text — reaches one measured
pipeline with one waist and one confirm boundary. The Modelo 349 population
becomes readable (any VAT-id vocabulary, any language). The libro registro
imports. Fabrication becomes a measured, per-stage quantity with a
structural zero on anchored fields. The operator's testing demand is met by
construction: the stage map above *is* the test plan.

**Costs and risks, honestly.** Two model roles (vision transcription, text
extraction) must clear floors that do not exist yet; if the consumer-hardware
local models cannot transcribe well enough, the twin oracle will say so
precisely, and the recourse is model selection, not architecture. S2 over a
long transcription may stress small local context windows — chunking is an
S2-internal concern that must never leak into the contract. Deleting the
regex extractor removes the only current text-path reader before its
replacement lands; sequencing mirrors the package-split ADR's D5 window
discipline: the semantic reader lands wired before the deletion commit. The
anchor check requires transcription and extraction to agree on printed form;
normalisation drift between S1 and S3 would manifest as false rejections —
visible, annoying, and safe-side, but a real tuning cost. The corpus's
Spanish optimism bias means Spanish-vision floors are provisional until real
Spanish rendered documents are acquired.

**Supersessions and contradictions, consolidated.** This record: closes
`2026-08-06-llm-package-split-adr` D8 (staged shape adopted) and supersedes
its stage-isolation-measurement precondition on the grounds stated in D2;
supersedes in part `2026-08-06-llm-invoice-read-reconciliation-adr` (the
extraction-side framing of the counterparty defect and the Spanish-label
anchoring remedy), while consuming its direction threading and rename and
leaving its two open operator rulings open; and completes the re-targeting of
`2026-05-30-purchase-invoice-ocr-extraction-discipline-adr` — its
confidence-surfacing and provenance obligations survive as D5, and the
deterministic-extractor lineage it once assumed ends with D3's deletion.
Status updates on those records land with the changes that make them true.

**Deliberately out of scope, each named rather than silent.** Handwriting
recognition (the corpus's own margin-note case tests separation, not
recognition). Multi-document bundles — splitting one scan containing several
documents — a real operator need with no corpus oracle yet. Counterparty
*resolution* (matching an extracted identity against the censo/counterparty
registry) — extraction ends at a grounded identity; resolution is a
different authority. Bank-statement auto-detection redesign beyond fallback
enrolment of the mapping capability. `.eml` ingestion. Acquisition of real
rendered Spanish documents and the hand transcription of the 12 real
photographs — corpus work, outside this repository. The sanitizer-wiring
hardening pass, already named by the package-split ADR for its own campaign.

**Pathways opened.** The `DocumentTranscription` artefact makes
re-extraction cheap (re-run S2 on a cached transcription when a model
improves, without re-reading bytes), gives audits a durable answer to "what
did the reader see", and is the natural substrate for the batch and resume
verbs the package-split ADR cleared ground for.

## Codification candidates

None. `no-silent-under-declaration`, `sensitive-financial-data-secure-storage-only`,
`aeat-architecture-boundaries`, `no-legacy-compatibility` and
`aeat-quality-gates` already govern every decision here; this record applies
them. The durable lessons (anchoring, the loss-forbidden waist, the stage
oracles) are carried as executable gates, the stronger form.
