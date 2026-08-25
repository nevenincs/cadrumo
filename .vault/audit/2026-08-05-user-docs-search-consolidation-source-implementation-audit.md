---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b5f3361464f2befd237faf7762bbf6fcfd598ed50fe3f633c4015f4d1a779142'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-05-user-docs-search-consolidation-p02-s04-query-token-matrix-audit]]"
---

# `user-docs-search-consolidation` audit: source implementation review

## Scope

Review the current source-only implementation against the approved L2 plan, the user-docs-search-consolidation ADR Update 6, deterministic casilla enrollment research, and the P02.S04 query-token matrix audit. The review was grounded with canonical vaultspec-rag searches and exact source reads across the Rung-2 matrix/provider/bridge/compiler/acceptance path, the shared browser controller, legal projection/resolution, Pagefind injection, CLI projection, and casilla projection/resolution. No tests, builds, model downloads, artifact generation, Pagefind/runtime probes, live sweeps, reindexing, or deployment were run.

## Findings

### rung2-input-provenance | high | Computed input provenance is discarded before bundle creation

`Rung2CompilationInputs.provenance` is built from the committed relevance bytes and canonical vocabulary/query-token fingerprints, but `compile_project_rung2_search_bundle` does not pass it into `Rung2SearchBundle`, which has no corresponding field. Sol-medium recommends a required top-level `input_provenance` field in the browser-consumed bundle, a schema-version increment, canonical hash coverage, and compiler/acceptance/browser validation. This is an architectural contract change and requires a focused ADR amendment before coding.

### model-content-attestation | high | Local model content and tokenizer hashes remain caller-attested

The Potion provider validates the ratified repository, immutable revision, package version, licence, dimension, and tokenizer shape, but does not independently attest local model contents or tokenizer configuration hashes. The current browser acceptance checks model identity and normalization but cannot verify absent raw source bytes. This remains an acceptance gap under ADR R8 and must be resolved before artifact acceptance.

### casilla-locale-fallback | high | Spanish fallback can be counted as localized coverage

Casilla projection obtains every locale through the localization resolver, which may fall back to Spanish. The coverage census then treats the resulting multi-language mapping as localized presence. This can overstate non-Spanish definition completeness and weakens the P06.S24 localized-definition evidence.

### miss-rate-threshold-override | high | Rung-2 adjudication accepts an unratified threshold override

`adjudicate_rung2` accepts a caller-provided threshold across the full metric range even though the ratified materiality line is 0.10 and the module documents that it must not be loosened ad hoc. A caller can therefore avoid the intended Rung-2 decision without new authority.

### diseno-casilla-locator | medium | Disenos paths are recognized but non-TOML hits are always dropped

The resolver matches official workbook/PDF paths, then `_resolve_casilla` rejects every non-`.toml` path because `ChunkHit` carries only a path and line range. The fail-closed behavior avoids a wrong casilla, but the declared locator-dependent Disenos contract is not implemented and official workbook/PDF hits cannot resolve individually. The preprocessor already models unit title/section/anchor metadata, so any fix must be grounded in the actual RAG hit payload rather than guessing a casilla from a modelo path.

### legal-source-collision | medium | Normatives source paths collapse multiple provisions

The reverse legal index strips corpus anchors and stores one legal id per path with `setdefault`. If multiple catalogue provisions share a normatives HTML source path, the resolver silently chooses the first provision instead of requiring an anchor or dropping an ambiguous hit. This conflicts with the per-provision legal target contract.

### cli-synthetic-record | medium | CLI family hits synthesize records outside the Pagefind projection

The CLI family resolver creates `cli-ref:<family>` records instead of resolving against the authoritative CLI projection or a Pagefind page record. The Rung-2 manifest admits only records emitted by the shared Pagefind projection, so this synthetic id can become an unmanifested relevance target.

### bridge-order-parity | medium | Python loading does not enforce the browser's deterministic target ordering

The builder and browser enforce ordered bridge targets, but the Python bridge model/loader does not enforce the same ordering. The two acceptance boundaries can therefore disagree on an artifact.

### browser-hash-parity | medium | Browser validation checks hash shape and links but not all nested content hashes

