---
tags:
  - '#research'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:09bc4f99e6ab2ea462d8d0d77edbe826bc75fa56656e3368934ee7e24e55252a'
related:
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-07-13-docs-terminology-search-adr]]"
  - "[[2026-07-13-docs-terminology-search-research]]"
---

# `user-docs-search-consolidation` research: `Sharpen the Rung-2 static-embedding boundary`

P02.S03 asks what the fired rung-2 verdict actually permits before a compiler is
built. The evidence supports a bounded, build-time term matrix, but does not
support open-vocabulary semantic search or a reader-side model: the current
miss-rate is an upper bound over the precompiled tiers, the client can only
compare query material represented in the closed vocabulary, and the shipping
rule admits only a small provenance-stamped plain-data matrix. The matrix model,
exact vocabulary inventory, and serialized representation therefore remain ADR
questions for the next step; this record does not select them.

## Findings

### The rung-2 trigger is real, but its measurement is deliberately conservative

The remediated held-out evaluation recorded 32 cases, 26 hits, and a 0.1875
miss-rate against the ratified 0.10 threshold, so the accepted D3 rule fired
`implement-rung-2`. All six misses were out-of-sample cases, and the audit
explicitly records that the evaluator models only the precompiled tiers and
therefore overstates (rather than understates) misses on the shipped product,
whose Pagefind full-text tier is not simulated. That result justifies studying
the next rung; it is not a claim that the current reader experience has exactly
an 18.75% miss-rate. `.vault/audit/2026-07-13-docs-terminology-search-audit.md:49-68`

The implementation makes the caveat structural: the out-of-sample evaluator
selects mappings whose normalised query is contained in the held-out query and
limits each mapping to the first five targets; it never invokes Pagefind or a
full-text index. `dev/docs/terminology/_miss_rate.py:168-235` The threshold and
top-five bound are code defaults, not ad hoc report parameters:
`dev/docs/terminology/_miss_rate.py:44-46`.

### The matrix has a hard token-coverage boundary, not open-vocabulary recall

Rung 2 can bridge a query to a closed-vocabulary term when the build-time model
has an embedding row for the relevant tokenised term, but it cannot represent
tokens absent from that inventory. The governing ADR states the limit plainly:
a query whose tokens are all outside the matrix still misses, while the client
uses cosine only over the shipped matrix. `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:66`
This is a coverage contract, not a promise that every Spanish, Catalan,
Hungarian, or English paraphrase is semantically understood.

The compiler should consequently derive and fingerprint the actual closed
vocabulary consumed by the shared search controller, and report at least the
term count, token inventory, model dimension, vocabulary fingerprint, and the
number of query terms that cannot be represented. Those measurements are
implementation acceptance evidence, not new product vocabulary: arbitrary
queries cannot be pre-embedded, and the existing architecture only precompiles
a finite term-to-result mapping. `.vault/research/2026-06-10-docs-terminology-search-research.md:122-129`

### Model2Vec supplies a viable build-time mechanism, but its full token table cannot ship

The existing model survey identifies `minishlab/potion-multilingual-128M` as a
Model2Vec candidate under the MIT licence, with 256 dimensions and 101-language
coverage including en/es/ca/hu. Its described inference is tokenisation,
lookup, and averaging rather than a neural network at read time, which fits the
build-time-only boundary. The same survey reports 90.86% of LaBSE on its cited
MTEB comparison, but that benchmark is prior research evidence, not a result
reproduced by P02.S03. `.vault/research/2026-06-10-docs-terminology-search-research.md:366-376`

The model's full static vocabulary is not the project's closed vocabulary. The
official model revision `e7421cd79c75fc506b88bb75723ae0a234994720` declares
`apply_pca: 256`, `hidden_dim: 256`, `normalize: true`, and a 512,361,560-byte
F32 tensor; the model card identifies MIT licensing, 101 trained languages, and
256-dimensional output. `https://huggingface.co/minishlab/potion-multilingual-128M/commit/e7421cd79c75fc506b88bb75723ae0a234994720`
The RAG-grounded candidate review also found a 500,353-token static table and an
approximately 18.6 MB tokenizer. A full int8 table would therefore be about
128,090,368 bytes (roughly 122 MiB) before metadata, far beyond the 3 MB shipped
bound. The compiler must select and fingerprint only the tokens derived from the
project's closed search vocabulary; it must never serialize the model's full
token inventory. The model page simultaneously displays a 102-language tag and
describes 101 trained languages, so the exact revision/configuration is part of
the pin rather than an inferred language count. `https://huggingface.co/minishlab/potion-multilingual-128M`

For the earlier approximately 5,000-project-term estimate, a raw 256-dimensional
int8 payload is about 1.28 MB before metadata and serialization overhead; the
prior survey gives a broader 1.3–2.5 MB estimate. This is an envelope
calculation, not a measured artifact size, and it says nothing about the model's
500k-token table. The compiler must measure the actual project-token inventory,
committed bytes, and provenance stamp, and reject the result if it exceeds the
3 MB upper bound.

