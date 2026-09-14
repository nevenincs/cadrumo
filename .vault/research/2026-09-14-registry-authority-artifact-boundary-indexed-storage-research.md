---
tags:
  - '#research'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:1a3aef9b07f5572dd6d8c7e528e545e90e28cd35d90a9ffba0b72eb90726d4f8'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-readiness-audit]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-storage-loaders-and-facts-scratch-research]]"
---

# Indexed authority storage and on-demand loading

The evidence favors an indexed SQLite publication with selective typed loading, provided the profile-facts schema first joins the captured compiler inputs. The decision is about source completeness and runtime access, not merely replacing JSON encoding. The related source-enrollment reference owns the code inventory, probes and test results; the readiness audit owns defects and their severity.

## Findings

### Three different meanings of facts must remain separate

Governed tax facts are already compiled. The profile schema declares which taxpayer facts can exist and how they are interpreted, but remains a separate input. Actual taxpayer values belong to encrypted persistence. Evidence: `2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference`. A complete public authority can contain both governed facts and profile-schema declarations as distinct typed components without storing private records or flattening their semantics into a universal fact payload.

### Indexed access addresses allocation while a monolithic codec does not

SQLite supplies selective indexed reads in one portable database; it need not parse the complete payload graph: https://www.sqlite.org/aff_short.html. Retaining canonical tagged JSON per component preserves the existing exact typed encoding while changing the amount loaded. A monolithic MessagePack/CBOR replacement may reduce decoding overhead but preserves wholesale allocation. FlatBuffers exposes direct Python accessors but requires a different domain access model and custom indexing decisions: https://flatbuffers.dev/languages/python/. No SQLite or FlatBuffers performance prototype was run in this planning-only workflow.

The installed local interpreter reports Python 3.13.11, SQLite 3.50.4 and DB-API threadsafety 3. These describe the audit workstation, not every supported deployment. The standard Python adapter supports URI read-only connections and has explicit thread ownership and close behavior: https://docs.python.org/3.13/library/sqlite3.html. The implementation must probe and test the SQLite features it actually requires, not assume this workstation's library version everywhere.

### Component boundaries must follow access needs and type ownership

A small directory can carry model and revision selection metadata; the canonical temporal resolver can then choose the revision before its payload is decoded. Facts can be keyed by fact ID with their variants, runtime catalogues by family, profile schema by its versioned component, and evidence by identity. The initial profile schema can remain one lazily decoded component; there is no evidence yet requiring per-field SQL. Export layouts should be separate where needed to keep non-export requests light. These are candidate boundaries for the ADR, not measured optimal sizes.

`ProfileSchemaDefinition` can remain canonically defined in its existing domain module. The current registry package already owns the publication reader and bundled composition seam; retaining the physical SQLite reader at that boundary avoids introducing a domain-to-adapter import or a new global registration facade. Consumer access should be typed; storage rows and SQL stay private. A separate adapter/composition migration offers stronger general layering but creates broad dependency injection work without demonstrated benefit for this domain publication format. Evidence: the related code reference and `src/cadrumo/domain/calculations/registry/authority.py:583`.

### Facts bootstrap makes dependency ordering a correctness requirement

Selected model decoders consult governed vocabulary and tax-ID definitions. Their loader must use dependencies from the same generation under an explicit validation scope. A conservative compiler-declared dependency set is safer initially than inferred minimal sets; access outside the declared set should fail and expose missing enrollment. No dependency graph establishes partial-publication safety by itself. Evidence: the readiness audit's fact-bootstrap and provider-enrollment findings.

### Lazy semantic validation changes one existing runtime promise

Complete publication validation can remain unchanged in strength: a clean reader must traverse every encoded component before cutover. Runtime can verify the complete database byte digest and global manifest/relationship inventory without reconstructing typed payloads. It then validates each requested component before use. An unused malformed component with all unsigned digests deliberately recomputed is not necessarily rejected at open; that is a deliberate timing change that the ADR must state. A digest is not a publisher signature. Evidence: `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py:264` and the readiness audit.

