---
tags:
  - '#research'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f4bbf7726ebea996663d31e8bdc310a77aa9bcdcd89020c36565b2fb3b242e11'
related:
  - "[[2026-08-06-llm-invoice-read-reconciliation-research]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
---
# `llm-package-split` research: `Extracting the document-ingestion and inference path into an optional local-inference package`

Can the document-ingestion-and-inference path be lifted out of the deterministic tax core
and shipped as an optional, local-only extension? The question matters because the
inference path is the one part of Cadrumo that is probabilistic, hardware-dependent,
licence-encumbered, and privacy-sensitive, while everything it feeds is a deterministic
filing engine bound by `aeat-safety-legal-gates`. This document establishes what would
move, what the move costs, and which of the two candidate boundaries the evidence
favours. It does not decide; the ADR does.

The headline finding is that the boundary question is really two separable questions —
where the CODE lives and where the DISTRIBUTION splits — and that only the first is
urgent. The evidence also refutes one premise the proposal was resting on, and surfaced
a live shipped defect in the path under discussion.

## Findings

### The torch-decoupling motivation is already satisfied; the honest argument is prospective

The proposal cited decoupling from `torch` as a motivation. That decoupling is done, and
was done deliberately by an accepted decision. `2026-06-15-dependency-provisioning-adr`
§4 records it: torch "is the vaultspec-rag embedding backend — no `src/cadrumo/` runtime
path imports it — yet it sat in `[project.dependencies]` (a ~GB CUDA wheel on every
production install). It is relocated to `[dependency-groups].dev`." The current state
confirms it: `pyproject.toml:302-311` declares torch under `[dependency-groups] dev`
with that rationale inline, `[tool.uv.sources]` pins it to the cu130 index at `:289-292`,
and `[tool.vaultspec-rag] managed-torch-direct-dependency = true` at `:300-301` marks it
as the search tool's dependency. It is absent from `[project.dependencies]` (`:23-80`).

An ADR claiming a present-tense torch burden would be factually wrong. The defensible
argument is prospective and rests on a posture the project already holds: the product
ships **no in-process model runtime**. `pyproject.toml:181-187` records a deliberately
absent `search` extra — "the runtime embedding stack the extra once gated (model2vec,
huggingface-hub, numpy) was retired, so the product ships no semantic runtime and
reaches no model host." Inference today is delegated out-of-process to an
operator-provisioned Ollama daemon over HTTP. A model served by transformers or vLLM
would be the first thing to put a model runtime back inside the process, and torch with
it. The extension boundary preserves that option without ever charging the core for it.

### The split line runs through one module, and it is the largest one

Classifying the candidate set by what each module actually does:

- **Purely inference** (movable as-is): `application/ledger/_evidence_draft_vision.py`,
  `application/ledger/_vision_classifier.py`, and most of `adapters/outbound/llm/` —
  `_client.py`, `_models.py`, `_errors.py`, `_pricing.py`, `_providers/*`, and the pure
  `_retention.py` selection function.
- **Mixed inference and core orchestration** (the split line):
  `application/ledger/_llm_classification.py`, 1606 lines. It holds inference call sites
  (`rasterise_pdf_pages_to_base64_png`, `LocalVisionLLMClassifier`, subprocess classifier
  and split proposer, `LLMRunTelemetryRecorder`) *and* core writes — `set_classification`,
  `BucketEventHistoryRepository` (`:53-54`), `AttachmentStore` over
  `secure_object_repository_for_bucket` (`:261`), the consent gate
  (`cloud_evidence_read_permitted`, `:275`), and split persistence
  (`split_transaction_with_classified_children`).
- **Core with an inference call-out**: `_llm_suggestions.py` (pure strict-frozen DTOs
  over `core`/`domain` only — the natural shared contract), `_llm_review_workflow.py`
  (decision routing; depends only on the apply/reject functions inside the mixed module),
  `_llm_diagnostics.py` (`:43-46`, reads `UsageRecord`/`UsageRecorder` plus the
  transaction catalogue).

Three adapter modules are inference-scoped but write core persistence through
`secure_object_repository_for_active_bucket`: `_cache.py:20` (read `:123`, write `:205`),
`_run_telemetry.py:55` (write `:153`), `_usage.py:20` (write `:119`). They cannot move
without either moving a persistence dependency across the boundary or leaving the writes
behind.

### One hard non-ledger consumer blocks a clean lift of the telemetry stores