The browser validates SHA-256 formats and cross-links but does not recompute every matrix, manifest, bridge, target-list, and bundle self-attestation hash that the Python contracts recompute. This leaves a source-level validation parity gap.

### pagefind-narrowing | medium | Pagefind injection can continue after malformed relevance or CLI projection omission

Malformed relevance data can become empty boosts, and CLI projection exceptions can be converted into a skipped projection while direct injection continues. The projection reports the omission, but a caller that does not enforce the report can ship a narrowed corpus. The open deployment-parity and record-corpus gates remain necessary.

### acceptance-boundary | low | Source contracts do not constitute artifact or release evidence

The matrix/provider/bridge/browser/legal/casilla source seams are directionally aligned, but the plan rows remain unaccepted. The current source review cannot prove the pinned model artifact, content hashes, quantization drift, held-out recall, locale parity, generated targets, or live behavior.

### shared-manifest-canonicalizer | low | Source remediation; independent parity remains open

Fresh vaultspec-rag grounding against ADR Update 10 and the raw-byte manifest implementation found that the manifest module retained a second compact `json.dumps` serializer after the shared `cadrumo-jcs-utf8-lf-v1` contract was introduced. `_content_manifest.py` now delegates both manifest-root hashing and complete-manifest bytes to the shared canonicalizer, so the provider/tokenizer attestation path no longer has Python-only serialization semantics.

Static evidence is limited to post-edit vaultspec-rag discovery, AST parsing, and focused whitespace validation. This does not close the broader `browser-hash-parity` finding: the language-neutral golden-vector corpus and independent Python/JavaScript reproduction are still absent, and no tests, artifacts, model/provider evidence, runtime probes, sweeps, reindexing, or deployment were run.

### per-root-casilla-recall-gate | low | Source gate added; runtime acceptance remains open

RAG and source inspection confirm the existing built-site gate already exercises one real concept record on each root, but its bounded per-kind sample was not asserted for casillas. A source-only continuation adds `_probe_casilla_record()` and a per-root browser/Pagefind gate that uses one real bounded casilla target, its stable title, and each available localized `OutputLanguage` description. The gate reads through the production `_materialise_records()`, `_bounded_to_sample()`, injector, and `pagefind.js` path; it does not invent a query or use a fake record.

Static Ruff, AST, and diff checks passed. The step remains open: no tests, builds, Pagefind/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run, and the deployed-root re-probe is still deferred.

### current-plan-count | low | Current status trace supersedes the older snapshot

The earlier audit sentence stating “12 of 24 steps” predates four later plan additions. The current VaultSpec trace is authoritative for the live plan: 28 total steps, 12 closed, 16 open, 42.9 percent, with P02.S04 next. No step is closed by this source-only continuation.

### focused-source-review | low | No new concrete source defect; artifact and runtime acceptance remain open

Fresh vaultspec-rag grounding over the active plan, the accepted Rung-2 contract, the P02.S04-S07 execution records, and the legal/casilla source seams was followed by exact reads of the current matrix, provider, bridge, browser-controller, legal projection, and casilla-resolution paths. The source contracts are present and fail closed at their current boundaries: P02.S05 has no enabled artifact without an explicit accepted config and validated bundle; P02.S06 validates the ratified provenance/licence/size boundary while awaiting real manifests and provider evidence; legal records use the dedicated `LEGAL` kind and generated targets; and deterministic casilla enrollment remains separate from sparse relevance coverage. No additional source edit is justified by this review. P02.S04 through P02.S07, P03.S08, P04.S12-S13, P05.S14-S17, and P06.S24 remain open until their named artifact, build, behavioural, live, or deployment evidence is authorized and observed. No tests, builds, model downloads, generated artifacts, Pagefind/runtime probes, live sweeps, reindexing, or deployment were run.

### source-lint-hygiene | low | Focused static cleanup leaves the Rung-2 contracts unchanged

After fresh vaultspec-rag grounding of the exact Rung-2 modules, the project Ruff gate surfaced six hygiene findings in concurrent WIP: one unused canonical-number tuple binding, three export-order issues, one import-order issue, and one ambiguous boolean-precedence expression in the browser-equivalent evaluator. These were corrected with a bounded source-only patch; the canonical JSON algorithm, public contracts, and ranking semantics were not changed. `uv run --no-sync ruff check` now passes for the task-scoped Python modules, `node --check` passes for the shared controller, and focused `git diff --check` passes. No tests, builds, artifacts, runtime probes, model/provider work, reindexing, live sweeps, or deployment were run.

