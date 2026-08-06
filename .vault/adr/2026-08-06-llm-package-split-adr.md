---
tags:
  - '#adr'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:aa2be766e897db458d175df3818e3b7ed8694a470a9d2392d3c9a8777247fc64'
related:
  - "[[2026-08-06-llm-package-split-research]]"
  - "[[2026-08-06-llm-package-split-enforcement-and-disposition-audit]]"
  - "[[2026-08-06-llm-package-split-measurement-basis-reference]]"
  - "[[2026-08-06-llm-package-split-ingest-cascade-reference]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
---
# `llm-package-split` adr: `Local-inference document reading as a gated subpackage: exempt from encryption, bound by the persistence gates` | (**status:** `proposed`)

## Problem Statement

The document-ingestion-and-inference path is the only part of Cadrumo that is
probabilistic, hardware-dependent and privacy-sensitive, and it currently sits
undifferentiated inside a deterministic tax engine bound by `aeat-safety-legal-gates`.
Five separate problems trace to that co-location: model licence questions become
core-product blockers; the hardware floor is an undeclared precondition with no probe;
the transport a document takes — and therefore whether it leaves the host — is decided by
whether its PDF happens to carry a text layer; the extraction fork (regex for text,
vision model for scans) has no principled home; and probabilistic output flows into a
filing engine with no declared boundary at which it becomes reviewable data.

A decision is needed now because a proposal exists to lift the path into a separate
package, and the naive form of that proposal would move the code most likely to write a
temp file to the one place where the gates forbidding temp files do not look. What gets
decided here is the boundary's shape, not whether inference is worth having.

## Considerations

- The motivating claim that this decouples the product from `torch` is already satisfied.
  `2026-06-15-dependency-provisioning-adr` §4 relocated torch to `[dependency-groups] dev`
  as the vaultspec-rag backend; no `src/cadrumo/` runtime path imports it. The live
  argument is prospective: a transformers- or vLLM-served model would put a model runtime
  back in-process, and the product currently ships none (`pyproject.toml:181-187`, the
  retired `search` extra).
- Every AST gate enforcing secure-storage-only persistence derives its corpus from
  `SRC_CADRUMO`, hard-coded as `src/cadrumo` in `src/cadrumo/tests/_inventory.py:11`. Code
  in a sibling top-level package is invisible to all five. **But the five do not share one
  mechanism, and the difference is load-bearing** — see the fail-open finding below.
- `.importlinter:2` sets `root_package = cadrumo`, so a sibling package is outside the
  import graph entirely. **A subpackage is inside the graph but is not thereby inside any
  contract**: `cadrumo.llm` appears in none of the five declared contracts, and the
  `layers` contract sets `exhaustive = false`, so an unlisted top-level subpackage is not
  flagged. Graph membership and contract membership are different properties and an
  earlier draft of this record conflated them. `aeat-architecture-boundaries` independently
  forbids new top-level packages.
- **The layering leg of the Option-B argument is therefore work, not inheritance.** A
  subpackage does not acquire a layering constraint by existing. Worse than neutral: with
  `cadrumo.llm` absent from every `forbidden_modules` list, `cadrumo.core` or
  `cadrumo.domain` importing the optional inference package would be caught by nothing — a
  hole that exists for no current package. Enrolling `cadrumo.llm` is a precondition of the
  boundary this ADR draws, not a confirmation of it.
- **The strictest gate tier fails open, and this relocation is the event that exercises the
  failure.** `_SENSITIVE_SURFACES`
  (`adapters/persistence/storage/tests/test_sensitive_persistence_policy.py:24-42`) is an
  enumerated tuple, not a walk. The iteration at `:353-354` feeds each entry to
  `non_test_python_files_under` (`src/cadrumo/tests/_inventory.py:142-150`), which filters
  an rglob — so **a surface path that does not exist, or that has been emptied, yields the
  empty tuple with no error, no warning and no failure.** There is no existence check, no
  `is_dir()`, no non-vacuity assertion anywhere in either file. A named entry pointing at an
  empty directory is indistinguishable from a named entry pointing at clean code: the
  instrument cannot tell you it lost a surface. Moving modules out of
  `adapters/outbound/llm` empties that entry; enrolling `src/cadrumo/llm/` before the
  directory exists enumerates a path that iterates nothing. Both pass green.
- `EvidenceInput`'s tripwires (`_evidence_input.py:118-146`) block serialization, not
  attribute reads; `instance.data` returns decrypted bytes freely.
  `AttachmentStoreProtocol` is structural, so satisfying it proves call shape, not
  custody. The type system cannot carry this boundary.
- The optional-extra machinery is mature and uniform: `core/_optional_extras.py`,
  `require_optional_extra` at each adapter's lazy import, and the CLI degradation seam
  `_surface_for_import_failure` (`entrypoints/cli/__init__.py:907-947`).
- `2026-06-28-product-packaging-adr` fixes an exact-version three-distribution cohort and
  keeps optional integrations as capability extras, whose absence must yield install
  guidance rather than `ModuleNotFoundError`.
- Nothing outside the ledger uses the cloud subprocess transport; `src/cadrumo/agent/` has
  zero references. The on-host vision path reuses the shared prompt/parse machinery but
  does not depend on the cloud path.
- The cloud path is nonetheless the only way to classify a text-layer PDF today.
- No hardware-capability probe exists anywhere in the product.

- **Structured XML parsing is measured, and it wins decisively on latency, cost and failure
  mode.** Recomputed from `harness/results/v5-structured-rescore.json`, whose embedded
  `ground_truth_sha256` is key `e2db6a49...`: of 102 parsed rows, 56 carry a non-null truth
  and return **82.1% mean field accuracy**. Parse latency is **jittery across passes and must be
  quoted as a range**: median **0.59-0.93 ms**, worst **70-164 ms** (v5 0.593/70.28, v4
  0.815/106.28, pre-v4 0.926/163.61). The **86.8 ms** worst-parse an earlier draft quoted appears
  in no artefact and is withdrawn as phantom; so is any point value, which misrepresents a
  metric this unstable. Zero VRAM, no licence exposure. Per format: ZUGFeRD 88.5% (n=20),
  Facturae 88.8% (n=17), UBL 100% at n=2, too small a cell to carry weight. An earlier 88.2%
  over 53 documents, and the claim that ZUGFeRD and UBL were both exact, remain withdrawn;
  they were scored against an unstamped pre-v4 key.
- **The accuracy comparison against the vision models is real but rests on three documents,
  and that caveat is now attached to it.** The vision figures do reconcile against the same
  key and the same metric - mean `accuracy_present` over ten scored fields, which is exactly
  what the 82.1% is - so the comparison is not apples-to-oranges in its measure: `qwen2.5vl:3b`
  returns **75.8% at a 4.81 s median** and `qwen3-vl:4b` **78.8% at 17.23 s**, with
  `qwen3-vl:2b` at 75.8% / 15.59 s, `Nanonets-OCR2-3B` at 71.7% / 37.59 s and `moondream` at
  4.2%. What an earlier draft omitted is the **cell size**: each `vis-*.json` run covers
  **three documents** (`qwen3-vl:4b` only two, its third being a `CALL_FAILED`), against 56 for
  the structured path. A 6.3-point margin measured over three documents is not a result, and
  this record does not treat it as one.

  **D7 therefore claims no accuracy advantage.** It was already re-based onto fail-loud
  behaviour, latency and zero marginal cost, each independently sufficient and each measured
  on a cell that can carry it; the accuracy line is retained for completeness with its
  n stated, not as a supporting argument. A later reader must not restore it to load-bearing
  status without a vision run at comparable scale, which is a cheap and well-specified thing
  to do and is named in the research as an offline procedure.