`application/diagnostics_run_health.py:71` imports `LLMRunRecord` and
`LLMRunTelemetryRecorder` directly. That module powers the general
`aeat app diagnostics run-health / runs / latency / errors / llm-usage` verbs, which are
not ledger-classification features. So the run-telemetry store has a core consumer
independent of the inference path: moving it into an optional extension would make a
core diagnostics surface conditional on an optional install.

The remaining apparent couplings are not imports and do not force a package dependency:
`core/telemetry/_producers.py`, `_schema.py`, `_http_sink.py` mention the recorder in
docstrings only; `core/errors/registry/_adapters_part2.py:176-245` keys an error table by
string qualname; `core/paths.py`, `_storage_path_definitions.py` and
`_namespace_registry.py` carry `owner="cadrumo.adapters.outbound.llm"` as a string label.
These need re-pointing on a rename, not re-architecting.

### The trust boundary is enforced by AST gates scoped to `src/cadrumo/`, and only there

This is the decisive constraint, and it cuts directly against a separate top-level
package.

Five gates enforce the secure-storage-only posture. `test_sensitive_persistence_policy.py`
carries three: a sensitive-surface AST scan forbidding `write_text`, `write_bytes`,
`NamedTemporaryFile`, `mkstemp` and envelope-bypassing calls across a fixed surface list
(`:24-57`, `:349-369`); a whole-tree file-write inventory asserting every write call site
in production equals a hand-curated reviewed allowlist (`:59-241`, `:386-398`); and a
narrow staging-directory pin (`:411-449`). `test_storage_provenance_gate.py:370-382`
restricts which functions may join onto the storage root.
`test_ephemeral_key_hygiene.py:78-98` guards test-side key isolation.

Every one of them derives its scan corpus from `SRC_CADRUMO`, defined as
`Path(__file__).resolve().parents[1]` in `src/cadrumo/tests/_inventory.py:11` — literally
`src/cadrumo`, walked via `package_python_files()` → `SRC_CADRUMO.rglob("*.py")`
(`_inventory.py:98-109`). Code in a different top-level package under `src/` is outside
that walk. A temp-file write, a plaintext side store, or an unreviewed `write_bytes` in
such a package would be invisible to all five.

That is the exact inversion the proposal must avoid: the code most likely to want a temp
file — an inference path handling decrypted invoice bytes — would be the only code
exempt from the gates that forbid temp files.

The same scoping appears in the layering contract: `.importlinter:2` declares
`root_package = cadrumo`, so a sibling top-level package participates in no layered
contract either. And `aeat-architecture-boundaries` states the rule directly: "Place
Python application code under `src/cadrumo/`. Do not add top-level Python packages,
ad-hoc module roots, or hidden parallel implementations."

**Correction, recorded after a fresh-context review of this record.** The sentence above is
literally true and misleading by implicature: it invites the reading that a *subpackage*
therefore does participate in a layered contract. It does not. `cadrumo.llm` appears in none
of the five declared `.importlinter` contracts, and the `layers` contract sets
`exhaustive = false`, so an unlisted top-level subpackage is not flagged. `root_package`
governs graph membership, not contract membership. The correct statement is that a sibling
package is outside the import graph entirely while a subpackage is inside the graph and
still outside every contract — so the layering leg of the Option-B argument is **work to be
done**, not a property inherited by choosing a subpackage. The governing ADR carries the
corrected claim and adds the enrolment as a decision.

The same correction applies one paragraph up, to "invisible to all five". The five checks do
not share a mechanism: two scan by whole-tree rglob and therefore reach any new directory
under the scanned root automatically, one **enumerates** a fixed surface list and reaches a
new directory only when that list is edited, and two have narrower scopes that do not bear
on a new subpackage. The enumerated one additionally fails **open** — a surface path that
does not exist, or that has been emptied, yields the empty tuple with no error — which makes
"a sibling package would be invisible" true but incomplete, since a subpackage can be
invisible to that same check for a different reason.

### `EvidenceInput`'s tripwires guard serialization, not attribute access

The custody chain is sound and single-pathed:
`secure_object_repository_for_bucket` (`runtime_repository.py:36-41`) →
`SecureBoundRepository` with classification, schema-version and payload-identity binding
(`envelope/_secure_repository.py:186-263`) → `AttachmentStore` with bucket-ownership,
manifest-to-blob and row-key bindings (`attachment.py:240-262`, `:394-415`, `:108-127`) →
`resolve_attachment_evidence_input` (`_evidence_input.py:162-197`) → `EvidenceInput`.

