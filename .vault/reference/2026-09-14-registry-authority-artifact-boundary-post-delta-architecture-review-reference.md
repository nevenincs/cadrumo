---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:3a992681e09b0e0f173898b3f41ee1a450161c19f1bedd13dbbc32dc233f72e7'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---
# `registry-authority-artifact-boundary` reference: `Post-delta authority backend architecture review`

## Summary

Historical baseline captured before the implementation authorized later on 2026-09-14. Present-tense findings and measurements below describe that baseline. The implementation outcome is recorded in `2026-09-14-registry-authority-artifact-boundary-remediation-result-reference`; the final review is recorded in `2026-09-14-registry-authority-artifact-boundary-authority-backend-final-review-audit`.

**Retain the compiled authority boundary. Repair its validation, identity and query contracts before changing its storage format.** Delta authoring and runtime publication solve different problems: deltas express what changed in law; publication supplies an installed application with resolved, versioned, evidence-bearing data. Fewer TOML files do not remove that distinction. They do weaken any argument that a monolithic eager JSON document is justified merely by file count.

The current artifact is a useful release boundary but is not yet a dependable corpus backend. Publication skips full conformance, two publishers assign incompatible meanings to its identity, one shared nested dictionary is mutable, and a real Modelo 303 snapshot fails. Performance is also material: a fresh process loads every modelo and all embedded evidence, while ordinary cached snapshots still copy large graphs.

This is an architecture review and remediation proposal, not an approved implementation plan. No production code or registry publication was changed. The accepted authority-artifact and edition-authoring decisions remain the governing intent; the recommendations below identify implementation gaps and a potential storage evolution requiring an explicit decision.

## Scope and evidence

Reviewed on 2026-09-14 in the assigned main worktree at HEAD `f37584ad806e11a90164705359f295d67b7de460`, including current working-tree source. Scope: artifact codec and loader, authority queries and snapshots, publisher and compiler validation, identity/currency, evidence projection, packaging configuration, and focused runtime tests. Tooling retirement underway in the worktree was excluded from edits. Semantic discovery failed in this session; owning Vaultspec discovery and direct source inspection supplied the grounding.

Measurements use Python 3.13.11 on Windows through `uv run --no-sync python -`. They are local diagnostic samples, not controlled cross-platform benchmarks or OS-cold disk measurements. No full source rebuild, full corpus conformance run, wheel installation, or independent legal-content audit was performed. Legal observations concern whether the code enforces its declared evidence contract; they do not certify tax law.

### Current size and access cost

| Measurement | Observed value |
| --- | ---: |
| Modelo authoring TOML files | 1,938 |
| All registry TOML files | 2,210; 47,070,993 bytes |
| Published artifact | 63,398,819 bytes; format v4 |
| Modelos / revisions | 58 / 146 |
| Expanded modelo section | 41,651,312 bytes |
| Catalogues | 3,300,736 bytes |
| Legal evidence | 1,402 entries; 3,756,971 bytes |
| Embedded source evidence | 18 entries; 14,689,519 bytes |
| Whole-document gzip, diagnostic only | 5,128,127 bytes |
| JSON read and parse alone | 0.449 seconds |
| Authority module import | 1.322 seconds |
| First `bundled_authority()` after import | 4.682 seconds |
| Process RSS after first authority load | 443,392,000 bytes |
| Warm authority lookup, median of 50 | 0.176 ms |
| M100 2025/0A applicability snapshot: first / warm median | 157 / 127 ms |
| M200 2025/0A applicability snapshot: first / warm median | 330 / 278 ms |
| M130 2025/1T applicability snapshot: first / warm median | 39 / 29 ms |

Sizes are UTF-8 compact JSON section sizes; framing adds a small overhead. RSS is total process resident memory, not incremental artifact memory or measured peak. Warm snapshot medians use five calls after the first. These measurements establish a current baseline rather than validate the approximate earlier 1.5k authoring count.

A separate instrumented run attributes 6.23 of 7.45 profiled seconds to typed reconstruction, including 3.50 seconds of model validation and 2.63 seconds of recursive JSON conversion. Profiling adds overhead; these are attribution numbers, not comparable latency samples. Optimizing disk reads alone misses the main work.

## Architecture assessment

The intended flow is:

```text
Authored deltas + official evidence + governed facts
    -> development compiler: resolve inheritance and typed semantics
    -> complete validation of one captured candidate
    -> atomic publication of one versioned authority generation
    -> runtime admission and immutable indexed queries
    -> context-specific applicability / calculation / filing admission
```

