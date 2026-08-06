---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:18e03bfb634adef508eeae4721dd3dfa96adada15ac7fc580e50d12be722fb1f'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# `user-docs-search-consolidation` audit: `P02.S04 bounded static matrix compiler review`

## Scope

Read-only review of the full new `dev/docs/terminology/_static_matrix.py` source and the
`dev/docs/terminology/__init__.py` export diff for P02.S04. The review was grounded by the
accepted `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md`, the P02.S03
`.vault/research/2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research.md`,
the active `.vault/plan/2026-08-01-user-docs-search-consolidation-plan.md`, and the P02.S04
execution record. Semantic discovery used the working vaultspec-rag path after the codebase
alias rejected its request; no reindex was performed. No Python code was modified and no
tests, builds, model downloads, sweeps, browser probes, deployment, or runtime gates were
run. The unrelated shared-worktree WIP was left untouched.

Overall verdict: NOT PASS. The compiler seam is directionally correct and contains no
critical or high-severity issue, but the medium findings below must be resolved before the
artifact can be treated as a strict, self-attesting deterministic matrix contract.

## Findings

### schema-markers | medium | Loader accepts artifacts with omitted required schema markers

`StaticEmbeddingMatrix` gives `schema_version`, `quantization_algorithm`, and `row_order`
defaults in `dev/docs/terminology/_static_matrix.py:170-176`. Because
`load_static_embedding_matrix` passes JSON directly to Pydantic at
`dev/docs/terminology/_static_matrix.py:319-328`, a payload omitting any of those fields is
accepted and silently rehydrated with the defaults. The later artifact-hash check operates
on that rehydrated model, so `extra="forbid"` does not restore required-field presence.
This weakens the schema/version and quantisation-provenance attestation for committed data.
Make these markers required on the artifact input or add an explicit presence check before
validation, while retaining the constants for the compiler's emitted payload.

### canonical-observation-identity | medium | Token inventory can be attached to a differently spelled term

The compiler calls `_canonical_term(observation.term)` and uses that result as the lookup
key at `dev/docs/terminology/_static_matrix.py:270-280`, but it retains the original
observation, including its token ids and vector, when it later builds the row and inventory.
It therefore accepts a provider response whose term is only NFKC/casefold-equivalent to the
requested canonical term. If the provider tokenized that alternate spelling differently,
those ids and values are recorded under the canonical row without a rejection. Require the
provider observation to echo the exact canonical term supplied to `embed`, or otherwise
prove that the tokenization was performed on that exact term before accepting the row.

### float32-scale-contract | medium | Deserialization does not enforce the declared float32 scale encoding

The compiler emits a float32-rounded scale through `_as_float32` in
`dev/docs/terminology/_static_matrix.py:344-371`, but `QuantizedEmbeddingRow.scale` only
checks that the loaded value is finite and positive at `dev/docs/terminology/_static_matrix.py:143-160`.
An artifact can therefore carry an arbitrary finite JSON/Python binary64 scale while still
claiming `symmetric-per-row-int8-f32-v1`. That permits a loaded matrix to bypass the exact
deterministic quantisation representation promised by its algorithm marker. Validate a
float32 round-trip (or an equivalent canonical scale encoding) on every deserialization
path, not only on the compiler's own output path.

### raw-artifact-canonicality | medium | Loader validates a canonical projection rather than the bytes on disk

`load_static_embedding_matrix` reads `payload` but only calls `model_validate_json`; the
invariant compares `serialized_bytes` with `len(self.to_json_bytes())`, not with the raw
`payload` length or byte-for-byte canonical serialization. Leading/trailing JSON whitespace
or another accepted formatting variant can therefore be loaded, while the declared size
still describes the reserialized form. A committed file could exceed the 3,000,000-byte
bound without the size stamp reflecting its actual bytes, and byte determinism is not
enforced at the load boundary. Require the raw payload to equal `to_json_bytes()` and bind
the declared size to those exact bytes before accepting an artifact.

### scope-boundary | low | PASS: the source remains a dev-only, model-agnostic seam

PASS for the explicit P02.S04 boundary. The new module imports only standard-library
facilities and Pydantic; it has no model package, model download, vaultspec-rag, browser,
runtime, or product import. The export diff is confined to the dev terminology package.
There is no provider adapter, selected model, generated matrix, client cosine tier, licence
gate, or test change in this source payload, which is consistent with the execution record's
no-model/no-runtime/no-tests constraint and with the accepted dev-side/build-side boundary.

### compiler-contract | low | PASS: core canonicalization, coverage failures, quantization, and size checks are present

PASS for the intended source seam. Vocabulary terms are NFKC-normalized, whitespace-folded,
case-folded, deduplicated, UTF-8-byte sorted, and fingerprinted; provider observations are
required to be finite, token-count-consistent, one-per-term, and free of missing, duplicate,
or foreign rows; vectors are float32-normalized and symmetrically quantized to bounded int8
values; and model, revision, licence, dimension, token inventory, algorithm, row order,
vocabulary hash, artifact hash, and serialized size are represented. The issues above are
strictness gaps around those otherwise correctly identified invariants, not a missing
compiler architecture.

### vocabulary-source-provenance | low | Fingerprinting does not prove the vocabulary came from the project corpus