`EvidenceInput` refuses `model_dump`, `model_dump_json`, `__iter__` and `__reduce_ex__`
(`_evidence_input.py:118-146`) and excludes `data` from `repr` (`:101`). But
`STRICT_FROZEN_CONFIG` is `ConfigDict(strict=True, frozen=True, extra="forbid")`
(`core/_models.py:39`) with no `__getattr__`/`__getattribute__` hook, so
`instance.data` returns the raw decrypted bytes with no friction. `frozen=True` blocks
re-assignment, not reading. The tripwires are anti-externalization guards — against
accidental persistence, logging, pickling and cross-process transport — not a capability
boundary. Any code in the same process holding the object has the bytes.

`AttachmentStoreProtocol` (`domain/attachments/_protocols.py:18-57`) compounds this: every
consumer types the store structurally, never as the concrete class
(`_evidence_input.py:165,203`; `domain/attachments/_service.py` throughout;
`_actions_manual.py`, `_actions_common.py`, `_actions_split_merge.py`). Being
`@runtime_checkable` and structural, any object with matching method names satisfies it.
The Protocol is a call-shape contract, not a provenance contract — nothing in the type
system verifies that a satisfying object routes through `SecureObjectRepository`.

Consequently, handing an extension either an `EvidenceInput` or an
`AttachmentStoreProtocol` gives it full byte access. The trust boundary cannot be
enforced by the type system or by the object's own tripwires; it is enforced by the AST
gates, which is why their scope is the question.

No ADR in the corpus governs package or distribution boundaries for sensitive-data code.
The binding decisions are the secure-storage-only persistence ruling in
`2026-06-10-llm-evidence-classification-adr` and the enforcement architecture behind
`2026-06-14-storage-backend-security-review-adr`; neither says the gates may be scoped
narrower than the code they protect.

### The optional-extra machinery already exists and is well-specified

`core/_optional_extras.py` is the single source of truth: the frozen `OptionalExtra`
model with `extra`/`import_name`/`feature` and an `install_hint` property (`:46-68`), the
declared set `OPTIONAL_EXTRAS` (`:74-81`), `MissingOptionalExtraError` subclassing both
`CoreError` and `ImportError` (`:84-109`), the spec-only non-raising probe
`optional_extra_available` (`:112-131`), the classifier `optional_extra_for_module`
(`:134-160`), and the guard `require_optional_extra` (`:163-177`).

The established convention is that the feature-owning adapter calls
`require_optional_extra(EXTRA)` immediately before its own lazy SDK import and converts
the error into its own domain type — `adapters/outbound/llm/_providers/anthropic.py:53-58`
wraps it into `LLMConfigError`; `aeat/browser/_factory.py:317-321` and
`inbound/financial/providers/_ofx.py:189,320` follow the same shape. The application
layer only ever calls the non-raising probe, for the doctor
(`application/provisioning.py:249-281`).

CLI degradation is uniform: `_lazy_loader` (`entrypoints/cli/__init__.py:1039-1060`)
catches `ModuleNotFoundError` at a command group's first import and routes it to
`_surface_for_import_failure` (`:907-947`), which asks `optional_extra_for_module`
whether the missing module belongs to a registered extra — returning a placeholder group
that refuses with the install hint if so, and raising
`CliCommandGroupUnavailableError` if not. Non-`ModuleNotFoundError` failures deliberately
propagate (`:924-926`). The shared test support records why this seam exists: `textual`
became required while stale environments lacked it, and `app modelo` silently degraded to
a placeholder for a day (`tests/_command_group_import_support.py:1-31`).

One precedent is a trap rather than a model: the `agent` extra is **not** registered in
`OPTIONAL_EXTRAS`. It hand-writes its install hint at `entrypoints/mcp/_server.py:157`
and gates itself with a bespoke lazy import in `entrypoints/mcp/__init__.py:67-76`, so it
sits outside the shared classifier. A new extra should register properly rather than copy
it.

### Packaging precedent supports a second distribution, but the cohort contract is exact

`2026-06-28-product-packaging-adr` fixes one exact-version cohort: `cadrumo` plus
`cadrumo-data-manuals` and `cadrumo-data-official`, each pinned `==<version>`, with the
constraint that "the three distributions are mandatory parts of one install; there is no
advertised slim mode that cannot calculate," and that "optional integrations remain
capability extras. Their absence produces the declared install guidance rather than
`ModuleNotFoundError`."