The existing publication, integrity framing, tagged fact atoms, schema-default omission, package source exclusions and artifact-only loading are worth retaining. The artifact is an application publication containing legal provenance; it is not itself legislation or an authenticated official document. Its self-contained SHA-256 checks detect corruption, not a publisher's identity. The accepted decision explicitly rejects same-repository signing; no new signing mechanism is warranted by this review.

The important separation is between **one logical authority generation** and **one eagerly decoded JSON object**. The former is required. The latter is a storage choice that should earn its cost against application workloads.

## Findings and required corrections

### F1 — P1: publication claims validation that it does not perform

`dev/registry/pipeline/authority_publication.py:210–248` calls `compile_structural_authority`. That function explicitly compiles without registry-wide conformance (`dev/registry/compiler/authority.py:46–69`). Full `RegistryValidator.validate_registry` is on a different path at `authority.py:72–112`. The CLI delegates to the structural publication path.

This is significant for legal evidence as well as cross-model relationships: `dev/registry/compiler/legal_grounding.py:203–210` says its projection assumes completed full validation, but only retrieves text. Required/forbidden quotation and provenance checks are separate at lines 225–253. Readable evidence and a valid digest do not establish those checks passed.

**Correction:** only a fully validated candidate can enter publication. Keep structural compilation available under a type that cannot stand in for that candidate. Capture and validate the same input generation through final replacement. Preserve grade-specific unsupported states; complete validation does not mean declaring every modelo filing-capable.

**Acceptance:** independently break a cross-model reference and a required legal quotation in isolated candidates. Both must refuse before replacement, preserve the prior artifact, and report the owning declaration. These must exercise the actual publisher, not a sibling validator.

### F2 — P1: whole-corpus identity is overwritten by facts-only identity

Full publication derives `identity_digest` from registry and evidence inputs (`authority_publication.py:660–678`). Facts-only publication assigns the facts catalogue digest to that same field (`authority_publication.py:400–405`; `authority_artifact.py:307`). Facts currency also expects this interpretation (`authority_publication.py:360`). A normal full publication and a facts-only publication therefore cannot satisfy the same identity contract. On the inspected artifact, whole identity starts `94130cff` and facts digest starts `4c943617`.

The partial path retains model definitions, provider facts, runtime projections and evidence without component dependency receipts. Reconstructing their types does not prove that they remain consistent with changed fact semantics or current provider inputs.

**Correction:** distinguish portable source-manifest identity, compiler/schema build identity, component dependency identities and serialized payload digest. Until partial publication can prove retained components current, use full canonical publication. A facts-only path must not mint a whole-corpus validation claim from one section hash.

**Acceptance:** unchanged facts preserve whole-corpus semantics and coherent currency; changing a provider input invalidates affected retained output; changing a fact used by a binding forces that binding's semantic revalidation. Full and partial rebuilds from equivalent inputs produce equivalent resolved authority.

### F3 — P1: a mutable shared temporal map invalidates cache isolation

The existing whole-bundle immutability test fails at Modelo 202, revision `2025-y-siguientes`, binding `modelo-202-cuota-base-ejercicio-anterior`, `provider.temporal.offsets`. The field is a plain `Mapping` at `src/cadrumo/domain/calculations/registry/binding_temporal.py:194`; decoding yields a dictionary.

A fresh isolated process changed its `1P` value and observed the changed value through the next `bundled_authority()` call. No disk data was altered. This is a reproduced shared-state defect, not an inferred risk. It also contradicts `FrozenMapping.__deepcopy__`'s premise that every reachable value is immutable.

The authority wrapper itself is a mutable dataclass with publicly assignable `modelos`, `catalogues` and `evidence` (`authority.py:151–161`), so the read-only contract also needs to cover the holder, not just nested models.

**Correction:** freeze every reachable semantic mapping and expose read-only authority state, keeping mutable caches private. Retain the graph walker and add consumer-level mutation refusal at the actual temporal field. Do not remove its current failure as a false signal.

**Acceptance:** the live graph walk passes; temporal-map mutation and public semantic-state rebinding cannot change a later caller's result; snapshot isolation still holds.

### F4 — P1: normal Modelo 303 access fails at two runtime boundaries

A fresh `bundled_authority().snapshot("303", filing_year=2025, period="1T", grade=RegistryAuthorityGrade.APPLICABILITY)` raises `RegistryValidationError`: ledger-IVA rate-kind and cash-accounting validators require candidate facts in scope. Artifact decode scopes them, but runtime snapshot construction reparses selectors without that scope (`authority_artifact.py:531`; `authority.py:479`; `snapshot.py:283`; `binding_selector_utils.py:674`).

A diagnostic invocation with the authority's facts explicitly scoped advances past that refusal, then fails at `authority.py:372`, the snapshot deep copy: `TypeError: IvaFlowDirection tokens must be projected from the facts registry`. The token constructor at `src/cadrumo/domain/iva/flow.py:111–115` refuses reconstruction by the generic copy machinery. Thus adding a context manager alone is not a complete fix.

