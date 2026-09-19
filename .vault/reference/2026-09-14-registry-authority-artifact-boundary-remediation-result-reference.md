---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:db67ce0011b196bade9b1def1ef2a9a5d49801aa762230f991594be3c9eb4013'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-authority-backend-final-review-audit]]"
---
# Authority backend implementation and performance review

Implementation assessment as of 2026-09-14, following the post-delta architecture review. The earlier review is the historical baseline; this document records the resulting backend and its measured limits. The accepted ADR owns the architectural decision, the plan owns completion status, and the final audit owns review findings.

## Summary

Retain `authority.json` as the compiled, validated runtime boundary. Collapsing authoring TOML into a delta registry reduces authoring duplication; it does not remove the need to resolve revisions, validate legal grounding, establish evidence closure, and publish one coherent generation. Applications should consume typed, immutable authority APIs, without reconstructing deltas or discovering authoring files. The measured authoring tree contains 2,210 registry TOML files, including 1,938 modelo files; v5 is 63,388,923 bytes. The delta collapse therefore changes authoring cost without eliminating the expanded runtime graph.

The implemented v5 backend now compiles the full corpus successfully, refuses incomplete or changing candidates, preserves typed values, and shares immutable runtime results. Its principal performance benefit is repeated application queries. Fresh-process hydration still costs approximately three seconds and the process retains roughly 436 MB; a single JSON file alone does not make startup cheap.

## Architecture and remediation passes

| Pass | Finding and implemented remedy | Reviewable entry points |
| --- | --- | --- |
| Publication integrity | Structural loading could produce a trusted-looking authority, and partial publication could retain unrelated components. Only complete validation now creates the publishable authority. Diagnostics receive structural components. Facts-only publication was removed. | `dev/registry/compiler/authority.py`, `dev/registry/diagnostic_classification.py`, `dev/registry/pipeline/authority_publication.py` |
| Generation identity | Payload identity alone did not explain source or compiler drift. V5 persists separate source, compiler/schema and complete-component dependency identities, derives generation identity from them, and verifies the payload digest separately. Compiler identity includes conservative transitive code roots, dependency manifests and relevant interpreter/library versions. | `dev/registry/compiler/build_identity.py`, `authority_artifact.py` |
| Coherent cutover | A candidate could change after validation. Publication captures inputs, performs full conformance, serializes and decodes the candidate, stages and fsyncs bytes, checks fresh receipts, then replaces the artifact. Failed validation or detected drift preserves the previous artifact. | `dev/registry/pipeline/authority_publication.py`, `authority_artifact.py` |
| Evidence closure | Incomplete or inconsistent evidence could enter the shipped artifact. Admission checks exact legal membership, required source coverage, source metadata consistency, duplicate identifiers and unknown wire members. Evidence is indexed for runtime lookup. | `authority_artifact.py`, `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` |
| Reliable runtime | Mutable temporal mappings and deep-copy reconstruction undermined sharing and Modelo 303. Semantic mappings are frozen, immutable IVA values support copying, and snapshots share typed definitions. Provider access avoids repeated schema reconstruction. Modelo 303 compensation is no longer mistaken for a refund merely because the result is negative. | `authority.py`, `binding_temporal.py`, `schema.py`, `src/cadrumo/domain/iva/flow.py`, `src/cadrumo/application/calculations/m303_carry_ingress.py` |
| Cache correctness and cost | Date-only projections could cross authority generations; metadata-only file caches could retain stale content. Bounded caches now include authority ownership. TOML and quotation identities include content, with manual sidecars in publication receipts. Snapshot results are shared per admitted context. | `governed_fact_scope.py`, `dev/registry/compiler/loader_cache.py`, `dev/registry/compiler/validate_evidence.py` |
| Corpus blockers | Full validation exposed existing continuity, historical procedural evidence and enum drift. Repairs preserve negative validation: transitive field-specific continuity, explicitly bounded procedural grounding, and nonbranching historical enum evolution. A stale Modelo 200 generated manifest pin was refreshed to the existing generated manifest. | `dev/registry/compiler/validate_cross_revision.py`, `dev/registry/compiler/validate_semantic_roles.py`, `dev/registry/tests/test_procedural_evidence.py`, `dev/registry/conformance_vectors/modelo_200_2025_y_siguientes.toml` |

Short module names in this table refer to `src/cadrumo/domain/calculations/registry/` unless their full path is given. Publication is a validated release boundary; a digest provides integrity and generation identity, not an external digital signature or an independent legal opinion.

## Measured performance

Run `uv run --no-sync python -m dev.registry.benchmark_authority --runs 3` to reproduce the measurement procedure. These are medians from three fresh Python processes on the current Windows workstation using Python 3.13.11, with 100 repeated reads per representative snapshot. Fresh process does not mean a cold operating-system file cache. Each row is its own median; component medians need not sum to the total. Measurements are descriptive, not cross-platform guarantees or percentile SLOs. The final benchmark used tracked generation `28abbb04db05ae702a5b69f9f93c98a3f19821c1f0b2f927f630fba70bc0f616`.