The mechanics for a further distribution exist: each companion is a full separate project
under `packaging/<name>/` with its own `pyproject.toml`, hatchling build, custom build
hook remapping corpus files, and a version kept in test-enforced lockstep with the root.
Both contribute to the `cadrumo_data` PEP 420 namespace, neither shipping an
`__init__.py`. So a fourth distribution is buildable — but it would be the first
*optional* one, and every artifact lane verifies a fixed cohort manifest before install.

### No hardware-capability probe exists anywhere in the product

Confirmed negatively at HEAD by direct search rather than by semantic-search absence:
patterns covering `vram`, `gpu`, `cuda`, `nvidia`, `nvidia-smi`, `pynvml` and
`torch.cuda` return zero matches across `src/cadrumo`. Every capability probe in the
product is import-spec based (`optional_extra_available`) or reachability based —
`probe_ollama_vision` (`application/provisioning.py:75-115`) reads `/api/tags` to check
the server is up and the model name is pulled, and never runs inference;
`probe_playwright_browser` (`:220-246`) checks a cache directory.

`core/_capabilities.py:36-45` already separates two axes in its own docstring: a
`ServiceCapability` records "whether the profile permits the service, not whether its
import/runtime dependency is installed," which is `OptionalExtra`'s job. The evidence
shows a third axis is simply missing:

- **installed?** — `OptionalExtra` / `require_optional_extra`
- **permitted?** — `ServiceCapability.LLM_VISION`
- **capable?** — no mechanism exists

The hardware floor is therefore an undeclared precondition today, discovered only when a
model fails to load or thrashes.

### A live defect: the rasterisation path depends on an undeclared production package

Found while tracing what the extension would have to declare, and verified independently.

`rasterise_pdf_pages_to_base64_png` (`adapters/outbound/llm/_providers/local.py:57-94`)
renders each page and calls `bitmap.to_pil()` at `:86`. In the installed
`pypdfium2`, `to_pil` builds the image via `Lazy.PIL_Image.frombuffer`
(`_helpers/bitmap.py:250-270`) — a lazy Pillow import. `pypdfium2`'s distribution
metadata declares no `Requires-Dist` at all, so it does not supply Pillow.

Pillow is declared **only** under `[dependency-groups] dev` (`pyproject.toml:342`), and
for an unrelated stated purpose: "Reproducible light-theme CLI GIFs for the repository
README." It is absent from `[project.dependencies]` and from every extra.

So on a clean `pip install cadrumo`, the scan-only-PDF vision path has no Pillow. The
failure is not a raw traceback — the page loop is wrapped at `local.py:95-96` and raises
`LLMPdfRasterisationError`, which `_evidence_draft.py:461-468` catches and converts into
a `PurchaseInvoiceEvidenceInputError` whose remediation comes from `probe_ollama_vision`.
The operator is therefore told to fix their Ollama installation when the actual fault is
a missing Python package. That is a misdiagnosed refusal, which is worse for the operator
than a crash and contradicts the dependency-provisioning contract of a "typed refusal
with the exact remediation command."

The image-only path is unaffected: it base64-encodes bytes directly
(`_evidence_draft.py:457-459`) and never rasterises. The defect is specific to
scan-only PDFs reaching the vision reader.

This is evidence for the boundary rather than merely a bug to fix: an extension with its
own `pyproject.toml` must declare `pypdfium2` and `Pillow` explicitly, because nothing
else would supply them. The current arrangement survives only because Pillow is present
in every environment that has so far exercised the path.

### The cloud subprocess path is the odd one out under a local-only extension

The routing evidence is recorded in `2026-08-06-llm-invoice-read-reconciliation-research`
and in the ingestion findings that prompted this work; the part bearing on the boundary is
that the transport chosen depends on whether a PDF happens to carry a text layer.
`_resolve_evidence` (`application/ledger/_llm_classification.py:235-297`) routes text to a
cloud subprocess classifier behind a per-invocation consent gate that is default-off and
barred for gestor deployments (`:274-282`), and routes scans and images to the local
Ollama vision model with no consent requirement. `_classify_with_evidence` (`:380-423`)
then dispatches on `_ResolvedEvidence.is_images`, and raises when the text path is taken
without a `--llm` provider (`:414-418`).

A local-only extension has no place to put the cloud branch. Either it is deleted, or it
stays in the core — where it would be the only inference path left inside the
deterministic package, and the only one able to send taxpayer documents off-host. The ADR
must settle this; `no-legacy-compatibility` bears on it directly, since a dormant-but-kept
cloud path is precisely the bridge that rule forbids.