- **The residual shortfall is a diagnosed and located parser defect, not a format limit.**
  Two causes account for the bulk: the parser selects the wrong tax identifier, taking a
  French SIRET or German Steuernummer where the truth holds the VAT number - which is why
  ZUGFeRD, a Franco-German format, carries 22 of the 34 wrong fields with zero missing ones
  - and it swaps emisor and destinatario on received-invoice SII records. Both are one-edit
  fixes. This is a stronger claim than the assertion it replaces: the shortfall is not
  merely fixable in principle but pinpointed, whereas a model's misread digit is not fixable
  at any cost.
- **A parser fails loudly; a model fails silently - and this was observed, not asserted.**
  One corpus document refused with `ParseError: junk after document element` and produced no
  record at all. A model handed the same bytes would have returned a confident, plausible,
  wrong invoice. For a filing product this axis matters more than the accuracy gap does.
- **The latency advantage is a range, not a single multiplier, and every figure below names
  its numerator, denominator and statistic.** All recomputed from the v5 artefacts under key
  `e2db6a49...`; each model figure is its own median wall time, and each structured denominator
  is named.
  - Against the application's **default** vision model (`qwen2.5vl:3b`, median 4.81 s):
    **~5,200-8,100x** (4.81 s over the 0.926-0.593 ms median range).
  - Against the **slowest measured** model (`Nanonets-OCR2-3B`, 37.59 s): **~40,000-63,000x**.
  - The **honest floor** - the worst observed parse against the fastest model, the least
    favourable framing available: **~29-68x** (4.81 s over the 164-70 ms worst-parse range;
    68x is the like-for-like v5 pairing, 29x crosses passes and is the more conservative).

  Three corrections and one reconciliation ride here. A previously quoted flat "20,000x" was
  derived from mid-range models and a superseded median, and stays withdrawn. The "~29,000x
  against the **slowest tested**" is **mislabelled, not miscomputed**: ~29,000x is the correct
  multiplier against `qwen3-vl:4b` (17.23 s), but that is not the slowest -
  `Nanonets-OCR2-3B` is. And the "~55x honest floor" was computed from the phantom 86.8 ms.

  **The ~5,200x / ~8,000x disagreement between the harness reports and this ADR is reconciled,
  not an error, and must not be "corrected" in either direction.** Both anchor to real observed
  passes and differ only in denominator: 4.81 s / 0.926 ms (pre-v4 median) = 5,194x, and
  4.81 s / 0.593 ms (v5 median) = 8,118x. Each is right about its own pass, which is exactly why
  the figure is stated as a range.
- **The core already carries hardened XML parsing.** `defusedxml>=0.7.1,<1` is a declared
  `[project.dependencies]` entry (`pyproject.toml:55`) with existing production consumers
  (`application/filing/_export_xml_dictionary.py:34`,
  `domain/calculations/registry/_export_parse.py:13`). An exact XML read costs no new
  dependency, no model, no GPU and no extra.
- **No e-invoice parser exists today**, confirmed at HEAD by targeted search:
  `zugferd|factur-x|facturae|en16931|ticketbai|CrossIndustryInvoice` returns no production
  match in `src/cadrumo`. `MediaKind` remains `PDF` and `IMAGE`
  (`application/ledger/_evidence.py:108-112`), so the ZUGFeRD corpus fixture - a complete
  machine-readable invoice - is read as rendered prose and, carrying a text layer, takes
  the cloud branch.
- **Live local inference destabilised the development host**, terminating four concurrent
  agent sessions during this campaign. Recorded factually rather than as a model-quality
  claim: it is evidence about placement. Inference embedded in the core is carried by every
  developer environment, every test run and every CI lane; behind an opt-in extra it is
  absent from the default build, test and development loop. This benefit lands on the day
  the extra ships, independent of the licence and privacy arguments.
- **The internal pipeline shape is unmeasured.** The stage-1/stage-2 isolation run never
  happened. No decision here may depend on it.

- **Operator ruling, 2026-08-06: the inference subpackage is exempt from encryption.** The
  reasoning is that a user who points a *local* tool at a file has by that action accepted
  the file will be processed, and that the security lanes govern how data is STORED inside
  Cadrumo rather than what a local processor reads. This is a clarification of
  `sensitive-financial-data-secure-storage-only`'s existing scope, not an exception carved
  out of it: that rule already permits decrypted bytes to exist "transiently in process
  memory" and binds only persistence. In-memory reading, rasterising and local inference
  therefore need no encryption and no consent gate.
- **The same rule enumerates what the exemption does not reach**, and it does so in terms
  that bear directly on an inference path: "no temp files, no scratch directories, no
  plaintext side stores, no on-disk caches, no logs." An on-disk cache is named explicitly.
  The rule's own worked failure is this exact shape - an early draft designed a
  decrypted-temp-file route for subprocess CLI agents and the operator rejected it - so the
  encryption exemption for in-memory bytes cannot be read as reopening the temp-file
  question.
- **Exemption from encryption and exemption from gate coverage are different claims, and
  only the first was ruled on.** The gates are not an encryption mechanism; they are an AST
  scan for `write_text`, `write_bytes`, `NamedTemporaryFile`, `mkstemp` and
  envelope-bypassing calls
  (`adapters/persistence/storage/tests/test_sensitive_persistence_policy.py:24-57`). They
  are the instrument that *establishes* the persists-nothing property the exemption relies
  on. Removing the code from their scope would convert an enforced property into an
  unverified assertion.
- **`adapters/outbound/llm` is today an explicitly enumerated sensitive surface** in that
  gate's `_SENSITIVE_SURFACES` list, verified at HEAD. The modules this ADR relocates are
  currently under the gate's strictest tier, not merely inside its general walk, so moving
  them outside `src/cadrumo/` would drop a named entry rather than lose incidental coverage.
  **The converse does not follow, and an earlier draft of this record asserted it.** Under
  the fail-open behaviour above, Option B *as naively sequenced* loses coverage exactly as
  silently as Option A would — a dropped entry and an emptied entry are the same observable.
  What distinguishes the two options is not that Option B preserves coverage automatically
  but that Option B leaves coverage **recoverable by an assertion that can be written**,
  because the code is still inside the scanned root. Option A puts it beyond any assertion
  short of re-scoping the gates. That is a real difference and it is the one the knockout
  criterion rests on — but it obliges this ADR to write the assertion, which D11 does.
- **The local path depends on an external daemon Cadrumo does not control.** Base64 page
  images are handed over HTTP to Ollama, which may keep its own logs, history or model
  cache entirely outside Cadrumo's storage. Recorded as a known property of depending on an
  external local runtime rather than as a security objection: it is on-host, it is what the
  accepted local-reading posture already chose, and the operator ruling covers it. It is
  named so the decision is made with it visible and so a later reader does not mistake
  "local" for "contained within Cadrumo's storage guarantees".

