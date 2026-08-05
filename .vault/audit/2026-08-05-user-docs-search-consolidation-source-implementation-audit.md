---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d32edab96ef559fa4e8226197b13fd1be2b2b020c4308fee0a5b9289ba53e9d3'
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

## Recommendations

- Obtain and record the focused ADR amendment for required bundle input provenance before modifying the Rung-2 schema; then delegate the source implementation to Luna with exact version/hash-link and fail-closed requirements.
- Correct the threshold lock, locale census semantics, bridge validation parity, pagefind omission handling, legal ambiguity behavior, and CLI authoritative-record resolution as disjoint source-only fixes, subject to RAG grounding and formal review.
- Resolve the Disenos locator contract from the actual preprocessor/RAG payload before adding fields or fallback logic; fail closed until an individual locator is available.
- Keep P02.S04 through P02.S07, P03.S08, P04.S12 through P04.S13, P05.S14 through P05.S17, and P06.S24 open until their authorized artifacts and runtime gates exist.