The blast radius was measured, and it is bounded. `SubprocessLLMClassifier`
(`domain/transactions/_llm.py:861-983`) shells out to a CLI binary resolved by
`shutil.which`; `resolve_classifier` (`:1141-1178`) maps a provider string through
`_PROVIDER_BUILDERS` (`:1134`) to `build_claude_classifier` (`:989`),
`build_antigravity_classifier` (`:1026`) or `build_codex_classifier` (`:1074`). Selection
has exactly one operator-facing entry: the `--llm` option on `aeat app ledger classify`
(`entrypoints/cli/_ledger.py:624`), typed to the application-layer `LLMProvider`
(`_llm_suggestions.py:51-56`). No setting or environment default selects a provider.

Note two distinct enums share the name `LLMProvider`: the application one above
(`CLAUDE | ANTIGRAVITY | CODEX`, the cloud path) and the outbound-adapter one
(`_models.py:33`, backing `LLMClient`/`LLMCache`/`UsageRecorder` and the on-host vision
transport). They are unrelated, and conflating them inflates any impact estimate.

Nothing outside the ledger depends on the cloud transport. `src/cadrumo/agent/` contains
zero references to it — confirmed by both keyword and semantic search; "evidence" in that
tree is eval-scoring vocabulary. `aeat app ledger llm-diagnostics`
(`_ledger_read_cli.py:165`) survives deletion: it folds an encrypted usage log written
only by the on-host `LLMClient` with `classified_by` provenance strings, so it would
simply observe fewer prefixes.

Orphaned by a deletion, with no remaining caller: `cloud_evidence_read_permitted`
(`_evidence_input.py:38`), `ServiceCapability.CLOUD_EVIDENCE_UPLOAD`
(`core/_capabilities.py:67`) and its `resolve_capability` branch
(`application/user_profile/_capabilities.py:97-129`),
`Settings.cadrumo_evidence_gestor_mode` and `cadrumo_evidence_cloud_upload_permitted`
(`core/config.py:762-786`), the `--evidence-acknowledged` flag (`_ledger.py:628-632`),
the whole subprocess builder family, `is_llm_provider_available` /
`available_llm_providers` / `_PROVIDER_CLI_BINARY` (`_llm_classification.py:129-165`),
`probe_subprocess_providers` (`provisioning.py:140-166`) with its `config check` branch
(`_check_cli.py:72`), and the `aeat app ledger providers` command
(`_ledger_read_cli.py:126-161`).

Surviving, because the on-host vision classifier reuses them: `LLMClassificationResponse`,
`LLMSplitResponse`, `PromptSpec` and the prompt-spec builders, `parse_response`,
`parse_split_response`, `build_split_prompt` (all `domain/transactions/_llm.py`, reused
per `application/ledger/_vision_classifier.py:10-14`), `ServiceCapability.LLM_VISION`,
and the entire outbound LLM adapter. The local path does not depend on the cloud path in
either direction, so the cut is clean rather than entangled.

Test impact is 24 files, not the 39 a naive marker sweep returns — 15 of those exercise
the identically-named adapter enum and share nothing with the cloud path. Of the 24, nine
are cloud-only and deletable wholesale (`test_llm_reject.py`, `test_llm_reject_split.py`,
`test_llm_saturation.py`, `test_llm_saturation_apply.py`, `test_ledger_llm_classify.py`,
`test_ledger_llm_saturate.py`, `test_ledger_llm_split.py`, `test_ledger_llm_autosplit.py`,
`test_ledger_corpus_llm_classification.py`); the rest mix cloud and on-host cases in one
file because `_resolve_evidence` branches internally, so they need case-level editing.

One consequence is not a cost of the boundary but a real capability regression, and it
governs sequencing: the cloud path is today the **only** way to classify a text-layer PDF.
Deleting it before a local text reader exists removes a working capability and leaves a
hole for every text-native e-invoice — the majority of modern invoices. The ADR must
decide whether the deletion is sequenced behind local text inference or accepted as a
temporary regression.

### The failure mode this migration invites is already documented

`2026-08-06-llm-invoice-read-reconciliation-research` records three deliverables that
shipped with no production consumer, each "a correct, legally grounded predicate built as
a plan-step deliverable and verified by its own unit tests," where "those tests pass
whether or not anything calls the predicate, so the step closes green with the enrolment
missing."

A package migration is the same shape at larger scale: a module can be moved, imported,
unit-tested and green while nothing in the core actually routes through it. Any plan for
this work needs an enrolment gate per step — proof that the core call site now reaches the
moved code — rather than trusting that the moved module's own tests passing means it is
wired.

