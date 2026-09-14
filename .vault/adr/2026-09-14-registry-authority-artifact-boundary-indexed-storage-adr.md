---
tags:
  - "#adr"
  - "#registry-authority-artifact-boundary"
date: '2026-09-14'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-research]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-readiness-audit]]"
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
  - "[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]"
  - "[[2026-08-04-profile-derived-selectors-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
supersedes:
  - '2026-09-10-registry-authority-artifact-boundary-adr'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:7c99fb4a88b187aabd9ec74ae1d4b179d9d5e317e91ae2d2cbba10772155d834'
---

# `registry-authority-artifact-boundary` adr: indexed authority and complete source enrollment | (**status:** `accepted`)

## Problem Statement

Make the compiled authority a complete, selectively loaded backend for model definitions, governed facts, profile-schema declarations and evidence. The related indexed-storage research and source-enrollment reference establish the source gap and eager-access constraints. This decision replaces the previous physical-format retention decision while preserving one validated authority generation and all applicable legal/domain semantics. The operator delegated the workflow through the implementation-plan boundary on 2026-09-14; implementation is not authorised by completion of this document workflow.

## Considerations

- Source completeness includes the profile-facts schema; governed facts and taxpayer values are different concepts. Grounding: the indexed-storage source-enrollment reference.
- Selective loading requires typed API changes, explicit dependencies and generation ownership. Grounding: the indexed-storage research.
- The current authority package already owns publication-format I/O and composition. A storage adapter migration would add unrelated dependency-injection work. Grounding: the source-enrollment reference.
- Lazy hydration changes the timing of semantic refusal for an unused payload whose unsigned digests were deliberately recomputed. Grounding: the readiness audit.
- Existing profile requiredness, derived-path ownership and secure-record policies remain binding. Related profile ADRs retain those decisions.

## Considered options

- Retain optimised monolithic JSON: operationally established, but retains full typed reconstruction. Rejected as the target backend.
- Replace only the codec with a monolithic binary format: may reduce decoding cost but preserves the access-model problem. Rejected.
- Use indexed SQLite with independently decoded typed components: selected for selective access, inspectability and the existing standard-library dependency surface.
- Use a custom directly addressable binary format: retained as a future alternative only if the measured SQLite implementation fails cutover targets; not implemented in parallel.
- Keep profile-schema TOML as a separate runtime input: rejected because candidate validation, runtime and generation identity can disagree.
- Flatten profile declarations and taxpayer values into governed facts: rejected because they have different semantics, ownership and persistence requirements.
- Add raw-source or previous-format fallback: rejected. Missing or invalid published authority fails closed.

## Constraints

Only complete canonical generations may be published. No retained-component or facts-only publication is introduced. All authoring inputs are explicit and captured together; candidate compilation never consults the currently published authority or an ambient profile schema. Source, compiler/schema, component dependency, logical generation and physical payload identities remain distinct. Identifier constructors remain syntax-only, with membership and scope authority-backed.

The authority contains public declarations and their public source evidence only. Taxpayer records, private evidence and credentials remain behind encrypted persistence. Profile schema ID/version and existing record-version refusal remain explicit; this storage change neither upgrades records silently nor changes requiredness, derived-field ownership, legal rules, export layouts or authority-grade policy.

Runtime selection continues through the canonical temporal and governed-fact resolvers. SQL may narrow candidates and retrieve records; it must not duplicate applicability, precedence, grade admission or fallback rules. Filing requires the actual draft/request coordinate or a valid pinned capture. Latest revision inspection is explicitly non-filing.

The package must ship one referenced database and a small control descriptor, with no JSON runtime twin, authoring TOML, compiler cache or required WAL/SHM sidecar. Normal filesystem wheel and sdist-rebuilt-wheel installs are supported initially. Zip-import support is not claimed by this decision.

## Implementation

### Complete source enrollment

Introduce an explicit typed compiler source set containing the AEAT registry root, profile schema path and source-evidence root. The development entrypoint may resolve bundled defaults once; custom candidates supply their profile schema explicitly. One enrollment mechanism owns input census, parsing, validation, fingerprints, compiler/cache receipts and component dependencies. Capture the profile schema bytes and parse that capture once, then inject its typed value into model contract validation. Remove the validator's ambient fallback.

