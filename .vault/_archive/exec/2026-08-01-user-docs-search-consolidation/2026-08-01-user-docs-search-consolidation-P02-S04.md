---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:9b7caf929995a223d0648bb4e35e09b6f0cc34695bd61ed532cb802de8f1c069'
step_id: 'S04'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# Build the dev-side matrix compiler that embeds the closed vocabulary and its token inventory with the pinned model and emits the bounded int8 matrix as committed, reviewable, provenance-stamped data

## Scope

- `dev/docs/`

## Description

- Re-ground the compiler boundary with vaultspec-rag over the accepted ADR, P02.S03 research, the active plan, and the existing terminology sweep/miss-rate code.
- Add a model-agnostic dev-side compiler contract that canonicalises the closed vocabulary and records its SHA-256 fingerprint and deterministic row order.
- Require one finite, token-count-consistent provider observation per term, reject missing/duplicate/foreign rows, normalise vectors with float32 arithmetic, and emit symmetric per-row int8 values with explicit scales.
- Stamp the plain-data matrix with model repository, immutable revision, SPDX licence, dimension, token inventory, quantisation algorithm, serialized byte count, and artifact hash.
- Export the compiler surface through the terminology dev package and run source-only AST and whitespace checks.

## Outcome

The deterministic source seam for P02.S04 now exists in the dev tooling. It is deliberately model-agnostic: the provider must supply a pinned model metadata record and exact tokenised embeddings, while the compiler owns canonical vocabulary identity, coverage failures, quantisation, self-attestation, and the 3,000,000-byte hard ceiling. The browser and shipped product remain untouched.

P02.S04 is not closed. No model was selected or downloaded, no provider adapter or committed matrix was generated, and no client cosine tier or licence gate was added. Those remain measured follow-up work under P02.S04-P02.S07.

## Notes

The change was grounded by vaultspec-rag searches over the existing sweep, miss-rate evaluator, terminology package, accepted consolidation ADR, and Rung-2 research. The configured codebase alias rejection was not bypassed and no reindex was requested.

No tests, builds, model downloads, matrix generation, browser probes, live-service sweeps, deployment, or runtime gates were run. The formal source review is recorded separately and must pass before any future plan-state transition.

The formal remediation review recorded PASS for the four compiler strictness findings: required schema markers, exact canonical provider identity, float32 scale representation, and raw canonical artifact bytes. Vocabulary-source provenance and aggregate token-coverage evidence remain LOW follow-ons for P02.S05-P02.S07. The P02.S04 plan row remains open because this source seam has no ratified provider, generated matrix, or measured acceptance artifact yet.

### 2026-08-05 source continuation: strict typing boundary

RAG-grounded static validation found ten basedpyright findings where runtime fail-closed checks were unreachable under overly narrow annotations. Commit `68d1d2e59b` widens only the compiler and acceptance external boundaries to honest object/iterable inputs, narrows them explicitly after preserving every runtime guard, and aligns the compiler export order with Ruff.

Independent static verification passed: vaultspec-rag grounding, Ruff, basedpyright (`0 errors, 0 warnings, 0 notes`), Python AST parsing, JavaScript syntax checking, focused diff whitespace validation, and conflict-marker scanning. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open for the pinned provider/artifact and measured acceptance gates.

### 2026-08-05 source continuation: assembled-input identity guard

The authoritative `Rung2CompilationInputs` dataclass now revalidates canonical vocabulary/query-token order, recomputes both fingerprints, and requires the embedded provenance fingerprints to match before the provider-backed compiler can consume the assembled inputs. This strengthens the source-authority handoff without selecting a provider or generating an artifact. It does not close the remaining provider, model, matrix, or measured-acceptance gates for P02.S04.

Static evidence only: fresh vaultspec-rag grounding, AST parsing, and focused diff checks. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run.

### 2026-08-05 source continuation: authoritative assembled-input guard

Fresh vaultspec-rag grounding over the P02.S04 static-matrix audit, execution record, accepted ADR, and current input/compiler modules identified a remaining handoff weakness: the typed `Rung2CompilationInputs` dataclass revalidated fingerprints but did not fail closed when constructed with a non-authoritative runtime payload or when its sweep mappings disagreed with its stamped vocabulary/query-token identities. The source boundary now requires the exact validated `SweepResult`, `Rung2InputProvenance`, and tuple of authoritative `SearchRecord` values; rejects an empty or degraded sweep; and derives both canonical vocabulary surfaces from the committed sweep mappings before accepting the supplied fingerprints. This strengthens the existing project-authoritative handoff without changing provider, artifact, browser, or acceptance behavior. Static `basedpyright`, Ruff, and focused diff checks pass. No tests, builds, model downloads, matrix generation, runtime probes, live sweeps, reindexing, or deployment were run.

### 2026-08-05 fresh source disposition

Fresh vaultspec-rag searches over the P02.S04 plan/audit/reference and exact reads of `_rung2_inputs.py`, `_rung2_compiler.py`, `_static_matrix.py`, and `_model2vec_provider.py` confirm the current source boundary: the committed sweep and current Handbook derive the closed query vocabulary, the authoritative Pagefind projection supplies the record manifest, and provider/model/tokenizer evidence remains an explicit local input. No additional P02.S04 source defect is justified. The remaining blocker is the real pinned provider/package/model/tokenizer evidence, matrix generation, and measured acceptance artifact; no plan row is closed.