### assembled-input-authority | low | Rung-2 input handoff now rejects mismatched or degraded source payloads

Fresh vaultspec-rag grounding of the P02.S04 contract showed that `Rung2CompilationInputs` relied on annotations plus fingerprint checks, while direct dataclass construction could still carry the wrong runtime model, an empty/degraded sweep, or vocabulary/query-token tuples that did not come from the committed sweep mappings. The source boundary now enforces exact validated runtime types, a non-empty authoritative record projection, a consistent non-degraded sweep, and equality between the canonical sweep-derived identities and the supplied identities before provider compilation. `basedpyright`, Ruff, and focused diff checks pass. This is source remediation only; P02.S04 remains open until the real provider, matrix artifact, licence, and acceptance evidence exists.

### bridge-order-parity-followup | low | PASS: committed Python ordering now matches the browser contract

Fresh vaultspec-rag grounding and exact inspection of commit `c2f7a464ce` confirm that `SemanticBridgeEntry` now requires targets in descending `ranking_weight` order with UTF-8 `record_id` ordering for ties. The browser validator applies the same comparator. The change preserves duplicate-id rejection and hashes the ordered target list, so Python loading and browser acceptance no longer disagree on this contract. A focused LUNA Max review was dispatched but timed out; this PASS is based on the exact source/diff review and is not agent approval.

No tests, builds, artifact loading, runtime probes, model downloads, reindexing, live sweeps, or deployment were run. This finding does not close P02.S04, P02.S25, or any acceptance row.

### legal-surface-recheck | low | PASS: current legal targets remain generated and provenance-separated

Fresh vaultspec-rag grounding over P05.S14-S17, followed by exact RAG code-file reads and local relevance/record inspection, confirms that the legal projection emits the dedicated `LEGAL` kind, generated site-relative provision targets, and BOE provenance as metadata. The injector requires a non-empty legal projection; the resolver uses the generated target and refuses ambiguous provision identity; and the committed relevance entries inspected use generated legal anchors rather than direct BOE URLs. No legal source correction is justified in this continuation.

P05.S14-S17 remain open only for their named generated-surface, parity, build, and runtime evidence. No tests, builds, generated artifacts, Pagefind probes, live sweeps, reindexing, model downloads, or deployment were run.

## 2026-08-05 RAG-grounded Pagefind narrowing remediation

A fresh vaultspec-rag search over `dev/docs/pagefind_inject.py` confirmed that the authoritative projection reports a skipped CLI projection while the ordinary Pagefind injector previously continued with concepts, casillas, legal provisions, and pages. The same source contract treats the committed relevance file as optional only when absent; a present but malformed sweep file must not silently become an unreviewed base-weight build.

The source seam now raises `SearchInjectionError` before Pagefind writes when the CLI projection is incomplete, and raises the same error when a present relevance file fails `SweepResult` validation or cannot be read. An absent relevance file retains the documented deterministic base-weight fallback. Relevance loading is deferred into the injection callback so a missing vendored Pagefind still reaches its existing unavailable-backend boundary first.

Static verification passed with Ruff, basedpyright (0 errors, 0 warnings, 0 notes), AST parsing, and diff checks. No tests, builds, Pagefind/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run. This is source remediation only; the deployment-parity and record-corpus acceptance rows remain open.

## Recommendations

- Obtain and record the focused ADR amendment for required bundle input provenance before modifying the Rung-2 schema; then delegate the source implementation to Luna with exact version/hash-link and fail-closed requirements.
- Correct the threshold lock, locale census semantics, bridge validation parity, pagefind omission handling, legal ambiguity behavior, and CLI authoritative-record resolution as disjoint source-only fixes, subject to RAG grounding and formal review.
- Resolve the Disenos locator contract from the actual preprocessor/RAG payload before adding fields or fallback logic; fail closed until an individual locator is available.
- Keep P02.S04 through P02.S07, P03.S08, P04.S12 through P04.S13, P05.S14 through P05.S17, and P06.S24 open until their authorized artifacts and runtime gates exist.