### What was not investigated

The runtime cost of the boundary (import time, process count) was not measured. Whether
the invoice-store canonicalisation work interacts with the moved classifier's write path
was not traced; that surface is owned by a concurrent campaign and is recorded as a
dependency rather than analysed. No measurement was made of how many tests would need
rewriting under either boundary beyond the counts reported for the cloud path.

Two items listed here in an earlier pass have since been answered by the concurrent smoke
harness and are reported in the two findings that follow this section, which were appended
after it. The hardware floor is now measured rather than merely cited as the reason a
capability axis is needed, and the structured-XML comparison is measured against real
documents. Neither displaces the capability-axis finding above; both sharpen what belongs
on each side of the boundary.

One question remains open and is deliberately left so rather than resolved by assumption:
the internal pipeline shape (one-shot extraction versus normalize-then-extract). The
measurement that would settle it is specified below as a procedure to run offline with the
fleet quiesced. It was not run.

The share of real user documents arriving as structured XML rather than as scans or
photographs was not measured and could not be, since the corpus was curated rather than
sampled from user traffic. That ratio bounds how much of the ingestion problem the
deterministic path removes.

### Structured XML parsing outperforms every model path measured, and it needs nothing the core does not already have

This finding arrived after the boundary analysis above and changes what belongs on
which side of the boundary. It is the best-evidenced result available to this campaign,
and it is measured rather than reasoned.

**Figures corrected after first publication. An earlier pass of this document reported
88.2% over 53 documents, with ZUGFeRD and UBL both exact. Those numbers were computed
against an unstamped pre-v4 ground-truth key and are WITHDRAWN.** What follows is the v5
re-score, reproduced independently for this document via `tools/rescore_structured.py`,
which prints the key digest before any figure. Ground-truth key
`e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593`, 302 corpus documents,
103 detected as structured, 102 parsed, **56 scoreable** (carrying at least one non-null
truth field).

Direct structured parsing returned **82.1% mean field accuracy** at a **median parse of
0.59 ms** (worst 86.8 ms), 21 of 56 documents perfect, with zero VRAM and no licence
exposure. The local vision models on comparable documents returned **75.8% accuracy at a
4.8 s median** for the application's default (`qwen2.5vl:3b`), rising to 17.2 s for
`qwen3-vl:4b` at 78.8%.

Accuracy by format under v5:

| Format | n | Mean field accuracy | Perfect | Missing | Wrong | Hallucinated |
|---|---:|---:|---:|---:|---:|---:|
| Facturae 3.2.x | 17 | 88.8% | 8 | 1 | 9 | 0 |
| ZUGFeRD / Factur-X (CII) | 20 | 88.5% | 4 | 0 | 22 | 9 |
| VeriFactu / SII | 10 | 81.5% | 6 | 13 | 2 | 0 |
| EN16931 UBL | 2 | 100.0% | 2 | 0 | 0 | 0 |
| TicketBAI | 6 | 50.8% | 1 | 23 | 1 | 0 |
| unrecognised | 1 | 0.0% | 0 | 2 | 0 | 0 |
| **Overall** | **56** | **82.1%** | **21** | **39** | **34** | **9** |

UBL remains at 100%, but at **n=2** that cell carries no weight and must not be quoted as
evidence of format-level exactness. The withdrawn claim paired it with ZUGFeRD, which under
v5 is 88.5%; the fields that made ZUGFeRD look exact were `null` in the old key and were
therefore not being scored at all.

**The residual shortfall is a located parser defect, not a format limit.** This is a
stronger claim than the earlier one it replaces, because the causes are now diagnosed
rather than merely asserted to be fixable. Two account for the bulk of it. The parser
selects the **wrong tax identifier**, taking a French SIRET or a German Steuernummer where
the truth holds the VAT number - which is why ZUGFeRD, a Franco-German format, carries 22
of the 34 wrong fields despite having zero missing ones. And it **swaps emisor and
destinatario** on received-invoice SII records. Both are one-edit fixes in roughly 300 lines
of stdlib parsing code. The data is present in the documents; the gap is element selection.
A misread digit from a vision model is not fixable in that way, at any cost.

**The fail-loud property was observed rather than asserted.** One document,
`REAL-SPA-aeat-sii-gisce-alta-factura-emitida-rectific`, refused with
`ParseError: junk after document element: line 60, column 0` and produced no record at all.
That is the whole argument in one line: **a parser fails loudly; a model fails silently.**
A model handed the same malformed document would have returned a confident, plausible,
wrong invoice. A silent wrong value in this product reaches a filing; a refusal does not.