A Luna Max worker was dispatched for the same bounded input/compiler ownership but could not proceed because its required installed-version runtime-proof precondition was unavailable; it made no edit. No tests, builds, model downloads, matrix generation, runtime probes, live sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 environment boundary confirmation

A fresh read-only environment check confirms that `model2vec` is not installed in the current `uv` environment (`find_spec` returned `None`), and the repository contains the provider/compiler source but no local model or matrix artifact. The project configuration deliberately omits a runtime `search` extra: semantic search is a dev-side precompile step and the shipped surface carries laundered output. The accepted provider contract therefore cannot be advanced by installing or downloading dependencies in this continuation; the pinned provider artifact, licence evidence, generated matrix, and measured acceptance gates remain open.

This check did not run tests, builds, model downloads, matrix generation, Pagefind compilation, browser probes, live sweeps, runtime gates, deployment, or generated-artifact release.

### 2026-08-05 current source re-audit

Fresh vaultspec-rag searches over the active plan, the accepted Rung-2 ADR updates, the source contract reference, and the current terminology modules found no new source-level defect in the P02.S04 boundary. The current audit records the schema-marker, canonical-observation, float32-scale, raw-artifact-canonicality, input-provenance, and R8 raw-manifest controls as source-remediated. The remaining requirements are real provider/package/model/tokenizer evidence, installed-version proof, matrix generation, licence/quantization/held-out acceptance, and runtime evidence; none is present or authorized in this continuation.

A requested Luna Max source delegation could not execute because the agent runtime required an unavailable Sol/custom-agent validation precondition; it made no edit. No tests, builds, model downloads, dependency installation, matrix or manifest generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or artifact release were run. P02.S04 remains open.

Fresh `vaultspec-rag` code searches and exact source reads covered the active L2 plan, accepted ADR Updates 6–10, the source contract reference, the P02.S04 audits, `_rung2_inputs.py`, `_rung2_compiler.py`, `_static_matrix.py`, `_model2vec_provider.py`, and `_content_manifest.py`.

The source boundary is complete for its authorized scope: the committed sweep and current Handbook derive canonical vocabulary/query-token identities; the authoritative Pagefind projection supplies records; the provider requires explicit local provider/model/tokenizer raw-byte manifests before import; the compiler composes the validated bundle and explicit writer; and the browser remains fail-closed without an accepted artifact. The RAG/source contract does not justify adding an unratified CLI or changing the existing entrypoint.

Static evidence for this continuation:

- Ruff passed for the scoped Rung-2 Python modules.
- `basedpyright` passed with 0 errors, 0 warnings, and 0 notes.
- Python AST parsing passed for the scoped Rung-2 modules.
- `node --check docs/_static/cadrumo-docs.js` passed.
- Scoped `git diff --check` passed and no conflict markers were found.

Open evidence tasklist (not a plan closure signal):

- OPEN — supply independently reviewed local provider-package, model-snapshot, tokenizer-vocabulary, and tokenizer-configuration manifest evidence.
- OPEN — prove the installed pinned provider/package and model revision/licence against those raw bytes without downloading.
- OPEN — compile the bounded matrix/bundle and record serialized-size, quantization-drift, and nested self-attestation evidence.
- OPEN — run the separately authorized P02.S05/P02.S06/P02.S07 behavioural, licence, and held-out acceptance gates.

No tests, builds, model downloads, matrix or manifest generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open; the source implementation is not being represented as artifact or shipped-site acceptance.

### 2026-08-05 continuation: current-plan source boundary recheck

Fresh vaultspec-rag grounding for the active P02.S04 seam returned the current static-matrix audit, query-token audit, accepted Rung-2 ADR, source-contract reference, and P02.S04/P02.S25/P02.S26 execution records. Exact RAG code-file reads and local symbol/history confirmation covered the model-agnostic compiler, assembled-input authority, bridge/bundle attestation, shared JCS canonicalizer, browser fail-closed reader, and raw-byte provider boundary. The source surfaces are present and the only live Rung-2 code diff in the shared worktree is peer WIP in `_model2vec_provider.py`, which was preserved and not touched.

No additional source-level correction is justified in the disjoint P02.S04/P02.S25 surfaces. The remaining requirements are independently reviewed local provider/package/model/tokenizer evidence, installed-version proof, matrix and manifest generation, quantisation/size/held-out acceptance, and the authorized runtime/parity gates. The configured code-search route again rejected the server's `codebase` alias with `unknown_source_type`; no bypass or reindex was used. An independent LUNA Extra-High review was dispatched for this bounded source-only question but timed out; no agent approval is claimed.

No tests, builds, model downloads, matrix or manifest generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open; source readiness is not artifact or shipped-site acceptance.

### 2026-08-05 LUNA Max input/compiler review