**Correction:** let runtime queries operate on already typed providers; pass the active authority explicitly where contextual validation remains necessary. Make immutable domain tokens copy-safe, and replace snapshot-wide copying only after F3's immutability guarantee is established. Move invariant binding/layout compilation to publication while retaining request-dependent temporal and grade admission.

**Acceptance:** fresh-process M303 snapshot, calculation and export admission use the installed artifact without authoring context. Cover applicability and the revision's supported higher grades, warm calls, copy/capture paths and alternate authority instances. Do not solve this by weakening membership validation.

### F5 — P2: eager corpus reconstruction and snapshot copies dominate access

`authority_artifact.py:514–573` reconstructs every modelo, catalogue and embedded evidence item before answering any query. `_immutable_json_value` traverses the graph first. A small facts lookup therefore pays the same first-load cost as a complete modelo inventory. Shared caching improves later calls within one process, not repeated short CLI processes.

`authority.py:372` and the capture API deep-copy snapshots. Snapshot maps remain mutable (`schema.py:1290–1314`), and the snapshot carries a complete modelo definition. Layout derivation and reference checking also occur during context-specific snapshot construction (`snapshot.py:232–283`). The warm timings above show that caching the wrapper has not made normal reads cheap.

**Correction:** first make snapshots deeply immutable and share typed definitions. Cache compiled revision-level indexes/layouts separately from filing-context admission; normalize request keys before caching and bound context-cache retention. Index evidence by ID instead of repeated tuple scans. Then measure whether eager JSON loading still violates startup/memory targets.

**Acceptance:** queries for the same admitted context do not copy the full model graph or repeat invariant derivation. Prove unchanged refusal behavior and isolated semantics. Record fresh-process latency, peak memory, first snapshot and warm query p50/p95 for small facts, M303, M100, M200 and whole-corpus enumeration.

### F6 — P2: artifact admission does not prove evidence closure

`AuthorityArtifact.__post_init__` checks component types and digest syntax; decode reconstructs evidence independently, then requires runtime catalogue completeness (`authority_artifact.py:232–245,547–573`). It does not establish that every required legal/source projection matches the catalogue membership and source metadata. A correctly rehashed incomplete frame can defer failure until a consumer asks for missing evidence. This is a verified validation gap; the review did not find missing evidence in the shipped artifact.

**Correction:** enforce unique modelo identities, legal-evidence coverage and typed required-source evidence closure, including catalogue hash/length agreement, before replacement and on artifact admission. Required source evidence means what runtime consumers actually need, not embedding every corpus source. Validate the candidate encoding before full publication, as the facts writer already attempts before cutover.

**Acceptance:** removing required evidence, substituting mismatched source bytes, duplicating a modelo, or introducing unknown references into a correctly hashed artifact fails at admission. Preserve decimals, dates, absence/default distinctions and provenance in semantic round trips.

### F7 — P2: freshness lacks compiler identity and uses a broad, cached inventory

`_capture_receipt` scans and hashes broad registry/evidence roots, but its portable identity does not include compiler semantics. Compiler changes can leave currency reporting current despite changed output. Conversely, unrelated corpus additions invalidate the broad input digest. A delta compiler needs explicit transitive dependencies if it is to rebuild selectively.

Evidence inventory under bundled data is cached for ten seconds (`dev/registry/compiler/source_evidence_fingerprint.py:69–76`; `loader_cache.py:67`). Development publication operates in that writable tree. Known files are rehashed, but newly added paths can escape a receipt until inventory expiry. This concurrency scenario is inferred from source and was not reproduced.

**Correction:** record compiler/schema identity and the actual transitive input manifest. Use uncached inventory for publication receipts, or compile from an immutable staged input set. Keep an independent clean rebuild comparison; source-hash currency is not a replacement for it.

**Acceptance:** compiler changes invalidate the build receipt; relevant additions during publication cannot escape detection; unrelated evidence outside the dependency closure does not force an incremental rebuild. Retained output must compare equal to a clean full build.

## Remediation passes