`Qwen/Qwen3-Embedding-0.6B` is an Apache-2.0 dense-model comparison point: the
existing research records 1024 dimensions and an approximately 1.2 GB model
footprint, while also noting the resident RAG wrapper's CUDA refusal. It is
therefore plausible as a dev-box oracle but not as a shipped reader dependency;
at the same 5,000-term estimate, a direct int8 matrix would already be about
5.12 MB before metadata. `.vault/research/2026-06-10-docs-terminology-search-research.md:89-101`
The size comparison does not authorize dimensionality reduction or a different
quantisation scheme; those are uninvestigated choices for the ADR/compiler
design.

Two smaller Model2Vec alternatives remain comparison points, not selected
models: `M2V_multilingual_output` is MIT and 256-dimensional but has a roughly
1.56 GB model tree, while `potion-retrieval-32M` is MIT and 512-dimensional but
English-only. Their model footprints and language trade-offs do not remove the
need for a project-token subset and an exact revision pin. `https://huggingface.co/minishlab/M2V_multilingual_output`
`https://huggingface.co/minishlab/potion-retrieval-32M`

The SPLADE path is not a candidate: the same research records `naver/splade-v3`
as CC BY-NC-SA 4.0 and gated, and the accepted rule bars NC/ND/gated-derived
data. `.vault/research/2026-06-10-docs-terminology-search-research.md:97-100`
Likewise, a reranker is a different model role and is not evidence for a term
embedding matrix merely because its licence is Apache-2.0.

### The shipped artifact is narrowly bounded and must remain separate from RAG

The accepted boundary places vaultspec-rag, preprocessing, sweeping, and
laundering on the dev side; only light reviewable data crosses into the build,
and the RAG service, model downloads, raw oracle outputs, and search server
remain out of the shipped surface. `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:57-61`
The amended licence rule narrows the exception further: a matrix may ship only
in built docs, never the wheel, only as plain data from a pinned named MIT or
Apache-2.0 model over project vocabulary, with exact revision, licence,
vocabulary fingerprint, and serialized size in its provenance stamp, and with a
3 MB maximum. `.vaultspec/rules/shipped-search-licence-clean.md:9-20`
This rules out shipping model weights, vectors from the RAG oracle, sparse maps,
raw scores, or the generated Pagefind index as substitutes for the matrix.

The next decision record must settle the exact model revision and encoding
against this evidence, while the implementation must prove token coverage and
the serialized-size/licence gates from real generated data. No model download,
benchmark, matrix generation, browser probe, test, or deployment was performed
for this research step.

### The compiler can be built before the model is ratified, but the artifact cannot

The architecture review of this evidence recommends a model-agnostic compiler
first, with model selection and artifact acceptance kept as a measured gate. Its
minimum plain-data contract is a schema version; model repository and immutable
revision; SPDX licence; canonical vocabulary hash and count; dimension;
quantisation algorithm and version; deterministic row order; per-row symmetric
scale; int8 values; serialized byte count; and artifact hash. The build-side
float32 input must reject NaN, infinity, zero vectors, and dimension mismatch,
then normalize, apply a specified symmetric scale, round deterministically, and
clamp to `[-127, 127]`. This is an implementation recommendation, not an ADR
decision; the existing corpus does not yet establish acceptable cosine-drift or
recall thresholds for quantisation.

The acceptance boundary should hard-fail above 3,000,000 serialized bytes and
should require exactly one finite, non-zero row for every admitted projected term
in every shipped locale, with explicit subword/token counts and no silent token
dropping or fallback row. The unquantized and int8 paths should be compared over
the committed held-out set and by locale/record kind before a matrix is accepted;
the numeric drift limits still require measurement and ratification. The compiler
must remain under dev tooling and emit only the bounded plain-data artifact; the
browser reads data, never model weights, and neither side invokes or imports
vaultspec-rag. `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:57-65`
`dev/docs/terminology/_sweep.py:167-209` `.vaultspec/rules/shipped-search-licence-clean.md:9-20`

## Sources

- `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md:57-66`
- `.vault/adr/2026-07-13-docs-terminology-search-adr.md:115-123`
- `.vault/audit/2026-07-13-docs-terminology-search-audit.md:49-68`
- `dev/docs/terminology/_miss_rate.py:44-46`
- `dev/docs/terminology/_miss_rate.py:168-235`
- `.vaultspec/rules/shipped-search-licence-clean.md:9-20`
- `.vault/research/2026-06-10-docs-terminology-search-research.md:89-129`
- `.vault/research/2026-06-10-docs-terminology-search-research.md:366-376`
- `https://huggingface.co/minishlab/potion-multilingual-128M`
- `https://huggingface.co/minishlab/potion-multilingual-128M/commit/e7421cd79c75fc506b88bb75723ae0a234994720`
- `https://huggingface.co/minishlab/M2V_multilingual_output`
- `https://huggingface.co/minishlab/potion-retrieval-32M`