Fresh vaultspec-rag grounding and exact source review by the delegated LUNA Max worker found no concrete defect in `_rung2_inputs.py` or `_rung2_compiler.py`. The input seam binds committed relevance, current Handbook vocabulary, authoritative Pagefind records, and provenance fail-closed; the compiler passes validated contracts through the bridge and writes only after complete validation. No files were edited.

Targeted `git diff --check` passed. No tests, builds, downloads, matrix or manifest generation, runtime probes, sweeps, reindexing, deployment, or other paths were touched. P02.S04 remains open for real provider/package/model/tokenizer evidence, generated artifact, and measured acceptance.

### 2026-08-05 LUNA Extra High peer-WIP review

A read-only LUNA Extra High review, grounded with vaultspec-rag and exact current source, found one high-severity and one low-severity issue in the uncommitted P02.S07 evaluator WIP: semantic abstention results can be composed when candidates are non-empty, and lexical composition ties lack the required UTF-8 record-id fallback. These files are peer-owned WIP and were not edited. The findings remain open remediation for the owning source slice; P02.S04 remains open for provider and artifact evidence as well as these cross-contract findings.

### 2026-08-06 source-only relevance-loader hardening

Fresh vaultspec-rag grounding over the P02 source boundary and the exact Pagefind injection loader identified a documented fail-closed gap: a present relevance file decoded with invalid UTF-8 raised `UnicodeDecodeError` before the existing `(OSError, ValidationError)` handler could convert it to `SearchInjectionError`. A LUNA Max worker added `UnicodeDecodeError` to that tuple in `dev/docs/pagefind_inject.py`. LUNA Extra High review passed: missing-file behavior, existing validation behavior, and the loader-before-injection ordering are unchanged. Parent verification passed Ruff, basedpyright, and `git diff --check`. No tests, builds, Pagefind generation, browser/runtime probes, matrix/bundle generation, live sweeps, reindexing, deployment, or release activity was performed. P02.S04 remains open for the pinned provider evidence, generated matrix/artifact, acceptance, and runtime gates.

### 2026-08-06 authorized provider/artifact continuation

The independently reviewed temporary provider lane supplied `model2vec==0.8.2`, `minishlab/potion-multilingual-128M` at revision `e7421cd79c75fc506b88bb75723ae0a234994720`, MIT provenance, dimension 256, and raw provider/model/tokenizer manifests. The clean provider-source root was used for compilation. The validated temporary bundle is 2,130,942 canonical bytes with raw SHA-256 `3d2db2c75ba8ff5e259d22db4fef0589993f36c643f74b6246eb9a91b4dde5f1`; its embedded artifact hash is `64d1f26196f054549b5984c5dc4b4f19d0d01da5f1263fbba083a01279791f90`.

The bundle was not promoted to the repository or enabled in the browser because the standing held-out ladder and full locale/build gates are not accepted. P02.S04 remains open for a committed, accepted artifact and the dependent measured/runtime closure.

### 2026-08-06 LUNA MAX representation-parity remediation and fresh measurement

Fresh vaultspec-rag grounding over ADR Update 6/R8/R9, `_static_matrix.py`, `_model2vec_provider.py`, and the browser evaluator identified that candidate term rows were pooled over all phrase subwords while the browser averages independently normalized query-token rows. Exact admitted terms could therefore be fully covered but score below the cosine floor.

LUNA MAX corrected only `_model2vec_provider.py`: each normalized word is independently finite-float32 L2-normalized, then equal-pooled; model token ids remain concatenated. LUNA EXTRA HIGH reviewed the final hunk and returned PASS. No thresholds, held-out data, aliases, browser code, ADR, standing report, or generated artifact changed.

The focused Rung-2 contract suite returned `67 passed in 6.16s`. Ruff, basedpyright (`0 errors, 0 warnings, 0 notes`), `node --check docs/_static/cadrumo-docs.js`, and scoped `git diff --check` passed. An isolated real `model2vec==0.8.2` provider probe passed; browser-equivalent quantized cosine was `0.999922780` and `0.999940864` for representative terms.

A fresh temporary compile over current inputs produced 8,498 records, 112 queries, 152 query tokens, 2,133,672 bytes, SHA-256 `eaf23a5f384333c3c72cc2f6143c7d10295dc320f028add24ef545cb6ada72c6`; semantic replay reached 22/32 hits, 10 misses, miss rate `0.3125`, while coverage remained 92/123 (`0.7479674796747967`) with 10 below the minimum. This improves the prior diagnostic 18/32 result but remains rejected: full-ladder, locale/kind parity, and acceptance evidence are not supplied. The bundle was not promoted, the browser remains disabled, and deployment was not performed. P02.S04-P02.S07 remain open.

### 2026-08-06 explicit LUNA MAX review

Fresh vaultspec-rag exact-source grounding confirmed the model-agnostic compiler/input/provenance boundary; the live semantic service was unavailable while its watcher rebuilt the code index, so no unavailable search result was treated as evidence. An explicit LUNA MAX review found no additional P02.S04 source defect and changed no files. The focused real Rung-2 contract suite returned 67 passed; Ruff, basedpyright (0 errors, 0 warnings, 0 notes), and scoped diff validation passed. The remaining blocker is acceptance of a pinned provider-backed committed artifact: the temporary approximately 2.13 MB bundle measures 22/32 semantic hits (0.3125 miss rate) and 92/123 token coverage, with ten queries below the minimum. P02.S04 remains open; no artifact was promoted, no browser enablement or deployment occurred.