SQLite integrity checks detect structural faults but do not substitute for domain schema or legal conformance; foreign-key checking is a separate operation: https://www.sqlite.org/pragma.html#pragma_integrity_check. Full-file hashing remains an O(file size) admission cost and must remain inside performance measurements.

### Publication needs immutable generation paths and a small control descriptor

A single data database plus a small descriptor is one logical authority, not two competing registries. The descriptor identifies an exact content-addressed generation; switching it avoids replacing an open database on Windows. Missing or malformed descriptors must refuse, never scan for the newest file. SQLite immutable mode disables locking/change detection and is unsafe if the referenced file can change: https://www.sqlite.org/uri.html. Ordinary read-only mode is the initial choice. Finish and close the database before distribution so it requires no WAL sidecars: https://www.sqlite.org/wal.html.

The descriptor must keep physical file digest separate from logical source/build/component identities. Published file names can use the physical digest without recursively embedding that digest inside its own database. Package resources and connections require a coordinated lifetime; normal filesystem wheel installs are sufficient for the first release. The source reference records why zip-import needs an additional real test before support is claimed.

### Exact values and indexes should be explicit

Persist decimal values using the canonical tagged encoding or exact text, not binary floating point: https://www.sqlite.org/floatingpoint.html. Selection keys belong in indexed scalar columns. SQLite JSONB does not provide general constant-time nested lookup, so it is not a substitute for those indexes: https://www.sqlite.org/json1.html. Whole-file compression prevents ordinary SQLite page access; independent payload compression, memory mapping and a new binary codec remain optional experiments after measuring the basic design.

### Comparative acceptance is more useful than an invented universal startup promise

The previous measurements are specific fresh-process medians, not OS-cold results or product SLOs. The ADR can set engineering cutover targets relative to a fresh paired JSON baseline from the same captured source generation. Measure admission plus first selected operation, imports separately, incremental authority memory and cached public queries. Include profile-only and fact-only operations so a model-only benchmark cannot hide an eager catalogue dependency. No measured SQLite speedup is claimed.

### SQLite compatibility and resource tuning have explicit trade-offs

SQLite STRICT tables require version 3.37.0 or newer and check scalar column types without replacing typed payload validation: https://www.sqlite.org/stricttables.html. A minimum version at this level permits explicit metadata types while avoiding newer JSONB dependencies. Multi-thread SQLite permits distinct connections concurrently but forbids concurrent use of one connection; a bounded exclusive-checkout pool can satisfy this: https://www.sqlite.org/threadsafe.html. Cache byte ceilings and connection counts are engineering tuning choices rather than source-derived optimal values; they must be measured with admission and schema-dependent workloads.

### Existing decisions require a storage pivot and a narrow facts amendment

The authority ADR retains v5 pending a separate measured storage decision; it should be superseded for the new physical/access contract while retaining full publication, refusal, immutable semantics and separate identities. The facts ADR's flat-file description conflicts with the live nested layout; amend it to registered-subtree ownership with path-independent semantic identity. Profile derived-path and requirement policies remain binding: moving their schema into the authority must not reinterpret requiredness, legal applicability, secure snapshots or operator inputs. Evidence: the related source reference and existing ADRs retrieved during audit.

## Sources

Internal grounding: `2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference`, `2026-09-14-registry-authority-artifact-boundary-indexed-storage-readiness-audit`, and the historical remediation result referenced by them. All live test outcomes are recorded in the source reference.

Primary technical documentation retrieved 2026-09-14: https://www.sqlite.org/aff_short.html ; https://www.sqlite.org/uri.html ; https://www.sqlite.org/wal.html ; https://www.sqlite.org/pragma.html#pragma_integrity_check ; https://www.sqlite.org/floatingpoint.html ; https://www.sqlite.org/json1.html ; https://docs.python.org/3.13/library/sqlite3.html ; https://flatbuffers.dev/languages/python/ . Additional primary references: https://www.sqlite.org/stricttables.html ; https://www.sqlite.org/threadsafe.html . No third-party benchmark was used as a prediction of Cadrumo performance.
