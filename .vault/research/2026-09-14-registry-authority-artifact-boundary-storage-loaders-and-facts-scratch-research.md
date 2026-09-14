---
tags:
  - '#research'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:03ca71905f10506d8ea6d163aafa0a074564193cb25c0d7949c4901e877c4fe1'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-remediation-result-reference]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference]]"
---

# Authority storage and loaders: scratch findings

## Findings

### Standing and measured problem

Conversation checkpoint requested on 2026-09-14 for continued audit. This is working research, not a new approved ADR or an implemented storage migration. The shipped backend remains compiled JSON. The operator agrees with on-demand access through layered cache-backed loaders. SQLite is the recommended next storage candidate; its performance in this application is unmeasured.

The linked remediation result remains the authoritative home for benchmark values and qualifications. Eager typed-object reconstruction is the principal measured concern; cached requests are already fast. Compilation resolves and validates authoring deltas. Hydration reconstructs Python objects once on first generation load per process, not on every request. Separate CLI processes pay separate initial costs. A faster monolithic codec alone does not remove whole-corpus allocation.

### Proposed route

Complete authoring sources feed one validated compiler, which publishes resolved components and indexes in a generation-specific SQLite authority. A typed provider loads only what an operation requires, without replaying authoring deltas.

Layers:

- Artifact admission verifies compatibility, integrity and generation identity without domain-object hydration.
- A small authority directory exposes model, revision and component metadata.
- The canonical resolver owns temporal/legal selection; indexed SQL narrows candidates without duplicating those rules.
- Component loaders independently retrieve immutable resolved revisions, fact families and substantial export layouts.
- Application projections assemble snapshots referencing shared components.
- Evidence loading retrieves detailed provenance on demand. Ordinary components retain evidence references; compilation validates full evidence closure.

Initial storage: manifest, indexed directories, resolved payloads, fact families, evidence and dependency edges. Start with canonical tagged JSON inside individual payload records, preserving exact decimals and domain semantics. Index selection keys in SQL columns. Use a resolved revision as the initial model-loading unit, with facts, evidence and large layouts independently addressable. Avoid a full-corpus blob and per-casilla query loops. Refine granularity or codec only with profiling. Direct-access binary formats remain alternatives if SQLite misses measured requirements.

### Cache and publication contract

Pin every operation to a generation. Cache immutable components by generation and identity, share them across projections, bound expensive caches by memory and coalesce concurrent loads of the same missing component. Make whole-corpus iteration explicit. Selective reads and the operating-system cache are the initial approach for separate CLI processes; a persistent service is not presently justified.

Build and validate a complete candidate offline, preserving conformance, evidence closure and source/compiler/component identities. Publish a generation-specific database without required WAL sidecars. Existing readers finish on their generation; new readers adopt the new one. Start with read-only connections; immutable mode requires a file that cannot change beneath an open reader.

Preserve admission verification. A full-file digest still scans bytes but need not hydrate objects. Partial verification would require a separate integrity design.

### Open finding: facts-schema enrollment

The operator reports that a facts schema exists on disk as a valid registry-adjacent structure but is not enrolled in canonical authority Python backend registration or compilation. This checkpoint records the reported gap; a fresh code trace must establish its exact extent.

Earlier proposals included governed fact families but did not establish that the on-disk facts schema itself is registered, compiled, versioned and enforced as an authority input. Existing fact records do not prove schema enrollment. Distinguish schema definitions from instances and other uses of the word facts.

This reopens compilation-source completeness. Finalizing storage before resolving that inventory risks carrying the omission into the new backend.

Next audit:

1. Locate facts schemas and records, Python schema/types, registrars and loaders; establish authoritative homes.
2. Trace discovery, Python registration, compiler validation, serialization, identity calculation, packaging and runtime retrieval. Identify omitted or bypassed enrollment edges.
3. Determine which schema semantics runtime needs for validation, introspection and decoding, and which remain compiler-only. Do not assume authored schemas must ship verbatim.
4. Verify schema-only changes affect appropriate generation identities and cache invalidation.
5. Trace consumers using disk reads, parallel registries or duplicated definitions outside canonical authority.
6. Check fact-to-model and fact-to-evidence references, unknown families, duplicate identifiers, incompatible types and applicability semantics.
7. Establish installed-package proof that facts and required schema semantics work from the artifact without authoring files.
8. Reconcile existing facts-registry architecture records; separate confirmed omissions, implemented behavior and uncertainty.

Facts schemas are an explicit candidate first-class compilation input. Ground their enrollment contract before finalizing storage.

### Remediation and acceptance

First complete the source/enrollment audit and resolve confirmed omissions. Then define the provider boundary and inventory eager modelos/catalogues/revisions consumers. Implement compiler-produced SQLite with semantic parity, add selective bounded loaders and generation pinning, and migrate consumers to explicit component access and enumeration.

Verify installed behavior, publication transitions and semantic equivalence. Benchmark fresh-process first use, incremental authority memory, cached queries and whole-corpus operations. Cut over only after acceptance, retaining an on-demand diagnostic JSON export rather than a second shipped runtime authority.

Acceptance must prove admission hydrates no model definitions, selected-context requests load only required components, eviction preserves correctness and generation transitions cannot mix results. Numerical targets require representative prototypes; projected improvements are not measured results.

## Follow-up disposition

This checkpoint is retained as the historical question set. The subsequent `2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference` owns the completed code trace, the `indexed-storage-readiness-audit` owns confirmed findings, and the `indexed-storage-adr` and implementation plan own the final route. Read those documents for the resolved enrollment scope and acceptance contract; the open audit questions above are not the current task status.

## Sources

The two related reference documents hold the previous architecture review and completed remediation evidence. The operator's 2026-09-14 conversation supplies the agreement on layered loaders and the newly reported facts-schema gap. Schema enrollment has not been independently re-audited in this checkpoint.

Primary storage references: [SQLite application-file benefits](https://sqlite.org/aff_short.html), [SQLite URI and immutable-file contract](https://www.sqlite.org/uri.html), [FlatBuffers Python](https://flatbuffers.dev/languages/python/).