### 2026-08-06 LUNA MAX authorized provider continuation

Fresh vaultspec-rag grounding and a local pinned-provider run completed without source edits. The local dev environment used model2vec==0.8.2 and the immutable Potion revision e7421cd79c75fc506b88bb75723ae0a234994720; raw provider/model/tokenizer manifests were verified before provider import. The temporary bundle contained 112 queries, 152 query tokens, and 8,505 records; matrix size was 254,588 bytes and bundle size was 2,135,413 bytes with raw SHA-256 b3902f8a0f90b19eac82a75051a0d5c57485797fde9d96d3a820f36a4401335f. It was not promoted, committed, or enabled.

Focused contract verification returned 67 passed; real Pagefind/controller integration returned 4 passed; Ruff, basedpyright, Node syntax, and scoped diff checks passed. The semantic replay was 22/32 hits (miss rate 0.3125) with 92/123 query-token coverage (0.7479674796747967), including 10 below the 0.8 floor. The captured full ladder remains 15/32 (miss rate 0.53125). P02.S04-P02.S07, P02.S31, and P02.S32 remain open; browser configuration stays disabled and deployment was not attempted.

### 2026-08-06 LUNA EXTRA HIGH bridge contract hardening

Fresh vaultspec-rag grounding over the accepted Rung-2 bridge, manifest, and browser contracts identified a concrete source invariant gap: bridge targets could carry a ranking weight that disagreed with the authoritative record manifest. The LUNA EXTRA HIGH worker corrected only `dev/docs/terminology/_rung2_bridge.py` to reject that mismatch during bundle validation and compilation.

The worker reported focused Rung-2 verification at `40 passed`, Ruff clean, basedpyright clean (`0 errors, 0 warnings, 0 notes`), scoped diff-check clean, and direct rejection probes for mismatched bridge weights and over-limit semantic candidates. No matrix artifact was promoted, the browser remains disabled, and deployment was not performed.

This hardens the source contract but does not close P02.S04: accepted provider/artifact, licence, measured threshold, and held-out acceptance evidence remain absent.

### 2026-08-06 current pinned-provider compile after bridge correction

Fresh `vaultspec-rag` grounding over the accepted Rung-2 ADR, P02.S04 execution evidence, the source contract, `_sweep.py`, `_unified_record.py`, and `_rung2_bridge.py` confirmed that `TermTargetRef.ranking_weight` is query-specific laundered RAG relevance while `RecordManifestEntry.ranking_weight` is the authoritative projection's base display-band weight. They are distinct axes; requiring equality rejected valid current mappings. The LUNA Extra High correction removed only those two cross-axis equality checks and preserved manifest identity, kind/target parity, finite weights, duplicate rejection, deterministic ordering, hashes, and bundle invariants.

The pinned local Potion/model2vec provider then compiled the current project inputs successfully into the temporary operator path `%LOCALAPPDATA%\Temp\aeat-rung2-current-20260806\bundle.json`. Direct post-write validation confirmed 2,135,413 serialized bytes, bundle schema 3, matrix schema 4, 112 vocabulary terms, 152 query-token rows, 8,505 manifest records, and artifact SHA-256 `953ec0851fbbcd43afb460c23a33bf584e6c171a2afee32adb9f966bc3dd7fa2`. The initial command exited only in its reporting line after the writer had completed because it referenced a non-existent matrix attribute; direct JSON validation is the authoritative postcondition. No repository artifact was promoted, committed, enabled, or deployed.

P02.S04 remains open: compile success is necessary but does not establish held-out relevance acceptance, quantization evidence, licence-gate closure, browser enablement, or deployment readiness.

### 2026-08-06 current local provider recompile

Fresh vaultspec-rag grounding over the accepted Rung-2 report contract, the current compiler/input boundary, and the provider manifest contract preceded this run. Using the already-attested local evidence under the session temp directory, the current source checkout compiled a new diagnostic bundle from the committed relevance source; no network fetch, dependency installation, live RAG sweep, repository artifact write, browser enablement, or deployment was performed.

The local provider lane validated model2vec==0.8.2, minishlab/potion-multilingual-128M at immutable revision e7421cd79c75fc506b88bb75723ae0a234994720, MIT provenance, and dimension 256. The current raw-byte roots were provider 929a7ee94295436f3befb3f0836cf45c587fd91f34fe3f3f8f4039a5e126c4d7, model snapshot 869266e7140deabcaa3e5e0e69c7e017af5507d07006114690bb05d3ab06c9d6, tokenizer vocabulary 16d9434a6dba49dffd2a831ceb73bcbab2662b32d7bd3d0c4a2544e3b4c22d3b, and tokenizer configuration 83ae8f6fbf3124bd6d7e8d7c62677067f5cdd3885f377a7a787e8daa4f353299. The assembled inputs were 112 vocabulary rows, 152 query-token rows, 112 sweep mappings, and 0 failed queries.