## Considered options

- **A — sibling top-level package `src/cadrumo_llm/`, separate distribution.** Matches the
  proposal's literal wording. Gives the strongest dependency isolation. Rejected: it
  breaches `aeat-architecture-boundaries`, escapes every layering contract, and — decisively
  — removes the inference path from all five secure-storage AST gates precisely when that
  path is the one handling decrypted invoice bytes.
- **B — gated subpackage `src/cadrumo/llm/` behind an `llm` extra (chosen).** The code stays
  inside the scanned root and inside the import graph; the dependency closure is isolated by
  the extra, which is the mechanism the project already uses for five integrations. The
  distribution split remains available later without moving code. **Stated precisely, since
  an earlier draft overstated it:** B does not inherit gate coverage or layering coverage.
  It inherits the whole-tree rglob checks automatically, and it makes the enumerated-surface
  coverage and the layering contract *achievable by enrolment* (D11, D12) where Option A
  makes them unreachable without re-scoping the instruments themselves. The advantage is
  real and it is the knockout, but it is an advantage in what can be enforced, not in what
  is enforced for free.
- **C — leave the path where it is, add a hardware probe and fix the transports.** Solves
  the hardware and privacy findings without a boundary. Rejected: it leaves probabilistic
  inference undifferentiated inside the deterministic core, so the licence and
  quarantine problems remain, and nothing prevents the next model dependency from landing
  in the base closure.
- **D — subpackage now, separate distribution later as a fourth cohort member.** Not a
  rival to B but its sequel; recorded so the ADR's scope is explicit. Deferred, with the
  gate re-scoping named as its precondition.

## Constraints

- The gates are the boundary. Wherever the inference code lives, `SRC_CADRUMO`-scoped AST
  scanning must cover it. A future distribution split is conditional on re-scoping those
  gates first, in the same change.
- **A control must be able to fail at the point it is applied.** A surface enumerated before
  its directory exists, an import contract naming an absent module, and an AST assertion over
  an empty path all report success. Every control this ADR relies on is therefore proven by
  mutation — introduce the violation, observe red, revert — and scheduled where that proof
  can actually run. This is a constraint on execution, not a preference about rigour: the
  encryption exemption of D9 is valid only while the controls establishing the
  persists-nothing property exist, so a control that silently checks nothing invalidates the
  exemption while appearing to support it.
- **Nothing that names `cadrumo.llm` may land before `cadrumo.llm` exists**, with one
  deliberate exception in the other direction: the sensitive-surface enumeration lands in the
  same atomic commit that creates the directory, because the interval between creation and
  enumeration is unguarded.
- Decrypted evidence bytes stay in process memory and never persist outside secure storage
  (`2026-06-10-llm-evidence-classification-adr`, operator ruling, binding).
- `llm-selects-system-derives-tax-numbers` is unaffected: the regulated figures remain
  registry-derived regardless of which package reads the document.
- Extras absence must degrade to install guidance, never `ModuleNotFoundError`
  (`2026-06-28-product-packaging-adr`).
- Retiring the cloud path removes a live capability; sequencing is a constraint, not a
  preference.
- Frontier risk is low: no new library class is introduced. The one novel element is a
  hardware-capability probe, for which no in-tree precedent exists.

## Implementation

**D1 — the package boundary.** The inference path moves to `src/cadrumo/llm/`, a
subpackage of the existing root, gated by a new `llm` extra registered as an
`OptionalExtra` in `OPTIONAL_EXTRAS` (not hand-rolled like the `agent` extra, which sits
outside the shared classifier and is a precedent to avoid). The extra declares the
runtime packages the path actually needs. Guarding follows the established convention:
`require_optional_extra(LLM_EXTRA)` immediately before the lazy import, at the adapter
boundary, converted to a domain error.

**The Pillow finding, stated at its true strength.** An earlier draft of this record
implied Pillow does not reach a default install. It does: `pdfplumber` and `pikepdf` are
both unconditional `[project.dependencies]` entries and both declare Pillow, so
`bitmap.to_pil()` resolves in a clean production install and the on-host vision path works
as shipped. `pypdfium2` is likewise declared, not undeclared. What is real is narrower and
still worth fixing: Cadrumo imports `PIL` **directly** while declaring it nowhere but the
dev group, so a direct reliance is carried by another package's incidental transitive. The
project has already reasoned through this exact class and written the reasoning down for
`lxml` at `pyproject.toml:40-47` — *"incidental supply for a direct reliance… Declaring it
turns that into a resolution failure instead"* — and then did not apply it to Pillow. The
remedy that matches the precedent is a **direct `[project.dependencies]` entry carrying the
same comment rationale**, in addition to the extra's declaration; the extra alone is
correct but not load-bearing, since pdfplumber and pikepdf keep Pillow in the base closure
regardless. The failure this prevents is also a misdiagnosing one:
`rasterise_pdf_pages_to_base64_png` wraps its render loop in a bare `except Exception` and
re-raises as `LLMPdfRasterisationError`, so a missing `PIL` presents as a broken PDF rather
than a missing dependency — the campaign already carries a Step to fix that remediation
text. This is a **latent** defect, not a live break, and it is recorded as the ADR's
cleanest worked example of why an implicit boundary fails: an inference-path dependency was
consumed directly and never declared, surviving only on another package's transitive. An
explicit extension boundary forces every inference-path dependency into the open, which is
precisely the class of error that produced it.

**D2 — the distribution boundary is deferred, not decided.** The extra isolates the
dependency closure, which is what the prospective torch argument requires. Splitting a
fourth distribution later is permitted only in a change that first re-scopes the five AST
gates to cover the new root. Recording this as a precondition is the point of the
decision.

**D3 — the persistence boundary: the extension holds no storage handle.** (Framing refined
by D9 and D10 below, which record the operator's encryption ruling; the substance here is
unchanged and confirmed by it.) The inference subpackage never
resolves secure storage itself. It receives already-resolved bytes in memory from the
core, and returns a typed result; it holds no repository handle, constructs no
`AttachmentStore`, and imports nothing from `adapters.persistence`. This is a discipline
enforced by the gates and by an import contract, not by the type system — the research
established the type system cannot carry it, since both `EvidenceInput.data` and a
structural `AttachmentStoreProtocol` hand over bytes freely. The three inference-scoped
stores that today write through `secure_object_repository_for_active_bucket`
(`_cache.py`, `_run_telemetry.py`, `_usage.py`) stay on the core side of the boundary,
which also preserves `application/diagnostics_run_health.py:71` — a core, non-ledger
consumer of run telemetry that must not become conditional on an optional install.