**The latency advantage is real but must be stated as a range, not a single flattering
multiplier.** Against the application's default model, the median parse is roughly 8,000x
faster (0.59 ms against 4.8 s); against the slowest model tested, roughly 29,000x. The
honest floor is the worst observed parse against the fastest model - 86.8 ms against 4.8 s,
still roughly 55x. An earlier draft quoted a single "20,000x" derived from mid-range models
and the superseded latency median; it is withdrawn.

**The core already has everything this path requires.** `defusedxml>=0.7.1,<1` is declared
in `[project.dependencies]` at `pyproject.toml:55` and already carries production
consumers in the filing and registry export paths
(`application/filing/_export_xml_dictionary.py:34`,
`domain/calculations/registry/_export_parse.py:13`), so hardened XML parsing costs no new
dependency, no model, no GPU, no extra and no licence exposure. Verified at HEAD.

**And no such parser exists today.** Confirmed at HEAD by targeted search rather than by
semantic-search absence: `zugferd|factur-x|facturae|en16931|ticketbai|CrossIndustryInvoice`
returns no production match anywhere in `src/cadrumo` - only the
`zugferd_en16931_invoice.pdf` corpus fixture and a test asserting that a German word
appears in its text layer (`application/ledger/tests/test_evidence_corpus_parsing.py:36-38`).
`MediaKind` remains a closed two-member enum, `PDF` and `IMAGE`
(`application/ledger/_evidence.py:108-112`). The most machine-readable invoice in the
corpus is read as rendered prose, and because it carries a text layer it takes the cloud
branch - so the format needing no model at all is the one whose bytes leave the host.

The consequence for this campaign is unchanged by the correction, and cuts against a naive
reading of the campaign's own proposal: the exact path does not belong in the optional
inference extension. It belongs in the deterministic core, where it is available on a
default install with no extra enabled. The extension is then correctly scoped to what
genuinely needs a model - documents that carry no structured record.

**The honest limits, stated so the ADR does not over-claim.** The accuracy margin over the
default vision model is **82.1% against 75.8%** - a real advantage but a narrower one than
the withdrawn figures implied, and the case now rests at least as much on the fail-loud
property, the four-orders-of-magnitude latency gap, and the zero marginal cost as on
accuracy alone. Separately, none of this establishes what share of documents a real user
receives as structured XML versus as a photograph of a paper receipt. That ratio decides
how much of the problem the deterministic path removes, and the harness did not and could
not measure it - the corpus composition was curated by the corpus lane, not sampled from
real user traffic. The directional argument remains strong for Spanish taxpayers
specifically, because a business subject to VeriFactu is legally required to produce a
structured record for every invoice.

One instrument caveat is recorded because it bears on a different metric: 46 parsed
documents remain unscoreable because the key carries no truth for them, and the 9
hallucinations are wholly concentrated in ZUGFeRD, where the wrong-identifier defect also
sits. Until that defect is fixed and the key's remaining gaps are closed, **the
hallucination column above should not be quoted** as a property of structured parsing.
The accuracy figures are unaffected, being computed only over fields with a non-null truth.

### The internal pipeline shape is unmeasured, and the measurement that would settle it is specified

A two-stage shape - normalize every origin to markdown, then run one uniform extraction
stage over it - is an attractive reading of the ingestion findings, and this research
deliberately does not adopt it. **The stage-1/stage-2 isolation was never measured.** The
corpus transcriptions needed for it landed minutes before the session ended and the run
never happened. No number in the harness distinguishes one-shot extraction from
normalize-then-extract.

Adopting the two-stage architecture on the strength of the one-shot measurements would
repeat exactly the conflation this campaign exists to break, and it would do so against a
known cost: the ingestion findings establish that promoting hostile document text across a
stage boundary makes prompt injection *worse*, because extraction fields have no
allow-list the way classification categories do. A two-stage shape must therefore earn its
place with evidence rather than inherit it by assumption.

The measurement, to be run later offline with the agent fleet quiesced and no concurrent
GPU load, is: over the same corpus and the same model, score (a) one-shot direct field
extraction from page images against (b) transcribe-to-markdown followed by a separate
text-only extraction pass, reporting per-field accuracy, end-to-end median latency and
resident VRAM for each, and holding prompt, model, revision and decoding parameters fixed
across both arms so the stage count is the only variable. Two-stage is preferable only if
it wins on accuracy by a margin that justifies both its added latency and the injection
surface it opens. The ADR must therefore be able to stand on its packaging and boundary
decisions without depending on the answer.