## 2026-08-05 live refresh: no additional source defect justified

Fresh vaultspec-rag code and vault searches, followed by exact reads of the current Rung-2 compiler/acceptance/browser/controller seams and the legal resolver/projection, found no new source defect within the authorized boundary. The client cosine tier remains an additive, fail-closed path shared by the palette and inline search page; the legal resolver returns the generated `LEGAL` projection target with BOE retained as typed provenance. P02.S04 through P02.S07 and P02.S25 remain open for provider/artifact, behavioural, measurement, and independent cross-runtime parity evidence rather than missing source scaffolding.

The code RAG index reported a transient live/index count mismatch during refresh; no reindex or alias bypass was used, and exact source reads supplied the confirmation boundary. No tests, builds, golden-vector verification, matrix generation, Pagefind/runtime probes, live sweeps, reindexing, model downloads, or deployment were run.

## 2026-08-05 scoped static typing cleanup

Fresh vaultspec-rag grounding of the Rung-2 evaluator confirmed that its composition and held-out functions are source-only measurement seams with explicit fail-closed input validation. The runtime guards were retained while the public parameters at those boundaries were widened to `object` and narrowed with explicit casts only after validation, removing four unnecessary-type-check and unknown-type diagnostics. The JCS serializer likewise retains its canonical contract while using explicit casts for mapping and sequence values after the existing type checks.

The scoped Rung-2/casilla Python surface now passes Ruff and basedpyright with zero errors, warnings, or notes; the shared controller passes Node syntax and the unstaged focused diff check. The staged focused diff check still reports one new blank line at EOF in the peer-modified `_static_matrix.py`; it was not altered to preserve that staged WIP. No tests, builds, runtime probes, generated artifacts, Pagefind runs, live sweeps, reindexing, model downloads, or deployment were run.

## 2026-08-05 casilla projection locale-stat remediation

Fresh vaultspec-rag grounding of the casilla projection and coverage contracts confirmed that `records_with_localized` is a source-statistic for authored non-Spanish registry labels, while reader-facing descriptions may legitimately use Spanish fallback. The projection was still deriving that statistic from `len(record.descriptions) > 1`, which counted fallback labels as authored localization. The bounded Luna Extra High review corrected the projection to consult the registry localization catalogue with `lookup_translation_entry` for the selected latest casilla definition; missing or fallback-only locales are no longer counted. The display projection remains unchanged.

Ruff, basedpyright, and focused diff checks pass for the changed projection. No tests, builds, runtime projection, generated artifacts, Pagefind probes, live sweeps, reindexing, model downloads, or deployment were run. P06.S24 remains open until its authorized real-behaviour gate is observed.

## 2026-08-05 continuation — bounded source remediation

Following the RAG-grounded review, the accepted ADR Update 7 ratified the required Rung-2 input-provenance bundle contract. The source assembler's computed `Rung2InputProvenance` is now propagated through the compiler into a required schema-v2 `Rung2SearchBundle.input_provenance`; canonical serialization, artifact hashing, and byte accounting include it. Python acceptance validates the embedded identity and its matrix fingerprints. The browser contract accepts only schema-v2 bundles, validates the embedded provenance shape and SHA-256 fields, and checks vocabulary/query-token links without attempting to recompute the raw-source digest.

The Luna Extra High browser slice updated `docs/_static/cadrumo-docs.js`; the Python provenance implementation was integrated against current `HEAD` after the Luna Max worker failed to converge without touching a stale shared-index projection. The existing committed strict-boundary source was preserved. Static verification passed with Ruff, basedpyright (0 errors, 0 warnings, 0 notes), AST parsing, Node syntax, diff checks, and conflict-marker scan. No tests, builds, model downloads, Pagefind/runtime probes, artifact generation, live sweeps, reindexing, or deployment were run.

### Disposition of previously identified findings