**D4 — the output shape is a typed validated payload, never free text.** The core accepts
a single strict model (`extra="forbid"`, closed key set, `STRICT_FROZEN_CONFIG`) and
refuses a malformed one at the boundary rather than coercing it. Markdown or raw model
text may exist *inside* the extension as an intermediate, but it is never the interchange
value: handing free text to the core would make the boundary a laundering channel rather
than a validation point, and the ingestion research established that promoting hostile
document text across a stage boundary is where prompt injection gets worse, because
extraction fields have no allow-list the way classification categories do. Every field
carries the shape-grounding the vision path already applies (checksum-valid tax id,
parseable date, finite decimal), and the payload carries its own provenance: `legal_refs`
and `source_refs`, the typed source kind, and the model identity and revision that
produced it, so a persisted record can always answer how each field was recovered.

**D5 — the cloud subprocess path is deleted, sequenced behind local text inference.**
Under a local-only extension the cloud branch is the only inference left inside the
deterministic core and the only path able to send taxpayer documents off-host, which is
the inversion this ADR exists to remove; `no-legacy-compatibility` forbids keeping it
dormant as a bridge. But it is today the only reader for text-layer PDFs, so the deletion
lands *after* a local text reader is wired, not before. The orphan set is then removed in
one change: `cloud_evidence_read_permitted`, `ServiceCapability.CLOUD_EVIDENCE_UPLOAD` and
its `resolve_capability` branch, `cadrumo_evidence_gestor_mode` and
`cadrumo_evidence_cloud_upload_permitted`, `--evidence-acknowledged`, `--llm`, the
subprocess builder family, `probe_subprocess_providers`, and `aeat app ledger providers`.
The shared prompt/parse machinery survives untouched because the local vision classifier
already reuses it.

**D5 narrows an accepted decision, and this record says so rather than leaving the corpus
self-contradictory.** `2026-06-10-llm-evidence-classification-adr` is `status: accepted` at
HEAD and its title is literally *"on-host/local-first reading; cloud only behind a consent
gate"*. Its **ruling 2** sanctions a cloud read behind that gate. D5 deletes the gate and
the capability behind it, so ruling 2 is **superseded in part by this record** — not
reinterpreted, not quietly outgrown. Leaving both accepted would put two ratified records
in the corpus, one sanctioning a capability the other deletes, which is exactly the
ADR-vs-ADR conflict `vaultspec-curate` exists to catch. The narrowing is in the spirit of
that ADR's own headline rather than against it: it makes the on-host posture uniform across
document formats instead of conditional on whether a PDF happens to carry a text layer, and
it removes the gestor bar that applied to one arm of the fork and not the other. Two
mechanical consequences ride with it and are authorised here rather than discovered in
execution. That ADR's status is amended to record the partial supersession in the same
change that lands the deletion, not afterwards. And the `llm:<provider>:<model>` provenance
stamp changes meaning: with the cloud providers gone, the provider axis collapses to the
local runtime, so every stamp a classification writes after D5 names a local provider. The
stamp's **shape** is unchanged and no persisted record is rewritten — pre-existing records
keep the provider they were stamped with, which is the honest history — but a reader who
assumes the axis is still multi-valued would be wrong, and the field's documentation is
updated to say so.

`2026-06-13-llm-evidence-classification-adr` binds the default local vision model to a
consumer-hardware constraint. That constraint governs the local **text** model D5's
sequencing requires as well; the choice is made under it, not beside it.

**D6 — the third capability axis.** The product distinguishes *installed*
(`OptionalExtra`) from *permitted* (`ServiceCapability`); it has no notion of *capable*.
The extension declares a hardware floor and a probe reporting it through the existing
`DependencyStatus` shape into `aeat config check`, so an under-specified machine gets a
typed refusal naming the shortfall instead of a model that fails to load or thrashes.

**D7 - exact structured-document reading stays in the deterministic core, outside the
extra.** Parsing an e-invoice that already carries a structured record is deterministic,
exact and model-free, so it is not inference and does not belong behind an inference
boundary. A `DocumentShape` probe and parsers for EN16931 in both syntaxes (CII and UBL,
covering ZUGFeRD / Factur-X) and for Facturae 3.2.x land in `src/cadrumo/`, available on a
default install with no extra enabled, using the already-declared `defusedxml`. The
extension is thereby scoped to what genuinely needs a model: documents carrying no
structured record.

This is a refinement of the boundary this ADR draws, not a widening of it. The routing
order is itself a control and must be recorded as such so a later agent optimising for
latency does not discard it: a document carrying a structured record reaches **no model at
all**, which makes prompt injection categorically impossible for that document rather than
merely mitigated. The corresponding hazard moves rather than disappears, and is bounded
here - XML parsing runs with entity resolution and external DTD loading disabled and with
size and depth bounds, which is what `defusedxml` is for.

D7 also fixes the inversion D5 addresses from the other end. Today the most
machine-readable invoice format in the corpus is the one whose bytes leave the host,
because it happens to carry a text layer. Under D7 it is read exactly, on-host, by a
default install, with no consent gate and no gestor bar, because no model is involved.

**The parsers land in `src/cadrumo/adapters/inbound/`, not in `application/ledger/`.**
Reading an externally-authored document format is inbound-adapter work, and the tree
already carries seven sibling packages doing exactly that — `pdf/`, `financial/` (the
CSV/XLSX/OFX/QFX/TSV providers), `borrador/`, `censo/`, `declaracion/`, `justificante/`,
`sanitizer/`. `aeat-architecture-boundaries` mandates the separation, and a record whose
subject *is* a boundary decision cannot put format parsing in the application layer without
contradicting itself. The `DocumentShape` probe travels with them, since deriving a shape
from content bytes is the same kind of work. `application/ledger/` keeps what it already
owns: resolving evidence, calling the reader, and carrying the result to the confirm
boundary. Placing them correctly now is also materially cheaper than moving them later,
because `aeat-architecture-boundaries` requires a relocation to land as one atomic
explicit-path commit.

**The record the parsers produce is the extraction draft, extended to carry lines.** An
earlier draft of this plan said "the typed invoice record" — a phrase with no referent, and
both available readings were defective. The parsers produce an **`InvoiceDraft` extended
with a line set and a per-rate IVA breakdown**, and that draft crosses
`confirm_invoice_draft_from_evidence` unchanged. They do not write `Invoice` directly:
doing so would bypass the confirm boundary, which is where the sibling ADR's D-K
plausibility gate lives and where this ADR says it must stay. The extension is required
work in this campaign rather than an optional refinement, because a nine-flat-scalar draft
structurally cannot hold a per-rate breakdown, so an exact parser feeding it would land as
a producer of the same collapsed scalars the regex path already produces — the multi-rate
silent collapse would survive a campaign whose whole claim is that the structured path is
exact. It is also the deliverable the sibling campaign's D-G reader half is waiting on:
`Invoice.lines` and the M303 per-line aggregation already exist, so no persisted-schema
change is authorised or needed on either side of the seam.

Three further consequences follow that this ADR authorises. The vacuous ZUGFeRD assertion
(`application/ledger/tests/test_evidence_corpus_parsing.py:36-38`, which asserts only that
a German word appears) is replaced by an exact-field assertion against the fixture.