| Workload | Result |
| --- | ---: |
| Authority imports | 0.933 s |
| Hydration after import | 3.045 s |
| Imports plus hydration | 3.952 s |
| First M100 2025 applicability snapshot | 63.14 ms |
| First M200 2025 applicability snapshot | 61.63 ms |
| First M303 2025/4T filing snapshot | 58.59 ms |
| Repeated snapshot on a held authority, same admitted context | 0.9–1.0 microseconds |
| Repeated M303 query through bundled_authority(), including file admission | 0.338 ms |
| Enumerate revision objects and count casillas across the corpus | 0.223 ms |
| Process RSS after queries | 435,826,688 bytes |
| Peak working set | 512,036,864 bytes |

The original review measured hydration after import at 4.682 seconds; the current median is about 35% lower. Original warm M100 and M200 snapshots cost 127 and 278 ms respectively, while M303 failed. Current warm reads return the same immutable snapshot object. Enumeration visits 146 revisions across 58 modelos in this generation; it does not construct every possible filing-context snapshot. Corpus counts are observations, not test oracles.

## Verification

The measured complete compilation published v5 in 91.9 seconds and its currency check passed. The initial round-trip generation was `8fa2ad5c2d7df1986b96c3917e3e3ba2b8ced15c4c1765e7e98377fe9085a8a9`.

- Final tracked publication: `28abbb04db05ae702a5b69f9f93c98a3f19821c1f0b2f927f630fba70bc0f616`. The full `python -m dev.registry.conformance integrity` command passed against this generation and live inputs after final lint and documentation corrections.
- Full canonical artifact round-trip suite: 10 passed, including a full corpus compilation and typed semantic comparison.
- Final focused authority review suite: 64 passed; no unresolved high or critical review findings.
- Exact diagnostic-classification integration regression: passed after the generated provenance pin repair; the negative provenance drift detector also passed.
- Focused publication, currency, quotation-cache, TOML-content and generation-cache checks exercised refusals and preservation of the previous artifact.
- Carry-forward regression suite: 38 passed after replacing stale constant-provider and unsupported-period fixtures.
- Non-empty Modelo 303 official worked-example suite: 4 passed after migrating removed enum tokens to dated registry projections. The published input amounts, expected tax figures and negative recargo coverage remain unchanged.
- Historical legal-catalogue grounding regression: passed for five pre-1993 references and refused a corrupted required quotation. The integrity CLI now applies corpus grounding at catalogue scope; filing eligibility remains a selected-runtime-context obligation.
- Introduced lint and type regressions were corrected. Broader changed-file checks still report pre-existing docstring, protected-member and incomplete-type diagnostics; a repository-wide clean lint/type result is not claimed.
- Installed CLI/MCP suite: 9 passed and one launch-fixture failure in 2,014.66 seconds. The isolated launch fixture omitted the required installed CLI executable path. After correcting that test environment, every assertion from the failed case passed against the same freshly built cohort, including the real server handshake, executable path, clean exit and ordered timestamps. This is a passing focused replay after the initial suite failure, not a claim that the full suite was rerun. The finite module timeout is now 900 seconds; its legitimate build/setup took 592.67 seconds.
- The installed cohort captured generation `8fa2ad5c2d7df1986b96c3917e3e3ba2b8ced15c4c1765e7e98377fe9085a8a9` before the final formatting, import-order and documentation corrections. Final publication integrity and the final benchmark use generation `28abbb04db05ae702a5b69f9f93c98a3f19821c1f0b2f927f630fba70bc0f616`.

The standalone installed-wheel probe passed under Python isolated mode. It covers Modelo 303 filing snapshot selection, deep copy, repeated-object sharing and actual empty-ledger IVA aggregation. It also round-trips Decimal amounts through 57 published Modelo 303 2026 export money fields and refuses a malformed amount. This proves the authority-to-export-codec boundary; it does not claim a complete approved Modelo 303 filing export. Publication and installed-runtime tests are distinct obligations: successful source compilation alone is insufficient release proof.

## Remaining performance decision

Keep full canonical publication and the current physical format. Selective retained-component publication is disabled; no selective-equivalence claim is made. Eager construction of every layout or context has not been added: the measured first-context work is about 59–63 ms and repeated contexts are cached. This avoids paying speculative startup and memory costs for contexts the application never requests.

A storage change remains conditional on a concrete application startup or memory requirement. No product budget was supplied, so these measurements do not prove that three-second hydration or 436 MB RSS is acceptable for every deployment. If a target requires substantially less, the next pass should profile JSON decoding versus typed graph hydration, then compare indexed or partitioned physical storage on the same workloads. Preserve one generation identity, immutable typed APIs, evidence closure, atomic replacement and artifact-only installed behavior in that comparison. Require semantic equivalence and installed corruption/refusal tests before switching.

Operational publication and recovery instructions are in `docs/how-to/publish-runtime-authority.md`; the application-facing contract is in `docs/reference/registry-legal-api.md`.