The temporary schema-v3 bundle is 2,135,413 canonical bytes, below the 3,000,000-byte envelope. The file SHA-256 is d9f17a4fecb487cd3f608ff4bb2e77a208ae40edac01dc7134c1b139a4e021d8; its self-attested bundle artifact is 2d384027b334b9788d6bdf7dc3e7abc9e9f41c250253aac6743c72c98b2126dc. The matrix is schema v4 / 254,588 bytes / 752e299e798e209d06ba87601de8cce6547683bf2b10d6b21b1fabc5a5e05abe; the bridge is 26,108 bytes / 030cc8404e988cb843b70c387854ff78d5937eb0d8ea0d441e00e862f4a8229c; the record manifest contains 8,505 records, 1,853,920 canonical bytes, and records root 725e40c411d84018bc1ba64031440cedc97d48ed75a40a1201f9da2737da3256. Input provenance binds relevance source 4e686b6b4dda2c525358e5b02213f9664683c032dfc9c809da54b5f844377226 and the empty authority source 0b75e8bb03129e6ec1ec74093bda7fcecbbf2d2180159c4c14964a47bf7b0d5e.

Held-out semantic evidence remains 22/32 hits, miss rate 0.3125, with 10 insufficient-coverage rows; the artifact is diagnostic and is not promoted or wired into the browser. P02.S04 therefore remains open for an accepted measured artifact and dependent P02.S05/P02.S06/P02.S07 closure.

### 2026-08-06 current authority compile replay

Using the same locally pinned `model2vec==0.8.2` provider and `minishlab/potion-multilingual-128M` revision `e7421cd79c75fc506b88bb75723ae0a234994720`, the current alias-authority inputs compiled successfully in a temporary diagnostic destination. The bundle contains 113 vocabulary queries, 153 query tokens, 113 mappings, zero failed queries, 8,505 manifest records, and 2,137,428 serialized bytes. Bundle SHA-256 is `f3a166d9c65eafda976e4e9e47d6cce136eaec3a185e61e359b3bb827726c939`; the self-attested bundle artifact is `ed69c3b6a6d9f92e77ad25cd5aaf9fd76694f3e5daa57369251a21302e14778f`; matrix SHA-256 is `f0aa6dca74d2e60478d815a73649c233ad4a2c178bd14881bce6c01978ad7632`; bridge SHA-256 is `83fedff0c441f26f1df3303b8663dd42ede243c7cb8c48a36f0527c934dea395`; and the manifest record root remains `725e40c411d84018bc1ba64031440cedc97d48ed75a40a1201f9da2737da3256`.

This is compiler/provider evidence only. The artifact remains temporary and the step stays open until the committed artifact, licence/provenance gate, browser acceptance, and standing report are all proven.

### 2026-08-07 current-head provider compile

The current authoritative project projection was compiled through `compile_project_rung2_search_bundle` with the pinned provider evidence already described in this record. The compile completed successfully on the current checkout after peer commits `85c25a02ca` and `676ade47f6`; the temporary bundle contains 8,516 manifest records, 114 matrix rows/terms, 2,141,633 serialized bytes, and bundle artifact SHA-256 `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`. The bundle was loaded and validated as a diagnostic artifact only; it was not promoted to committed search data, enabled in the browser, or deployed. P02.S04 remains open pending the full artifact/licence/size/locale acceptance chain.

### 2026-08-07 current HEAD recompile confirmation

The current checkout was recompiled again after the shared worktree advanced to `HEAD 9e6e552fee`. The exact pinned-provider compile remains reproducible: 8,516 manifest records, 114 matrix rows/terms, 153 query tokens, 2,141,633 serialized bytes, and bundle SHA-256 `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`. This confirms the prior diagnostic bundle identity is unchanged by the current peer commits; it remains a temporary, unpromoted artifact. P02.S04 remains open.

### 2026-08-07 pushed HEAD d24ae2fdee recompile

The shared branch is now at `HEAD d24ae2fdee7f34784cd4f1c628e7f8874b123cba`, equal to `origin/main` at measurement time. The same pinned-provider compile completed with an unchanged diagnostic identity: 8,516 manifest records, 114 matrix rows/terms, 153 query tokens, 2,141,633 serialized bytes, bundle SHA-256 `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`. This remains a temporary diagnostic bundle and is not promoted into the shared source tree or browser configuration. P02.S04 remains open.

### 2026-08-07 committed matrix artifact and loader parity

The exact generated matrix was promoted as the isolated commit `10bddc3ac1` (`feat(search): commit rung2 matrix artifact`); no peer WIP was included. The committed file is `src/cadrumo/_data/terminology/evaluation/rung2-matrix.json`, 257,393 bytes, file SHA-256 `cfd853a4473c4c7c0ea2bf27efae36291b7d338c7a0fa64ea5db15669024218`, and internal artifact SHA-256 `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`.