**The front door opens for the formats the parsers read.** `MediaKind` is derived at **two**
closed sites, not one, and an earlier draft named only the first: `_media_kind_from_mime`
(`_evidence_input.py:149-159`) is the read-time gate, while `_resolve_media_kind`
(`application/ledger/_evidence.py`) is the **ingest-time** suffix gate on
`evidence add --file`, refusing anything outside `.pdf` and eight image extensions. Left
alone, a standalone Facturae XML — one of the two formats this ADR adds a parser for — is
still refused at the front door and becomes readable only if it happened to arrive through
`doclink` or `pull-folder`. That is the campaign's own named pitfall: a deliverable that
ships correct, tested and unreachable. Both sites move to `DocumentShape` together. The
`_DEFERRED_ADR_REF` string in that refusal goes with them: it points operators at an
`evidence-source-expansion` ADR that does not exist, and it breaches *Code Stands Alone* by
citing a vault stem from source. **This record discharges that deferral** — the
`DocumentShape` taxonomy replacing `MediaKind`, the XML formats, and the accept-then-refuse
fix are the decisions the owed ADR was owed for, and they are made here.

**The accept-then-refuse residue is named rather than implied closed.** The trap —
documents stored through `doclink` / `pull-folder` and then unreadable forever — is closed
for the XML formats by making them readable rather than by tightening the ingest gate. It
is **not** closed for CSV, XLSX, plain text or `.eml`, which remain storable and
permanently unreadable. This ADR does not fix those and does not pretend to; they are
recorded under *Deliberately out of scope* so a later reader does not mistake the XML
closure for a general one.

**D8 - the internal pipeline shape is explicitly left open.** Whether the extension reads
a document in one shot or normalizes to markdown first and extracts second is **not
decided here**, because it was never measured: the isolating run did not happen. Every
decision above stands on the packaging, trust-boundary, output-shape and routing evidence
and none depends on the stage count. Adopting a two-stage shape on the strength of
one-shot measurements would repeat the conflation this campaign exists to break, and it
carries a known cost - promoting hostile document text across a stage boundary is where
prompt injection gets worse, since extraction fields have no allow-list the way
classification categories do. The settling measurement is specified in the research as an
offline procedure to run with the fleet quiesced; it is a precondition of any future ADR
adopting two-stage, not of this one.

**D9 - the encryption exemption, and the one line it does not cross.** Per the operator
ruling of 2026-08-06, the inference subpackage is **exempt from encryption for in-memory
processing**. It may receive decrypted bytes, hold them in memory, rasterise them, base64
them, and hand them to a local model, with no encryption and no consent gate. This
supersedes nothing in D3; it confirms D3's substance and corrects its framing. D3 already
required that the subpackage hold no repository handle, construct no `AttachmentStore` and
resolve no secure storage - which is precisely "receives bytes in memory and persists
nothing." The ruling makes that the *reason* rather than a restriction.

The rule in one line: **exempt from encryption for in-memory processing; anything persisted
goes back to the core's secure storage.**

Because omission is how this will go wrong in implementation, the persistence side is
enumerated rather than left to inference. Each of the following is storage, not processing,
and each returns to the core's encrypted bucket-scoped secure object repository:

- **The extracted-document cache.** Memoising the deterministic text extraction so
  re-classification need not re-run it is a design this ADR wants - the research records
  that nothing between raw bytes and a persisted record is stored today, which is why every
  operation re-does everything. But that cache holds invoice contents in plaintext. On disk
  in the clear it would be a **new plaintext store of taxpayer financial data that does not
  exist in the tree today**. It is written through the core, content-addressed and
  encrypted, and `sensitive-financial-data-secure-storage-only` names "on-disk caches"
  explicitly. **It is deliberately not called a *normalization* cache.** An earlier draft
  used that name, which presupposes a normalize-then-extract separation - i.e. exactly the
  two-stage shape D8 refuses to adopt for want of a measurement. What is cached here is the
  deterministic extraction of a document's text, which exists under either pipeline shape;
  the naming is corrected so no Step's title asserts a decision the ADR says is open.
- **Rasterised page images.** A rendered page is the invoice. No page raster reaches disk in
  the clear, including as an intermediate.
- **Debug dumps and temp files.** None, in any form, at any log level. The subpackage has no
  diagnostic escape hatch that writes cleartext.
- **Extracted field drafts.** The `InvoiceDraft` equivalent is derived financial data.
  Persisting it is storage and routes through the core.

**D10 - the subpackage stays under the persistence gates, and this is not what was
exempted.** The ruling settles the *data* question and does not move the *code-location*
question, because the two rest on different mechanisms. The gates do not encrypt anything;
they are an AST scan that detects a write. They are therefore the instrument that proves
the persists-nothing property D9 depends on, and `adapters/outbound/llm` sits in their
explicitly enumerated sensitive-surface list at HEAD.

The reasoning would be circular the other way round: the subpackage may sit outside the
gates because it persists nothing, but the only thing establishing that it persists nothing
is the gates. The research further established that no alternative enforcement exists - the
type system cannot carry it, since `EvidenceInput.data` returns decrypted bytes freely and
`AttachmentStoreProtocol` is structural, so satisfying it proves call shape rather than
custody.

D9's own carve-out list is the strongest evidence for D10. Every item on it is something an
inference path actively *wants* to write, and the operator explicitly wants the
extracted-document cache built. A component under standing pressure to persist is exactly the
one that must stay under the scan, not the one that has earned an exemption from it. The
simplification the ruling delivers is therefore real but lands on the data axis: no
encryption, no consent gate, no custody ceremony for in-flight bytes. Option A remains
rejected on its original knockout criterion, and D2's precondition stands unchanged - a
future distribution split is permitted only in a change that first re-scopes the gates to
cover the new root.

**D11 - the enumerated gate tier is made non-vacuous before anything relies on it.** Every
entry in `_SENSITIVE_SURFACES` must resolve to at least one non-test Python file, or the
gate fails naming the entry. This does not exist today, and without it the strictest tier is
a fail-open control: a surface that is deleted, renamed, emptied by a relocation, or
enumerated before it exists reports success identically to a surface that is clean.

The decision is scoped deliberately wider than this campaign. The assertion protects **all
eighteen enumerated surfaces**, not the inference one, and it is what makes Option B's
enforcement claim true rather than merely intended. It lands **first**, before any Step that
creates or empties a surface, because a campaign that relocates code across two named
surfaces is exactly the event that exercises the failure mode, and an instrument repaired
afterwards proves nothing about the interval. The assertion is itself proven by mutation:
point an entry at a nonexistent path and the gate must red. A gate that cannot be made to
fail has not been shown to work.

D11 also fixes the order of two Steps that an earlier plan got backwards. The surface is
enumerated in the **same** change that creates the directory, never earlier; and the
mutation proof that the gates reach the new code runs **after** the code exists, targeting
the enumerated tier specifically rather than the whole-tree rglob tier, which was never in
doubt.

**D12 - `cadrumo.llm` is enrolled in the layering contract, which it does not inherit.** The
subpackage is added to the `layers` contract's layer list, and to the `forbidden` contracts
that must catch a `core` or `domain` module importing the optional inference package. Today
nothing would catch it, which is a hole no current package has. The enrolment is verified the
only way an import contract honestly can be: introduce a deliberate violating import, observe
import-linter red, revert it.

`exhaustive = true` is **not** adopted here. It would surface a much larger backlog belonging
to no campaign, and taking it as a side effect of an inference boundary would be scope this
record has not earned. The narrower enrolment is sufficient for the property D12 needs.