| Pass | Required work and owner boundary | Exit evidence |
| --- | --- | --- |
| A — Restore trustworthy publication | F1, F2, F6; development publisher/compiler and artifact contract. Separate structural from publishable candidates; suspend unsound partial identity semantics. | Broken candidates cannot replace a good artifact; one coherent identity; fresh full publication and decode have identical typed meaning. |
| B — Restore reliable runtime reads | F3, F4; runtime schema, authority, IVA tokens and binding consumers. Freeze semantic state, fix candidate-scope leakage and copying. Repair incomplete runtime test fixtures. | Real M202 mutation refusal; fresh-process M303 success at supported grades; all focused artifact tests pass; installed artifact-only workflow smoke tests. |
| C — Make the current backend inexpensive | F5; immutable snapshots, compiled revision indexes, selective evidence queries, bounded caches. Add workload measurements. | No full-graph copying on warm reads; recorded startup and memory budgets; preserved temporal/grade refusals. |
| D — Make builds reproducible and selective | F7 and the durable incremental form of F2; compiler dependency manifests and uncached/staged publication inputs. | Clean/partial equivalence, compiler-change invalidation, concurrent-input refusal and stable no-op publication. |
| E — Decide the physical backend from measured workloads | Prototype indexed section loading only if Pass C leaves fresh-process cost unacceptable. | Same semantic corpus and refusal tests across candidates; measured startup, memory, package size, full-scan and publication costs. Record the chosen format in an ADR before migration. |

Passes A and B are prerequisites for calling this a dependable backend. Performance work must not hide failing semantic gates or turn unsupported capability into filing grade. The existing `dev/registry/tests/test_authority_artifact_round_trip.py:37,67–79` has a 64 MiB size budget and clean-publication equality check; retain their distinct purposes and add workload budgets rather than treating file size as latency evidence.

### Recommended backend direction

Start with the existing JSON format and correct query semantics. If eager startup remains outside the agreed product budget, prefer one immutable indexed publication containing resolved revision data, shared catalogues and separately addressable evidence blobs. A manifest-indexed container or a read-only SQLite artifact are candidates, not decisions made by this review. Both must remain hidden behind the canonical typed authority boundary; application consumers must not acquire their own SQL/JSON interpretation paths.

Use one generation manifest binding all sections, compiler/schema identity and hashes. Publish the complete generation atomically. Required-component membership is validated globally; lazy readers verify section integrity before exposing it. Runtime never evaluates authoring deltas, opens raw TOML as a fallback, or quietly mixes generations.

Do not assume simple whole-row deduplication will recover the source collapse. Across revision array members, exact canonical duplicates accounted for only 615,811 of 40,869,604 bytes. The largest sections are casillas (21.19 MB), export layouts (10.03 MB) and bindings (4.55 MB). Effective revision identities and provenance make otherwise similar rows differ. Structural sharing would need typed immutable declaration identities plus explicit revision membership/provenance, and parity tests proving that source lineage was preserved. Generic deduplication by labels or printed casilla number would be unsafe.

Likewise, gzip shrinks transfer/storage substantially but does not avoid whole-corpus reconstruction. Separate evidence blobs and selective typed loading address a different cost. Keep an inspectable canonical projection for review even if the installed physical format changes.

## Validation and reproducibility

Executed:

```powershell
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py -q --tb=short
```

**Exit 1: 24 passed, 7 failed, 32.76 seconds reported by pytest.** Six failures occur while staging minimal artifacts because their runtime catalogues are incomplete. They prevent their intended cache/corruption/citation assertions from running; they are fixture failures, not six separately established production failures. The remaining failure is the live temporal-offset immutability defect reproduced above. The committed artifact canonical read/write test passed.

All seven failing tests are in `test_bundled_authority_artifact_runtime.py`:

- `test_runtime_uses_one_authority_cache_per_published_artifact_identity`
- `test_a_republished_artifact_is_decoded_afresh_rather_than_served_stale`
- `test_a_corrupt_artifact_is_refused_on_every_call_even_after_a_good_read`
- `test_the_bundled_authority_graph_is_deeply_immutable`
- `test_runtime_answers_a_citation_from_published_evidence_without_a_corpus_root`
- `test_runtime_reads_published_provenance_without_a_corpus_tree`
- `test_corrupt_publication_refuses_before_any_authoring_fallback`

Additional read-only Python probes exited 0 and deliberately caught/reported the M303 refusals. The mutation proof changed only isolated process memory. No benchmark republished the bundle. The core reproduction is:

```python
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_authority

authority = bundled_authority()
authority.snapshot("303", filing_year=2025, period="1T",
                   grade=RegistryAuthorityGrade.APPLICABILITY)
```

For timing, measure imports separately, time the first `bundled_authority()` in a fresh process, then median 50 warm lookups and five warm snapshots per coordinate. Parse section sizes from `authority.json` using compact UTF-8 JSON. Use `cProfile` only for attribution, separately from wall-time runs. Recheck these measurements after the in-flight work settles; do not freeze corpus counts as correctness assertions.

The focused Vaultspec check reported no findings against this report. Feature-wide validation remains blocked by 15 existing per-Step execution-record errors, two empty sections in an earlier audit, and one stale execution-record stamp. The feature index was regenerated to include this review; unrelated records were left unchanged.