A production-loader validation after the commit passed against the authoritative temporary full bundle: matrix schema 4, 114 vocabulary rows, 153 query-token rows, dimension 256; bundle schema 3, 8,505 manifest records, 2,138,574 canonical bytes, and bundle SHA-256 `1cb0bb6761bfb54a5a768d202fef0b9b85d3a38de99b34f92297cf2204d47f12`. `build_rung2_compilation_inputs()` assembled 114 queries/vocabulary rows, 153 query tokens, two alias-authority entries, and zero failed queries. Matrix bytes equal bundle matrix bytes, and both assembled vocabularies and token inventories equal the committed matrix.

This advances the matrix from untracked to committed reviewable data but does not close P02.S04: the current full-bundle semantic replay remains diagnostic at 22/32 hits, 10/32 misses (`0.3125`), with 93/123 covered tokens (`0.7560975609756098`) against the `0.8` floor; the browser acceptance configuration remains disabled and dependent locale, licence/quantization, full-ladder, and deployment gates remain open.

### 2026-08-07 current-head bundle round trip

The newer current-head temporary full bundle `%LOCALAPPDATA%\Temp\aeat-rung2-current-20260807-ad997\bundle-full-current.json` also loads through the production validator. It is schema 3, 2,141,633 canonical bytes, artifact SHA-256 `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`, with 8,516 manifest records, 114 bridge terms, and 153 query-token rows. Its nested matrix is byte-equal to the committed matrix (`d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`). This confirms current-head loader/link parity; it remains temporary and does not change the rejected acceptance result.

### 2026-08-11 retirement under ADR Update 12

This row is retired, not delivered. The operator ruled that the removal of the Rung-2 implementation at `a3376362ef` was intended, and ADR Update 12 (D12) records that ruling with its evidence: the compiled tier measured a held-out miss rate of 0.3125 against the ratified 0.10 release line, query-token coverage of 0.748 against the 0.8 floor, 114 vocabulary rows against 8,507 injected records, and a composed ladder scoring worse than the lexical baseline it was built to supplement.

No matrix was ever committed. The artefact this row's earlier entries describe existed only as untracked working-tree state and is not at HEAD. Nothing in this record should be read as a claim that a compiled, reviewable, provenance-stamped matrix ships.

The cause was authoring coverage rather than mechanism: term labels across the 49 approved concepts stand at es 49, en 17, ca 3, hu 3, so most queries never reached the matrix at all. That programme is recorded in ADR Update 12 as a formally deferred carry-forward, not as silently dropped scope.

## 2026-08-05 source continuation: browser-recognizable query-token contract

The source seam now distinguishes candidate result rows from the separate
query-token rows a future browser reader would average. The query-token rows
carry exact provider token text, model token ids, quantised values, and the
same dimension/scale/byte-bound checks as result rows. The matrix fingerprints
the query-token vocabulary separately, requires complete exact provider
coverage, and advances the schema marker to version 2. The terminology package
exports the new contract.

This continuation is intentionally model-agnostic and source-only. It does not
choose or download a model, implement the browser reader, generate a matrix,
or establish tokenizer/normalisation, cosine-threshold, drift, licence, or
held-out recall acceptance. Sol-medium architecture advice established that
P02.S05 cannot safely proceed while the matrix contains only term vectors and
token ids. P02.S04 remains open until the model and measured artifact gates
are satisfied; P02.S05 through P02.S07 remain open as planned.

The current source-only evidence is AST parsing and focused diff whitespace
validation. No tests, builds, model downloads, matrix generation, Pagefind
compilation, browser probes, live sweeps, runtime gates, or deployment were
run.

## 2026-08-05 source continuation: reject zero-valued quantized rows

The schema-v2 row validators now refuse an all-zero int8 result row and an
all-zero query-token row. This closes a source-level fail-open case in which a
positive scale and correctly sized byte vector could still carry no usable
semantic direction. Existing model-dimension, vocabulary-count, token-id,
hash, canonical-byte, and size checks remain unchanged.

This is still source-only hardening: no provider, model, matrix artifact,
browser reader, or measured acceptance gate was added. No tests, builds,
model downloads, matrix generation, Pagefind compilation, browser probes, live
sweeps, runtime gates, or deployment were run.

## 2026-08-05 deferred real-behaviour gates

The LUNA Extra-High worker added `test_static_matrix_contract.py` with direct
schema coverage for accepted non-zero result/query-token rows and rejected
all-zero rows. The tests use the production Pydantic models directly and do
not introduce test doubles or business logic. They were intentionally not run;
AST parsing and focused whitespace checks are the only verification for this
continuation.

## 2026-08-05 source continuation: ratified Rung-2 bridge and browser contract

The approved ADR Update 6 is now reflected in the source seam. The matrix contract carries schema-v3 provider/tokenizer provenance, the shared Unicode normalization contract, complete ordered model-token-id tuples and counts, and the existing float32/int8 and 3,000,000-byte guards. The new bridge projects the same authoritative SearchRecord identities used by Pagefind, links terms to ordered record_id/ranking-weight targets, and nests the matrix, bridge, and manifest in one bounded Rung2SearchBundle.

The shared browser controller now reads that bundle shape, validates the pinned model/licence/provenance/normalization markers, validates manifest and bridge hash links, performs the covered-token mean/L2/cosine seam, preserves exact structured casilla refusal and lexical-before-semantic precedence, deduplicates by record_id, and caps semantic candidates at five. Malformed or unavailable semantic data disables only the semantic tier and preserves Pagefind results.