The layer position follows from D3 rather than from convenience. The extension receives
already-resolved bytes and returns a typed payload; it holds no repository handle and imports
nothing from `adapters.persistence`. It therefore sits at the adapter tier - callable by
application code, forbidden from reaching into persistence, and forbidden as an import target
for `core` and `domain`. The import contract of D3 and the layer enrolment of D12 are two
halves of one boundary: one bars what the extension may reach outward, the other bars who may
reach into it.

**D13 - the evidence-record identity defect is fixed here, because this campaign is what
makes it consequential.** `derive_purchase_invoice_evidence_id`
(`application/ledger/_evidence.py:162-200`) folds `created_at.isoformat()` into the derived
id, so re-running `evidence add` on the same file produces a second `PurchaseInvoiceEvidence`
record with a new id and a second bucket event over one shared blob. That is a direct breach
of `single-subject-mutation-is-idempotent-guarded`, whose text is explicit that *"the record's
identity MUST be clock-free - the timestamp is a non-identity last-seen body field, never
folded into the derived id."* The blob layer is already idempotent (content-addressed) and
the manifest already merges; the evidence record is the one half-idempotent link in the chain.

**The naive fix is wrong and is rejected here.** Reading the derivation at HEAD shows the clock
is deliberate, not an oversight: its docstring states that *"two evidence records for the same
file must keep distinct ids"* and that the `disambiguator` ordinal exists to break a
same-instant collision rather than to collapse a retry. That is a real requirement — the same
invoice PDF can legitimately be attached twice as two distinct pieces of evidence — and simply
dropping `created_at` would silently collapse those genuine duplicates into one record. The
governing rule anticipates exactly this and supplies the shape: a deliberately-additive verb is
`non_idempotent_append` and must document the choice, while a **caller-supplied idempotency
key** makes the guarded path available to callers that need it. The rule's own worked example is
`create_manual_transaction`, which keys on the clock-free `manual:{bucket}:{key}`.

So the fix is **not** "drop the clock" but "add the key": when the caller supplies an
idempotency key the id is derived clock-free from it, a matching re-add returns the existing
record as a no-op emitting no second bucket event and re-stamping no timestamp, and a same-key
re-add whose content differs refuses with an instructive conflict naming the divergent fields.
The keyless path stays additive and keeps its documented rationale. The match must compare
**every** persisted field: the close review of the rule's origin campaign caught precisely the
failure where a no-op match omitting a field silently drops the new value, which would be a
`no-silent-under-declaration` breach wearing an idempotency guard's clothes.

It is fixed **in this campaign rather than deferred** for two reasons that are about this
campaign specifically and not about tidiness. First, D7 opens the front door to new document
formats, which increases the traffic through the exact verb that multiplies records. Second,
the source discovery names it a **prerequisite**: any directory-ingest or resumable batch verb
multiplies evidence records on every re-run, so a defect that is merely annoying at one
document per invocation becomes corrupting at a thousand - and this ADR's own case for the
extracted-document cache is that it *"makes batch and resume cheap."* Authorising the thing
that makes batch cheap while leaving the thing that makes batch corrupting is not a coherent
position — a batch verb has no operator watching each row, so it is exactly the caller that
must be able to pass a key and get a guarded no-op.

## Rationale

Option B wins on a knockout criterion rather than a balance of factors. The purpose of
moving inference out of the core is to contain risk. Option A would relocate the code
that handles decrypted invoice bytes to the only place in the repository where the AST
gates forbidding temp files, plaintext side stores and unreviewed writes do not look, and
where no layering contract applies. That inverts the goal: the most sensitive code would
become the least supervised. No amount of dependency isolation compensates, because the
isolation Option A buys over Option B is a packaging property, while what it gives up is
an enforcement property.

The knockout survives the correction that an honesty review forced on this record, but it is
narrower than first written. Option B does not keep the code supervised automatically; it
keeps supervision **reachable**. Two of the three enforcement legs — the enumerated gate
tier and the layering contract — attach to a new subpackage only when someone enrols it, and
one of them fails open when nobody does. That is why D11 and D12 are decisions rather than
plan detail: without them, Option B's advantage over Option A collapses from "the code stays
supervised" to "the code stays in a directory where supervision would have been possible."
With them, the original claim holds and is now backed by controls that can fail.

Option B delivers what the proposal actually needs. The dependency closure is isolated by
the extra — that is precisely what keeps a future torch-bearing model off a default
install. The licence question narrows to an opt-in component. The hardware floor becomes a
declared property of an installed extra rather than a hidden precondition. The privacy
inversion disappears with D5. And the extraction fork resolves because the extension owns
one reading path rather than two transports chosen by file format.

Option D is not foreclosed. Because the extra already isolates the closure, the
distribution split becomes a mechanical follow-on whenever it is wanted — conditional on
re-scoping the gates, which is the honest price and is now written down rather than
discovered later.

## Consequences

Gains: probabilistic work is quarantined behind an opt-in boundary while remaining under
every gate that protects sensitive bytes; a default install loses no deterministic
capability; the direct-but-undeclared `Pillow` reliance is forced into the open. Two gains
land wider than this campaign and are the clearer wins: D11 converts the strictest gate tier
from fail-open to fail-loud for all eighteen enumerated surfaces, and D12 closes a layering
hole that would let `core` or `domain` import an optional package with nothing to catch it.

The encryption exemption's validity is **conditional on the enforcement actually landing**,
and that is the sentence most worth carrying forward. D9 exempts in-memory processing
because the code persists nothing; the only thing establishing that it persists nothing is
the gates. An execution that enrols a surface before the directory exists, or schedules the
mutation proof where it cannot run, or "confirms" an import contract that has no opinion,
leaves a correctly reasoned exemption resting on controls that do not exist — with every
checkbox closed. D11 and D12 exist to make that outcome impossible rather than merely
discouraged, and the plan's per-Step red conditions are how the outcome is detected if it is
attempted anyway.

Costs, stated honestly. The split line runs through
`application/ledger/_llm_classification.py`, 1606 lines mixing inference with core writes
(`set_classification`, bucket-event history, split persistence, the consent gate); it must
be divided rather than moved, and that division is the largest single piece of work here.
`_llm_review_workflow.py` depends only on the apply/reject functions inside that module,
so it cannot settle until the division does. Deleting the cloud path touches on the order
of two dozen test files, some deletable wholesale and the rest needing case-level edits
because `_resolve_evidence` branches internally. **That count is an estimate this record
could not confirm**: an independent partial symbol sweep at HEAD covering six of the orphan
symbols found 29 files (10 test, 19 production), and a fuller sweep would move the test
figure. The earlier precise-sounding "24 test files, nine deletable wholesale" is
downgraded to the estimate it always was, and the plan counts the modules against a fresh
sweep at execution time rather than against this number.

The regression risk is real and named: between the cloud deletion and a working local text
reader there is a window in which text-layer PDFs cannot be classified at all. D5 sequences
against it, and the plan must not reorder those steps for convenience.