- `rung2-input-provenance`: source contract and ADR amendment are now in place; artifact acceptance remains open because the user has deferred builds and tests.
- `miss-rate-threshold-override`: fixed by `2eca09e5e3`; the adjudication and CLI use the ratified threshold only.
- `legal-source-collision`: fixed by `2eca09e5e3`; ambiguous corpus-path-to-provision mappings fail closed.
- `cli-synthetic-record`: fixed by `2eca09e5e3`; family hits resolve only to an unambiguous emitted Pagefind CLI record and never fabricate a record.
- `model-content-attestation`, `casilla-locale-fallback`, `bridge-order-parity`, `browser-hash-parity`, `pagefind-narrowing`, and `diseno-casilla-locator` remain bounded follow-ups; no acceptance row is closed by source-only inspection.

The plan remains at 12 of 24 steps closed (50 percent), with P02.S04 and the remaining artifact, runtime, multilingual, legal, and deployment gates open.

## 2026-08-05 locale-census remediation

RAG confirmed that the projection's non-Spanish display labels intentionally use the shared Spanish fallback resolver, while the registry conformance surface already distinguishes authored locale values with `lookup_translation_entry`. The casilla census now keeps the display fallback unchanged but resolves each projected record's latest registry definition and counts locale coverage only when an authored `en`, `ca`, or `hu` label key has a non-null catalogue value. Missing modelos or casilla definitions fail closed as uncovered. Static verification passed with Ruff, basedpyright (0 errors, 0 warnings, 0 notes), AST parsing, and diff checks. No tests or runtime projection were run.

The `casilla-locale-fallback` finding is therefore source-remediated at the census boundary; the P06.S24 acceptance row remains open until its authorized evidence gate runs.

## 2026-08-05 bridge-order parity remediation

RAG confirmed that the browser already requires each semantic bridge target list to be non-increasing by ranking weight and UTF-8 record-id order on ties, while the Python `SemanticBridgeEntry` validator checked only uniqueness and `targets_sha256`. The Python validator now enforces the same deterministic ordering. Static verification passed with Ruff, basedpyright (0 errors, 0 warnings, 0 notes), AST parsing, and diff checks. No tests or artifact loading were run.

The `bridge-order-parity` finding is source-remediated; the browser nested-content hash parity finding remains open and no acceptance row is closed by this source-only change.

## 2026-08-05 R8 provider/tokenizer content-attestation disposition

### r8-content-attestation | high, deferred | Provenance fields are not independently verifiable from the current contract

The RAG-grounded source review and LUNA MAX implementation review confirm that `PotionModel2VecProvider` validates the selected local model identity, revision, package versions, dimension, tokenizer interface, and normalization shape, but does not independently derive or verify `ProviderProvenance.source_sha256`, `TokenizerProvenance.vocabulary_sha256`, or `TokenizerProvenance.config_sha256`. The current schema and ADR identify these as required content attestations but do not define the exact byte set, canonicalization, or authoritative local files for each digest.

Adding a deterministic package/model manifest or tokenizer-file convention now would invent a new provenance contract and could attest the wrong bytes. The existing model artifact has not been downloaded or inspected under the no-model-download boundary. No source edit was therefore made.

### disposition

Record this as a bounded R8 follow-up: first amend the accepted ADR/schema with the exact provider package/model byte manifest and tokenizer vocabulary/config byte semantics, then implement independent verification before matrix compilation or artifact acceptance. P02.S06 and the related Rung-2 acceptance rows remain open. No tests, builds, model downloads, matrix generation, browser probes, or deployment were run.

## 2026-08-05 R8 raw-byte manifest source implementation

The accepted ADR Update 8 now defines the missing byte semantics. Source implementation adds a strict `RawByteManifestV1` primitive with exact raw-byte SHA-256 entries, canonical compact sorted-key UTF-8 root hashing, explicit reviewed path membership, POSIX non-escaping path validation, duplicate/case-collision rejection, symlink rejection, and strict local verification of missing, changed, or unexpected files.

`ModelMetadata` now carries the required whole-model snapshot root. `PotionModel2VecProvider` requires provider, complete model-snapshot, tokenizer-vocabulary, and tokenizer-configuration manifests and verifies their role, pinned identity, roots, local bytes, and tokenizer-to-snapshot coverage before importing `model2vec` or calling `from_pretrained`. The browser matrix validator requires the embedded model snapshot root as part of the hash-covered model metadata.