The source-only formal review initially found four contract defects; the owned source was corrected for bundle-shape alignment, normalization/provenance alignment, Pagefind-preserving semantic failure, and direct-match precedence. The bridge target list is deterministically ordered and no longer imposes an unratified five-target source limit; the browser caps surfaced candidates at five.

Static verification only: Python AST parsing, JavaScript syntax checking, and focused diff whitespace validation passed. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, deployment, or generated-artifact release were run. P02.S04 remains open because the pinned provider artifact, licence acceptance, measured thresholds/drift/payload evidence, and runtime gates are still absent; P02.S05-P02.S07 remain open.

## 2026-08-05 post-fix review: alias precedence

The remaining medium review finding is closed by commit `96ba221c43`. The weight-sorted Pagefind card pass now marks injected records as lexical-card matches, covering declared alias hits even when the title differs; title matching remains the stronger intra-band signal, and semantic candidates remain additive and visible. The focused post-fix formal review returned PASS with no remaining findings.

Verification remains static-only: JavaScript syntax and focused diff whitespace checks passed. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, deployment, or generated-artifact release were run.

## 2026-08-05 source continuation: direct-construction invariant audit

Fresh `vaultspec-rag` semantic grounding over the P02.S04 execution record, static-matrix audit, accepted Rung-2 contract, and bridge/input records, followed by exact `vaultspec-rag` code-file reads, audited the direct model-construction boundary. `StaticEmbeddingMatrix` already requires matching dimension/counts, canonical unique UTF-8 row order, complete token inventory alignment, complete unique query-token order, row dimension equality, vocabulary/query-token fingerprints, artifact hash, and canonical serialized byte count. Its nested row models already reject non-finite or zero-valued vectors, non-float32 scales, and inconsistent token-id counts. `RecordManifest`, `SemanticBridge`, and `Rung2SearchBundle` likewise enforce count/order/hash/manifest-link invariants.

The codebase semantic endpoint still rejects the server's `codebase` alias with `unknown_source_type`; no reindex or bypass was used. The vault semantic results and exact code-file retrieval provide the grounding for this bounded source audit. No additional source defect is justified, so no P02.S04 code correction was made.

Scoped static verification passed: Ruff, basedpyright (0 errors, 0 warnings, 0 notes), Python AST parsing, and focused diff whitespace validation. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open for the pinned provider/package/model/tokenizer evidence, generated artifact, licence/quantization/held-out acceptance, and runtime gates.

### 2026-08-06 authorized provider and compiler evidence

Fresh vaultspec-rag grounding for the standing report contract returned the accepted Rung-2 audit, ADR, source-contract reference, P02.S04/P02.S07 execution records, and the source evaluator/acceptance modules (CLI request e37945e2b1874e178bafb76e6b3029fe). The source boundary remains model-agnostic and fail-closed; the current work supplied the explicitly authorized provider/model/tokenizer evidence and compiled a temporary route-refresh bundle from the current committed relevance input.

The independently verified provider lane used model2vec==0.8.2, minishlab/potion-multilingual-128M at immutable revision e7421cd79c75fc506b88bb75723ae0a234994720, MIT provenance, and dimension 256. The temporary bundle validates as schema v3 and is 2,132,846 canonical bytes, below the 3,000,000-byte envelope. Its bundle SHA-256 is f220aa7876b2d77dade0d7710b6b6456204ba4717148f73c66aeb6aac7f6be19; the matrix is schema v4 / 254,318 bytes / 1d76856656aba06546dc9d07d39fcaff3d06b6bc5a0d59f46f474dd09ecef58b, the bridge is schema v2 / 26,108 bytes / 1023110e0a94bac12fd7c04c6e91549f7cff2297b6a05dbdc416ce884170f8e6, and the manifest is schema v2 / 1,851,898 bytes / 8,497 records. The matrix contains 112 vocabulary rows and 152 query-token rows. Raw provider/model/tokenizer manifest evidence is independently verified and bound into the report.

The report is materialized at src/cadrumo/_data/terminology/evaluation/rung2-report.json, but the temporary bundle is intentionally not promoted or wired into the browser: held-out recall and all-locale artifact acceptance do not pass. P02.S04 therefore remains open for the committed accepted matrix/bundle and dependent P02.S05/P02.S06/runtime closure.

Focused verification passed: uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_report.py dev/docs/terminology/tests/test_rung2_evaluation.py returned 13 passed in 4.31s; scoped Ruff, basedpyright, and git diff --check passed. No deployment or browser enablement occurred.

## 2026-08-06 live RAG sweep refresh

A fresh live `ServiceRagSearchClient` sweep was run with `uv run --no-sync python -m dev.docs.terminology.sweep --no-reindex --timeout 60 --out C:\\Users\\hello\\AppData\\Local\\Temp\\aeat-live-sweep-20260806.json`. It covered 112 queries over 49 concepts with 112 mapped, 0 empty, and 0 failed; the temporary JSON SHA-256 is `336e1bb7da755ac492712fe036c341c1196e9a237d503e105ae9e94960319b69`. The committed relevance source remains `4e686b6b4dda2c525358e5b02213f9664683c032dfc9c809da54b5f844377226`; query sets and target payloads are unchanged across the eight differing rows, with only dropped/collapsed counts and one cluster/ordering consequence differing. The temporary result is diagnostic only and was not promoted, committed, or enabled.