The pitfall most likely to bite is not architectural but procedural. The
`llm-invoice-read-reconciliation` research records three deliverables that shipped correct,
tested and unreferenced, because a unit test passes whether or not anything calls the code.
A package migration is that failure mode at larger scale: every moved module can be green
while the core still routes around it. Each step needs an enrolment gate proving the core
call site reaches the moved code — not merely that the moved code works.

D7 changes the shape of the win. The most exact ingestion path becomes a default-install
capability rather than an opt-in one, so a taxpayer who never enables the `llm` extra still
gains exact reading of every structured e-invoice they receive - which, for a business
subject to VeriFactu, is every invoice it issues. The extension's remaining scope narrows
honestly to documents that carry no structured record.

The limits must be stated rather than glossed, and they are narrower than any earlier draft
of this record claimed. **D7 rests on no accuracy margin.** The measured margin is 82.1%
against 75.8% for the default vision model, on the same metric and the same key — but the
structured cell is 56 scoreable documents and each vision cell is **three**, so a 6.3-point
gap across them is within the noise a three-document sample can produce and cannot bear
weight. An earlier draft quoted an accuracy margin twice as a supporting argument, first from
a pre-v4 unstamped key and then without its cell size. The figure is retained above with its
`n` attached; the argument built on it is withdrawn.

What D7 rests on instead is three properties, each independently sufficient and each
measured. It **fails loudly**: one corpus document refused outright with a `ParseError` and
produced no record, where a model would have returned a confident wrong invoice. It is
**three to five orders of magnitude faster**, from ~68x at the least favourable framing to
~63,000x at the most. And it costs **nothing marginal** in dependency, hardware or licence
terms, running on a `defusedxml` the product already ships. None of the three is weakened by
withdrawing the accuracy argument, which is why the withdrawal costs the decision nothing —
but the decision must be read as resting on those three, and a later reader must not restore
the accuracy line to load-bearing status without a vision run at comparable scale.

Separately, nothing here establishes what share of documents a real user receives as
structured XML versus as a photograph of a paper receipt. That ratio bounds how much of the
ingestion problem D7 removes, and it was not measured - the corpus was curated, not sampled
from user traffic. The accurate claim is that where a structured record exists the
deterministic path is better on every measured axis, not that structured records are the
common case.

The corpus composition itself **is** confirmed exact against the v5 key, and an earlier verdict
calling these figures untraceable is withdrawn: **130** vision-path documents, **124** of them
scoreable, **107** of those real rather than synthetic, and **28** carrying a non-empty stage-1
reference transcription. They bound what a future measurement could achieve rather than what
this one did: the vision matrix could be re-run at roughly **40x** its current sample size, and
the stage-isolation run that would settle D8's open question is **executable today** and simply
was not run. Both procedures are recorded offline rather than started.

Two instrument caveats ride with the measurement, and both are live rather than historical.
Forty-six of the 102 parsed rows remain unscoreable because the ground-truth key carries no
truth for them. And the hallucination count is **an artefact of those gaps rather than a
property of parsing**, which an earlier draft stated too narrowly: across only the scoreable
rows it is nine, all in ZUGFeRD, but across all 102 rows it is 453 — ZUGFeRD 289, UBL 104,
Facturae 60 — because a row with no truth counts every emitted field as unmatched. So the
claim that the hallucinations are "wholly concentrated in ZUGFeRD" is false at corpus level
and is corrected here. **The hallucination figure must not be quoted in any form** as a
property of structured parsing until the wrong-identifier defect is fixed and the key's gaps
are closed; it currently measures the key, not the parser. The accuracy figures above are
unaffected, being computed only over fields with a non-null truth.

The 34 wrong fields and the zero-missing-fields claim survive scrutiny and are worth pinning
precisely, because they are what make the shortfall diagnosable: of 34 wrong fields
corpus-wide, 22 are ZUGFeRD, and ZUGFeRD's missing count is exactly zero — the parser is
finding every field and choosing the wrong one, which is a selection bug with a one-edit fix,
not a coverage gap.

This record's figures are pinned to key `e2db6a49...`, recomputed from
`harness/results/v5-structured-rescore.json` and the `harness/results/vis-*.json` runs rather
than restated from prose, and any future re-score should restate them rather than assume
continuity. Two successive publications of this ADR carried figures that could not be
reproduced from the artefacts — first from an unstamped key, then from vision numbers with no
artefact at all — which is precisely the failure this pinning exists to prevent, and the
reason the pinning now names the file each figure came from. `harness/RESULTS.md` and
`harness/RECOMMENDATION.md` have not been reconciled against this recomputation and should
not be treated as a second source until they are.

D8 leaves a real question open. The extension can be built, gated and enrolled without
answering it, but the answer will eventually shape the extension's internals, and a plan
executing this ADR must not quietly assume one shape while building the other.

### Dependencies and coordination with the concurrent invoice campaign

`2026-08-06-invoice-canonical-structure-adr` landed in parallel and owns the invoice
stores and the writer surface: it deletes the slim `BusinessOperationInvoice`, extends the
writer to reach retención, recargo, `iva_category`, `invoice_class`, `series` and
`operation_date`, and fixes the one-line synthesis in `build_catalogue_invoice`. That ADR
explicitly defers the ingestion architecture to this one, and this ADR does not decide any
store or writer question. The division is clean and is reaffirmed here rather than
renegotiated.

Three seams genuinely couple the two records, and each is reconciled rather than left to
collide.

**The confirm boundary.** That ADR's D-E extends the operator's override set and its D-F
keeps retención off the extraction draft. Both are framed as assertion-authority questions
(who may assert a fact) rather than as where-extraction-runs questions, so both survive
this ADR's boundary unchanged. This ADR's D4 is the complementary half: whatever the
extension produces arrives as a typed validated payload the core refuses when malformed,
so the confirm boundary receives a validated artefact regardless of which side produced
it. The two are consistent, and no field this ADR authorises the extension to emit is a
field that ADR reserves to the operator.

**The per-rate reader half.** That ADR's D-G fixes mixed-rate invoices at the writer end
and explicitly leaves the reader half out of scope, naming this campaign as the dependency.
D7 supplies it: a structured e-invoice carries its line items and per-rate IVA breakdown
exactly, so `W02` gives the new multi-line writer its first real producer to test against
rather than a hand-built fixture. This is the one place the two campaigns are
load-bearing on each other, and the ordering is that the writer half may land first and
the reader half rides `W02`.

**The plausibility gate.** That ADR's D-K places a confirm-as-ISSUED plausibility check at
the core boundary where a validated artefact arrives, whoever produced it. That placement
is correct under this ADR's boundary and needs no change; it is noted so a later reader
does not relocate it into the extension, where an optional install could disable a
safety check.

One point of deliberate divergence is recorded rather than left implicit. That research
treats the regex-versus-vision extraction fork as an unresolved duplication finding with
no resolution proposed, correctly deferring to this campaign. D7 resolves it in a
direction neither record anticipated: the fork is not settled by choosing between regex
and vision, but by removing most of its traffic, since a document carrying a structured
record reaches neither reader. What remains of the fork applies only to documents with no
structured record, and its resolution is the open pipeline-shape question of D8.