This is source-level remediation of the caller-only hash gap, not artifact acceptance. The actual provider distribution/model/tokenizer manifests, package version, model snapshot, quantization measurements, and held-out evidence are still absent and must be supplied under P02.S26/P02.S06 before any matrix can compile or ship. No tests, builds, model downloads, generated artifacts, Pagefind/runtime probes, live sweeps, reindexing, or deployment were run. Static Ruff, basedpyright, AST, Node syntax, and diff checks passed.

## 2026-08-05 formal review boundary and provider-import ordering

The formal reviewer did not issue PASS because concurrent shared-worktree WIP made the working-tree view unsafe for review; the committed object `a0dc2c47bf` remains the review target. No finding was reported against the manifest controls. A source-only follow-up `351d3cb935` now binds the provider manifest repository to the pinned provider package and checks the installed package version through importlib metadata before importing `model2vec`; manifest verification remains first.

The source acceptance boundary remains honest: no artifact or runtime acceptance is claimed, and P02.S26/P02.S06 stay open until real provider/model/tokenizer evidence and the authorized gates exist. No tests, builds, downloads, generated artifacts, probes, sweeps, reindexing, or deployment were run.

## 2026-08-05 browser-hash parity disposition

RAG and the LUNA Extra High source review confirm that the browser must not recompute the Python self-attestation hashes until the two runtimes share a proven canonical JSON number contract. Python's canonical serializer preserves numeric lexical forms that JSON.parse discards, and JavaScript serialization is not byte-equivalent for every valid finite float accepted by the matrix, bridge, and manifest schemas. Adding a browser recomputation now could reject a valid future artifact or validate bytes different from the Python contract. No new canonicalizer or schema amendment is authorized in this source-only lane; browser nested-content hash parity remains a bounded follow-up before artifact acceptance. No tests, builds, artifact generation, runtime probes, or deployment were run.

### Source continuation: committed JCS vector corpus

Fresh vaultspec-rag grounding of ADR Update 10 and the current Python/browser canonicalizers preceded a bounded new-file addition under `dev/docs/terminology/jcs_vectors/`. The corpus covers the ratified numeric, safe-integer, escaping, Unicode, surrogate, nesting, terminal-LF, and representative hash-scope vector classes. Its Python consumer imports `canonical_json_bytes` directly; its JavaScript consumer is independent and does not invoke Python. Static JSON parsing, Ruff, basedpyright, `node --check`, and `git diff --check` passed for the new files.

This advances source readiness but does not prove parity: neither consumer was executed, the browser production path was not runtime-probed, and no artifact or release evidence exists. P02.S25 remains open pending authorized independent execution and the broader Rung-2 acceptance gates. No tests, builds, model downloads, matrix generation, generated artifacts, Pagefind/runtime probes, live sweeps, reindexing, deployment, or release acceptance were run.

### Source continuation: vector rejection alignment

Exact source inspection found one corpus/consumer inconsistency in the newly added JCS vectors: both the production Python and independent JavaScript canonicalizers reject integer-valued binary64 numbers outside the safe-integer domain, so `1e21` cannot be an accepted upper-threshold vector under this contract. The corpus now records that case as rejected. JSON parsing, `node --check`, and focused diff checks pass; the independent consumers were not executed. This is a source correction only and does not close P02.S25.

## 2026-08-05 committed-object manifest review

### r8-manifest-review | low | PASS: raw-byte manifest source contract

The mandated RAG-grounded reviewer returned PASS for the committed objects `a0dc2c47bf` and `351d3cb935`. Direct committed-object inspection confirmed the ADR Update 8 contract: strict `RawByteManifestV1` fields and canonical root hashing; explicit raw-byte SHA-256 and byte-length checks; rejection of absolute, escaping, non-normalized, duplicate, case-colliding, symlinked, missing, and unexpected files; provider/model/tokenizer role and snapshot-root binding; verification before provider import and `from_pretrained`; local-only loading with `force_download=False`; and browser enforcement of `model_snapshot_sha256`.

The review is source-only. Actual provider/package/model/tokenizer manifests, installed package evidence, matrix generation, measured quantization, held-out evidence, tests, builds, runtime probes, reindexing, and deployment remain intentionally absent. P02.S26, P02.S06, and all artifact/runtime/deployment acceptance rows remain open.