### Running live local inference destabilised the host, which is operational evidence for the boundary

Recorded factually. During this campaign, live local model inference on the development
host destabilised the entire machine and terminated four concurrently running agent
sessions. Work continued only against already-captured results.

This is not an argument about model quality, and it is not evidence that inference should
not ship. It is evidence about *where* it should sit. An inference path embedded in the
deterministic core is one that every developer environment, every test run and every CI
lane carries by default, so its resource profile becomes everyone's resource profile.
Behind an opt-in extra, the same path is absent from the default build, test and
development loop and is exercised only by environments that asked for it. The isolation
that matters here is operational rather than architectural, and it is a benefit the extra
delivers on the day it lands, independent of the licence and privacy arguments.

It also independently supports the finding above: the deterministic XML path has no such
profile at all - no model, no GPU, no daemon - which is a further reason it belongs on the
core side rather than behind the extra.

## Sources

- `pyproject.toml` — `[project].dependencies` `:23-80`; extras `:124-198`; `search` extra
  absence rationale `:181-187`; build system `:200-202`; wheel/sdist targets `:209-272`;
  uv sources `:284-298`; `[tool.vaultspec-rag]` `:300-301`; dev group and torch
  `:302-311`; pillow `:342`
- `.importlinter:2`
- `src/cadrumo/tests/_inventory.py:11`, `:98-109`
- `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py:24-57`,
  `:59-241`, `:349-369`, `:386-398`, `:411-449`
- `src/cadrumo/tests/test_storage_provenance_gate.py:370-382`
- `src/cadrumo/adapters/persistence/storage/tests/test_ephemeral_key_hygiene.py:78-98`
- `src/cadrumo/adapters/persistence/storage/runtime_repository.py:36-41`, `:44-54`
- `src/cadrumo/adapters/persistence/storage/envelope/_secure_repository.py:186-263`
- `src/cadrumo/adapters/persistence/storage/attachment.py:108-127`, `:240-262`, `:394-415`
- `src/cadrumo/application/ledger/_evidence_input.py:101`, `:118-146`, `:162-197`, `:165`, `:203`
- `src/cadrumo/core/_models.py:39`
- `src/cadrumo/domain/attachments/_protocols.py:18-57`
- `src/cadrumo/core/_optional_extras.py:46-68`, `:74-81`, `:84-109`, `:112-131`, `:134-160`, `:163-177`
- `src/cadrumo/core/_capabilities.py:36-45`
- `src/cadrumo/entrypoints/cli/__init__.py:907-947`, `:1039-1060`
- `src/cadrumo/entrypoints/cli/tests/_command_group_import_support.py:1-31`
- `src/cadrumo/entrypoints/mcp/__init__.py:67-76`, `src/cadrumo/entrypoints/mcp/_server.py:157`
- `src/cadrumo/application/provisioning.py:75-115`, `:220-246`, `:249-281`
- `src/cadrumo/application/diagnostics_run_health.py:71`
- `src/cadrumo/application/ledger/_llm_classification.py:53-54`, `:235-297`, `:261`,
  `:274-282`, `:380-423`
- `src/cadrumo/application/ledger/_llm_diagnostics.py:43-46`
- `src/cadrumo/application/ledger/_evidence_draft.py:457-459`, `:461-468`
- `src/cadrumo/adapters/outbound/llm/_cache.py:20`, `:123`, `:205`
- `src/cadrumo/adapters/outbound/llm/_run_telemetry.py:55`, `:153`
- `src/cadrumo/adapters/outbound/llm/_usage.py:20`, `:119`
- `src/cadrumo/adapters/outbound/llm/_providers/local.py:57-94`, `:86`, `:95-96`
- `src/cadrumo/adapters/outbound/llm/_providers/anthropic.py:53-58`
- `src/cadrumo/adapters/outbound/aeat/browser/_factory.py:317-321`
- `src/cadrumo/adapters/inbound/financial/providers/_ofx.py:189`, `:320`
- `packaging/cadrumo_data_manuals/pyproject.toml`, `packaging/cadrumo_data_official/pyproject.toml`
- `.venv/Lib/site-packages/pypdfium2/_helpers/bitmap.py:250-270`; `pypdfium2@5.12.1`
  distribution metadata (no `Requires-Dist`)