Sequencing note. `W02` touches ingestion and adds no dependency; the invoice campaign's
phases touch the stores and the writer. They do not share files, so they may run
concurrently, but both touch `application/ledger/_evidence_draft.py` at the confirm
boundary. Before a first edit there, run `git diff -- <file>` and abort on non-authored
WIP.

## Deliberately out of scope

The research scoped itself narrowly and legitimately — *what would move, what the move
costs, which boundary the evidence favours*. D7 then annexed a large piece of ingestion
territory. Once a record claims a surface it inherits the duty to say what it is **not**
doing there, and an earlier draft of this ADR carried no such section while the sibling
`invoice-canonical-structure` ADR did. Each item below is a real finding from the source
discovery, dropped on purpose and with a reason, not by silence.

**Ingest hardening — no path sanitizes anything.** `adapters/inbound/sanitizer/` is a
competent PDF hardening pipeline with **zero production call sites**, and its own package
docstring says why: it is fixture-preparation infrastructure, not a runtime ingest guard. So
it is not a mis-wired control and nothing was bypassed — but the consequence stands that an
operator-supplied PDF is stored and later reopened by pikepdf, pdfplumber and the rasteriser
with its JavaScript, OpenAction, embedded files and annotations intact. The realistic
exposure is parser-level rather than script execution, and all three parsers currently fail
loudly on garbage, which is the right behaviour. Wiring sanitization into ingest is a
hardening pass with its own threat model, its own fidelity question (a sanitiser that
rewrites bytes changes the content address the whole evidence chain is keyed on) and its own
regression surface. This campaign **reads** the sanitizer's embedded-file walker to open
ZUGFeRD payloads; it does not wire the sanitizer into ingest. Recorded for its own campaign,
named here so the omission is a decision.

**The remaining accept-then-refuse formats.** CSV, XLSX, plain text and `.eml` stay storable
through `doclink` / `pull-folder` and permanently unreadable. D7 closes the trap only for the
XML formats. Closing it generally means either a reader per format or an ingest-side refusal,
and the second is the option D7 explicitly declined for XML; deciding it for four more
formats needs evidence this campaign does not have.

**Scale verbs.** No directory ingest, no batch extract, no batch confirm, no resume or
checkpoint. D13 removes the blocker that would make any of them corrupting, and the
extracted-document cache removes the cost that would make them slow, so this campaign
deliberately clears the ground for them without building them. `aeat app ledger import`
already accepts a directory for bank statements and is the ready precedent.

**Reader-only field gaps.** Supplier **name** (only the tax id is read, so a supplier whose
NIF fails checksum yields no identification at all), credit notes and rectificativas (no
sign, direction or document-type discriminator, so a rectificativa reads as an ordinary
positive invoice), foreign currency and the FX triple, series, operation date, payment terms,
supplier address and intra-community VAT-ID. These are genuine gaps in what the **regex/vision**
reader recovers. D7 narrows their reach rather than closing them: a structured e-invoice
carries most of these fields exactly, so for any document with a structured record they are
recovered for free by the parsers this ADR authorises. What remains uncovered is the
unstructured path, which is D8's open territory. The operator route also already exists for
the highest-consequence one — `counterparty_name` at confirm and at `catalogue create`.

**Recargo de equivalencia on the extraction draft.** The source discovery assigns the draft
half to the reader campaign, and it *is* printed on the document face, so it is legitimately
readable. It is left out here because it is a field-set question about what the draft
carries, owned by the sibling ADR's D-E override-set decision, and splitting one field-set
decision across two records is how the seam gets lost. The lines-and-per-rate extension D7
authorises is in scope because the sibling ADR's D-G explicitly names this campaign as its
dependency; recargo carries no such handoff.

**The manifest merge discarding the second observation's channel reference.** A documented
limitation of `_merge_with_stored_manifest`: re-ingesting the same invoice from a different
source keeps the first observation's provenance and drops the new one. Real, and adjacent to
D13 — but D13 is about record *identity* and this is about provenance *union* on merge. They
are fixed by different edits and only one of them blocks batch work.

**Generalising `PrintedTotalDiscrepancy` beyond one of three entry paths.** Independent of
the cascade, carried by nothing here.

**The injection-through-markdown regression gate.** Contingent on the markdown stage D8
leaves open. Building a regression test for a stage boundary the ADR refuses to adopt would
be building the two-stage shape by the back door. It is named as a **precondition** of any
future ADR adopting two-stage, alongside the settling measurement.

**The normalized-document seam and its custody discipline.** The source discovery specifies a
single typed `NormalizedDocument` record — source shape, structured record or text, page
count, content address, per-field `from_xml` / `from_text_layer` / `from_vision` provenance —
carrying `EvidenceInput`'s serialization tripwires, on the reasoning that normalized markdown
of an invoice is every bit as sensitive as the invoice. That seam **is** the two-stage shape,
so it rides D8 and is not built here. `DocumentShape` addresses only the shape-probing half,
which is shape-neutral. Two obligations are recorded for whoever does build it: it inherits
the custody tripwires, and it is a **single typed record rather than a tagged union** — the
discovery names the current `_ResolvedEvidence` union as the thing to replace, and rebuilding
a union under a new name would carry the defect across.

## Status note

This record stays `proposed`. The quantitative precondition an honesty review placed on
moving it off `proposed` — a full trace of every figure against the stamped key — **is now
discharged**. Every number was recomputed from `harness/results/v5-structured-rescore.json`
and the `harness/results/vis-*.json` runs rather than restated from prose. Three figures were
**corrected** (worst parse 86.8 ms → 70.28 ms; honest floor 55x → 68x; "29,000x vs the
slowest tested" → 29,000x is `qwen3-vl:4b`, the slowest is `Nanonets-OCR2-3B` at 63,000x),
one was **qualified** (the accuracy margin survives but on a three-document vision cell, so
it no longer carries the argument), one was **widened** (the hallucination count is nine only
among scoreable rows and 453 across all rows, spread over three formats rather than
concentrated in ZUGFeRD), and the rest confirmed to four significant figures.

One methodological note is worth leaving for whoever re-scores next, because it cost a full
wrong conclusion in this pass. Each result row carries **two** accuracy fields —
`accuracy_present` over all ten scored fields, and `accuracy_representable` over only the
fields the app's prompt can express. They differ sharply (`qwen2.5vl:3b` scores 75.8% on the
first and 100% on the second), and reading the wrong one makes the vision models look
flawless and the published figures look fabricated. The structured 82.1% and every vision
figure above are `accuracy_present`, which is what makes them comparable at all.

What remains before acceptance is not measurement but review of the two substantive changes
this trace produced: that D7 carries no accuracy margin, and that the Option-B enforcement
argument required D11 and D12 to become true rather than being true on its own.

## Codification candidates

None. `sensitive-financial-data-secure-storage-only`,
`single-subject-mutation-is-idempotent-guarded`, `no-legacy-compatibility`,
`no-silent-under-declaration` and `aeat-architecture-boundaries` already govern every
decision here; this record applies them rather than sourcing a new one. Codification is
retired by operator directive in any case. D11's non-vacuity assertion is the one durable
lesson worth carrying, and it is carried as an **executable gate** rather than as prose,
which is the stronger form.