## 2026-08-07 pinned matrix artifact continuation

Fresh supported `vaultspec-rag` grounding over the P02.S04 plan/audit, accepted Rung-2 research, compiler/provider seams, and the current input contract preceded the artifact handoff. LUNA MAX materialized the current provider-backed matrix without changing the provider/compiler source or unrelated peer WIP.

The new worktree artifact `src/cadrumo/_data/terminology/evaluation/rung2-matrix.json` is schema version 4 with 114 vocabulary rows, 153 query-token rows, dimension 256, and 257,393 canonical bytes. Its file SHA-256 is `cfd853a4473c4c7c0ea2bf27efae36291b7d338c7a0fa64ea5db15669024218`; its internal canonical artifact SHA-256 is `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`. The provenance records Potion multilingual 128M at immutable revision `e7421cd79c75fc506b88bb75723ae0a234994720`, MIT, model2vec `0.8.2` with source SHA-256 `929a7ee94295436f3befb3f0836cf45c587fd91f34fe3f3f8f4039a5e126c4d7`, and tokenizers `0.23.1` with the previously ratified vocabulary/config hashes. The worker reports a production-loader round trip, Ruff, basedpyright, and five focused contract checks passing.

The artifact is currently untracked shared-worktree WIP; no commit or push was performed. It therefore is not yet committed reviewable data and cannot close P02.S04. The full project bundle remains blocked by the unrelated `StopIteration` while resolving `CalculationSourceDiagnostic` in `src/cadrumo/application/aggregation/_modelo_bindings.py`; that peer-owned file was not touched. The matrix-only artifact must not enable the browser tier or be treated as a deployed search surface.

The formal review is recorded in `.vault/audit/2026-08-07-user-docs-search-consolidation-p02-s04-matrix-artifact-review-audit.md`. The feature-scoped VaultSpec check is clean with zero errors and zero warnings after the audit hygiene fix. P02.S04 remains open pending an authorized commit/handoff, authoritative full-bundle compilation, accepted remeasurement, and the downstream locale/deployment gates.

### 2026-08-07 authoritative full-bundle continuation

Fresh vaultspec-rag grounding was repeated through the supported code route (`vaultspec-rag search --type code`); the configured MCP `codebase` alias still rejects with `unknown_source_type`, so no alias bypass or reindex was used.

The earlier full-bundle assembly blocker is cleared in the current shared worktree. `build_rung2_compilation_inputs()` now assembled the authoritative closed vocabulary, token inventory, laundered sweep, and manifest with 114 queries, 114 vocabulary rows, 153 query-token rows, 8,505 manifest records, 2 ratified alias-authority entries, and 0 failed queries. The pinned-provider compiler then wrote a canonical temporary bundle at `%LOCALAPPDATA%\Temp\aeat-rung2-current-20260806\bundle-full-current.json`.

The repository loader round-trip passed for the exact bytes: schema v3, 2,138,574 serialized bytes, bundle artifact SHA-256 `1cb0bb6761bfb54a5a768d202fef0b9b85d3a38de99b34f92297cf2204d47f12`, file SHA-256 `0899c5cda51c32291d05d8274feda23c85ba814b54ad0de9d697760f44d04e99`, matrix artifact SHA-256 `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`, and query-token fingerprint `fce9c72d9da9cb5865aa76c752ff9778cd3af5f79728f91b4a267eaa6366e643`.

Browser-equivalent semantic replay against this fresh full bundle produced 32 cases, 22 hits, 10 misses, miss-rate `0.3125`, and aggregate token coverage `93/123 = 0.7560975609756098`; 20 queries were fully covered, 10 were below the `0.8` policy minimum, and none had zero coverage. The ten misses abstained for insufficient coverage; this does not justify lowering the policy or adding held-out terms.

P02.S04 remains open because the bundle is still temporary/unshipped and the acceptance ladder remains unproven. No browser enablement, generated-artifact promotion, deployment, commit, or push occurred.

Focused contract continuation: fresh supported `vaultspec-rag` grounding used code request `d46079ebc7784e8dbc24843bd6b2c3b` for the shared cosine seam and combined code/vault request `50ccf8560b6543f08b39b3a11b1e533d` for the Diseño boundary. The full bundle was loaded and its canonical matrix compared with `src/cadrumo/_data/terminology/evaluation/rung2-matrix.json`; exact equality and loader round-trip passed. The validated bundle is 2,138,574 bytes with 8,505 manifest records, 114 bridge terms, 153 query-token rows, bundle SHA-256 `0899c5cda51c32291d05d8274feda23c85ba814b54ad0de9d697760f44d04e99`, and matrix artifact SHA-256 `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`.

The focused real-behaviour contract suite returned `83 passed in 55.81s`. P02.S04 remains open because the matrix is uncommitted shared-worktree WIP and no release or browser enablement is authorized by this evidence.