Keep `ProfileSchemaDefinition` in its canonical user-profile domain module. Compile its complete public declaration as a separate immutable component, including version, fields, sections, sensitivity classifications, selectors and derived-path metadata. Validate the entire TOML envelope and declared legal/reference relationships without assigning new legal meaning. Preserve existing governed-fact families and implement the related facts ADR's recursive subtree and exhaustive-enrollment contract.

### Storage and typed access

Keep publication-format implementation in the established registry authority package. `authority_store.py` defines the typed read contract and SQLite generation reader; SQL and row representations remain private there. `authority_artifact.py` owns versioned manifest/identity and canonical component encoding, with its JSON runtime frame retired at cutover. `ValidatedRegistryAuthority` owns semantic query coordination over the store. This is a domain publication format, not a new taxpayer persistence backend or application registration facade.

Persist a manifest, model/revision directory, typed component descriptors, dependency edges, governed facts, profile schema, runtime catalogue families and evidence. Index point identities and revision selection metadata. Begin with one resolved revision payload, one fact with its resolved variants, one runtime catalogue family and one complete profile schema per component; keep substantial export layouts and evidence separately addressable. Revision metadata contains every field the canonical selector needs. Extract shared selection logic so metadata selection and full compiler validation use the same rules; never synthesize partially populated `ModeloRevision` objects.

Use the existing canonical tagged encoding for individual structured payloads and raw bytes for binary evidence. Preserve exact decimals, dates, enums, absence, ordering and provenance. Component hashes describe canonical logical payloads; SQLite file bytes have a separate digest. Encoding defaults are valid only under the declared codec/schema version. Do not ship arbitrary Python objects, executable payloads, generic untyped fact dictionaries or whole-file compression.

Expose typed metadata lookup, revision-by-context/identity, fact resolution, profile-schema retrieval, runtime catalogue access and evidence lookup. Remove public eager whole-corpus fields and update their consumers in one coordinated cutover. Provide explicit deterministic iterators for bulk diagnostics. Retire the raw runtime profile loader and its duplicate cache; its TOML parser moves to development. Profile record constructors and secure deserializers receive the pinned schema explicitly rather than loading authority inside model validators.

### Layers, dependencies and caching

Admission loads the descriptor and small manifest/directory. Context selection chooses component IDs. Component loaders retrieve the selected revision and dependencies; projections reuse those immutable components; evidence loads only on request. Compilation declares conservative complete validation dependencies, including fact-backed vocabulary and tax-ID bootstrap. Dependency reads remain within one generation scope. Unknown dependencies, cycles or undeclared recursive loads fail explicitly; a trace of one query is not proof of complete dependency enrollment.

Cache keys include logical generation, reader incarnation and full typed query coordinates as appropriate. Same-key concurrent misses share one load; different component loads do not hold a global decode lock. Cache only successful immutable results. Release waiters on failures and refuse cycles promptly. A shared retained-weight budget covers component and projection caches, with accounting that avoids double-charging shared objects; report estimates separately from measured process memory. Oversized components may be returned without retention. Eviction does not invalidate caller-held immutable values. Directory size, active leases and external references are measured separately, so cache budgets are not advertised as a total RSS cap.

Preserve process-incarnation capture semantics in addition to generation identity. A top-level operation pins one reader before profile/fact/model work. Descriptor changes affect subsequent operations; in-flight operations finish on their pinned generation. Existing stale-draft/capture checks remain mandatory before durable filing output.

### Admission and publication

Use a small `authority.current.json` descriptor naming an exact `authority-<physical-sha256>.sqlite3` file, its size, format and logical generation identity. The descriptor carries no registry records. Confine resolution to the authority resource directory, reject unsupported/malformed or dangling references, and never discover a replacement by filename ordering. The database carries its logical manifest, not its own physical file hash.