The compiler fingerprints whatever `Iterable[str]` its caller supplies at
`dev/docs/terminology/_static_matrix.py:230-249`; it does not bind that input to the
authoritative closed vocabulary enumerated by the existing terminology sweep or record a
project-authored/project-bundled vocabulary source. The accepted rule and P02.S03 research
require that provenance, while the fingerprint alone proves only identity of the supplied
strings. Keep this as a follow-on acceptance gate: the eventual build adapter/licence gate
must source the vocabulary from the shared controller's authoritative enumeration and
verify that the stamped fingerprint is the one actually consumed.

### token-coverage-evidence | low | Per-row token inventory exists, but aggregate unrepresentable-query evidence remains outstanding

The source records token ids and counts per row, satisfying the P02.S04 inventory seam, but
it does not and cannot by itself report the research-requested count of query terms that are
unrepresentable without the later shared-controller vocabulary, client cosine tier, and
held-out evaluation. This is correctly deferred to P02.S05-P02.S07 rather than a reason to
add runtime or test behavior here; it remains an explicit residual acceptance item.

### 2026-08-05-remediation-review | low | PASS: all four prior medium findings are fixed

Remediation verdict: **PASS** for the four prior `MEDIUM` findings, with no remaining
`CRITICAL`, `HIGH`, or `MEDIUM` issue in this bounded review. `schema-markers` is fixed:
`StaticEmbeddingMatrix` now declares `schema_version`, `quantization_algorithm`, and
`row_order` as required literal fields at `dev/docs/terminology/_static_matrix.py:176-182`,
so `load_static_embedding_matrix` cannot silently supply omitted markers through
`model_validate_json` at `dev/docs/terminology/_static_matrix.py:329-337`.
`canonical-observation-identity` is fixed: the compiler requires the provider term to be
an exact canonical echo and a member of the requested canonical vocabulary at
`dev/docs/terminology/_static_matrix.py:276-283`, before retaining its token inventory or
vector. `float32-scale-contract` is fixed on deserialization: the scale validator performs
an IEEE-754 binary32 pack/unpack round trip and rejects any finite value that does not
round-trip exactly at `dev/docs/terminology/_static_matrix.py:158-168`. Finally,
`raw-artifact-canonicality` is fixed at the loader boundary: the raw bytes must equal the
canonical newline-terminated JSON and the declared byte count must equal those exact raw
bytes at `dev/docs/terminology/_static_matrix.py:329-343`.

The explicit boundary remains **PASS**: `dev/docs/terminology/_static_matrix.py` remains
dev-only and model-agnostic, importing only standard-library facilities and Pydantic; the
package export in `dev/docs/terminology/__init__.py:91-110` exposes the compiler seam only
through the dev terminology package. No model provider, model download, vaultspec-rag,
browser, runtime, client cosine tier, generated matrix, or test change was introduced or
reviewed as part of this remediation. The shared-worktree unrelated WIP remains untouched.
The two previously recorded deferred follow-ons, `vocabulary-source-provenance` and
`token-coverage-evidence`, remain **LOW** and belong to the later P02.S05-P02.S07
integration/licence/evaluation work; they do not reopen the four remediated findings.

### assembled-input-identity | low | PASS: source handoff fingerprints are revalidated

The `Rung2CompilationInputs` boundary now recomputes canonical vocabulary and query-token fingerprints and requires both to match the embedded `Rung2InputProvenance` before the provider-backed compiler receives the assembled inputs. This closes accidental mismatch between the authoritative input assembly and its stamped identity without claiming that a provider artifact or measured matrix exists. The vocabulary-source and token-coverage evidence gates remain open as previously recorded.

## Recommendations

Resolve `schema-markers`, `canonical-observation-identity`, `float32-scale-contract`, and
`raw-artifact-canonicality` before accepting a committed matrix artifact. Preserve the
current dev-only/model-agnostic boundary, then close `vocabulary-source-provenance` and
`token-coverage-evidence` in the P02.S05-P02.S07 integration and licence/evaluation gates.

## 2026-08-05 source continuation: direct-construction invariant audit

Fresh `vaultspec-rag` semantic grounding over the P02.S04 execution record, static-matrix audit, accepted Rung-2 contract, and bridge/input records, followed by exact `vaultspec-rag` code-file reads, audited the direct model-construction boundary. `StaticEmbeddingMatrix` already requires matching dimension/counts, canonical unique UTF-8 row order, complete token inventory alignment, complete unique query-token order, row dimension equality, vocabulary/query-token fingerprints, artifact hash, and canonical serialized byte count. Its nested row models already reject non-finite or zero-valued vectors, non-float32 scales, and inconsistent token-id counts. `RecordManifest`, `SemanticBridge`, and `Rung2SearchBundle` likewise enforce count/order/hash/manifest-link invariants.

The codebase semantic endpoint still rejects the server's `codebase` alias with `unknown_source_type`; no reindex or bypass was used. The vault semantic results and exact code-file retrieval provide the grounding for this bounded source audit. No additional source defect is justified, so no P02.S04 code correction was made.

Scoped static verification passed: Ruff, basedpyright (0 errors, 0 warnings, 0 notes), Python AST parsing, and focused diff whitespace validation. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open for the pinned provider/package/model/tokenizer evidence, generated artifact, licence/quantization/held-out acceptance, and runtime gates.