The publisher holds exclusive publication ownership, validates the complete captured corpus, builds a new database, runs structural and foreign-key checks, then uses a clean reader to traverse and strictly validate every encoded component and semantic relationship. Close/flush the database, compute its physical digest, install it under a new content-addressed path, recheck exact input receipts and atomically switch the descriptor. Failed publication preserves the previous descriptor. Never replace a file held by readers. Orphan/old-generation cleanup is a separate lease-aware operation; inability to remove an open Windows file must not break cutover.

Runtime opens read-only, verifies the entire physical file digest and coherent manifest, schema version, identity and global component/evidence closure before serving an operation. This scans bytes but hydrates no model, fact, profile or evidence payload. Verify file identity around admission and invalidate/refuse changed files; do not cache failures. Use ordinary read-only mode initially, without immutable or memory-mapping shortcuts. Connections have bounded checkout ownership and deterministic closure; a connection is never concurrently used by multiple threads. Resource leases outlive their connections. Require SQLite 3.37 or newer with STRICT metadata tables and a thread-safe build; refuse unsupported libraries explicitly. Use at most four exclusive connection checkouts per reader initially, release each checkout before dependency decoding, and never hold a connection while waiting on another component. Run full integrity and foreign-key checks during publication; runtime admission runs quick_check and global foreign-key/manifest checks in addition to the physical digest. The initial shared component/projection cache budget is 64 MiB of accounted retained weight using LRU eviction; adjust only with recorded workload evidence. Retire unleased old readers promptly. Cleanup never removes the current file or a leased generation and safely skips a generation another process still has open.

On first component access, verify its digest and strictly decode it with its declared dependency context before exposing any result. Full-file corruption anywhere is rejected at admission. Deliberately malformed unused component content with all unsigned digests recomputed may be rejected only when that component is accessed; this replaces the old eager semantic-refusal timing explicitly. Publication still refuses it during complete pre-cutover traversal. Digests provide integrity, not authenticated publisher identity. Do not claim that runtime has revalidated the entire typed corpus merely because admission succeeded.

### Engineering acceptance and rollout

The plan establishes paired comparisons using the same captured source generation and at least ten fresh Python processes per backend on the same machine. Include full admission hashing and first selected operation. Separate import time and total process startup. Initial cutover criteria are median post-import admission plus first M100/M200/M303 operation at most half the paired JSON baseline, incremental authority RSS at most half its baseline, and median cached public context lookup at most 1 ms on the reference workstation. Add fact-only, profile-only, evidence and explicit bulk-enumeration workloads and report their costs. These are engineering acceptance targets, not measured gains or a universal product SLO; a failure blocks cutover rather than silently lowering the target.

Correctness gates additionally prove zero domain payload hydration on open; no unrelated model/evidence loading for a selected request; exact semantic parity; schema-only source/cache invalidation; custom-candidate isolation; cycle/concurrency refusal; generation-safe profile record validation; historical filing-context correctness; and real Windows held-reader publication. Installed CLI/MCP and profile/model/evidence paths must work without authoring files and refuse missing/corrupt authority before durable output.

Build the new writer/reader and parity tools as an unshipped development candidate first. The old shipped backend remains until the coordinated consumer/package cutover passes acceptance. Comparison tools may read historical JSON only in development. No compatibility loader or permanent dual authority remains after cutover.

## Rationale

The selected design moves invariant work to compilation while making runtime cost proportional to requested components. The source-enrollment reference establishes why profile schema must enter the same generation before the format changes. SQLite supplies indexed access without requiring a new domain object system; keeping typed records and canonical resolvers limits semantic risk. Explicit validation timing and generation leases make laziness reviewable rather than an implicit weakening of the current boundary. The indexed-storage research owns the comparative evidence.

## Consequences

Cold access and memory are expected to improve, but must pass the comparative gates. Compilation remains full and may become more expensive because it proves the encoded database independently. A small descriptor accompanies the single data file. Runtime now owns connection/resource leases and bounded caches, and callers must use explicit queries rather than eager graph traversal. Profile schema becomes generation-consistent while taxpayer persistence semantics stay separate. The current JSON backend remains the actual shipped implementation until the plan is executed and accepted.
