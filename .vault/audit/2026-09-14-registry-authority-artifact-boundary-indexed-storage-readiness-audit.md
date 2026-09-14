---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:d4bd971d3ae33ce5252a7f3278127d48b07283ab80bf53f5ca00bd03390c53b8'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference]]"
---

# Authority storage readiness and profile facts schema enrollment

## Scope

Audit the source-to-authority boundary and runtime loading contract before planning an indexed backend. Code evidence and the read-only input inventory probe are recorded in the related source-enrollment reference. This audit does not certify current publication currency: other work is changing corpus inputs. No production implementation is changed here.

## Findings

### profile-schema-enrollment | high | Compilation reads a schema that publication does not identify or ship

The profile facts schema is an ambient compiler dependency and a separate runtime TOML input. It is absent from both publication receipt roots and the authority payload. The obsolete fingerprint path does not point at its real sibling location. A custom candidate can therefore validate against the checkout's profile schema, and a schema edit can leave authority identity unchanged. Evidence: `dev/registry/compiler/validator.py:422`, `dev/registry/compiler/authority.py:110`, `dev/registry/compiler/loader_fingerprints.py:232`, `dev/registry/pipeline/authority_publication.py:367`, `src/cadrumo/domain/user_profile/loader.py:39`. This confirms the missing enrollment for profile-fact declarations; the blanket claim that governed tax facts are absent is incorrect.

### eager-public-contract | high | The public authority shape requires wholesale typed reconstruction

The artifact and authority hold all models, catalogues and evidence, and model lookup returns all revisions. Replacing the serializer without changing consumer access cannot deliver selective hydration. Evidence: `src/cadrumo/domain/calculations/registry/authority_artifact.py:287`, line 528, and `src/cadrumo/domain/calculations/registry/authority.py:132`. An explicit typed component-access boundary and consumer migration are prerequisites for the intended performance benefit.

### fact-bootstrap | high | Lazy decoding must preserve generation-scoped vocabulary dependencies

Typed model validation already reads facts from an explicitly scoped candidate to avoid recursively entering bundled admission. A lazy loader that decodes a revision before loading its vocabulary dependencies can deadlock, refuse incorrectly or consult a different generation. Evidence: `src/cadrumo/domain/calculations/registry/authority_artifact.py:564`, `src/cadrumo/domain/calculations/registry/governed_fact_scope.py:50`. Compilation must establish dependency closure; runtime must load it under the pinned generation with explicit cycle/re-entry refusal.

### admission-timing | high | Lazy loading cannot claim unchanged eager semantic refusal timing

Current tests reject even digest-consistent malformed unused typed payloads at open. Selective hydration defers those semantic checks until access. Whole-file digest verification can preserve immediate raw-byte corruption detection, but it cannot authenticate a rewritten artifact whose unsigned digests were all recomputed. Evidence: `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py:264`. The ADR must explicitly distinguish full publication validation, admission integrity and component-use validation; silently deleting negative tests would weaken the contract without a decision.

### generation-lifetime | high | SQLite introduces long-lived handles that fixed-path replacement does not address

The current JSON reader releases its file after reading bytes and replaces a single fixed path. A lazy SQLite reader must retain access to the same generation throughout an operation. Publication therefore needs immutable generation files, a coherent descriptor switch, bounded retained readers and deterministic connection/resource lifetime. Evidence: `src/cadrumo/domain/calculations/registry/authority_artifact.py:340`, line 386, `src/cadrumo/domain/calculations/registry/authority.py:583`, `src/cadrumo/core/resources/bundled_data.py:77`. Windows held-reader cutover needs a real multiprocess test.

### consumer-enumeration | medium | Existing callers bypass point lookup and expand evidence eagerly

Direct model/catalogue/fact traversal occurs in filing, calculation, profile grounding, IVA, categories, deadlines and reporting. Evidence examples: `src/cadrumo/application/filing/runtime.py:362`, `src/cadrumo/domain/calculations/registry/profile_grounding.py:103`, `src/cadrumo/domain/iva/rates.py:37`, `src/cadrumo/domain/categories/registry.py:60`. The plan must name these cohesive consumer areas and separate deliberate full enumeration from point reads. Canonical temporal selection remains in `src/cadrumo/domain/calculations/registry/temporal.py:204`.

### package-proof | medium | Existing archive tests permit the separate profile schema and pin JSON paths

Packaging excludes the AEAT authoring tree but not the sibling profile schema. Format-specific includes and installed tests require coordinated migration. Evidence: `pyproject.toml:269`, line 305, `src/cadrumo/tests/test_wheel_content_boundary.py:309`, `dev/packaging/tests/test_installed_oracles.py:450`. Proof must cover profile operations as well as model/fact queries with authoring resources absent.

### performance-acceptance | medium | The current benchmark supplies observations without cutover criteria

The benchmark measures eager hydration and warm access but does not expose component reads, cache memory or enforce comparative cutover targets. Evidence: `dev/registry/benchmark_authority.py:14`. The next plan needs paired generation-equivalent workloads, post-import authority costs, separate total startup, incremental memory and explicit enumeration behavior. Previous measurements remain historical evidence, not measurements of SQLite.


### filing-default-context | high | Default export and verification select a schema without the draft coordinate

`src/cadrumo/application/filing/export.py:232` and `src/cadrumo/application/filing/export_verification.py:201` omit the draft year/period when building their default provider. `src/cadrumo/application/filing/runtime.py:684` then selects the newest open revision and invents a coordinate. This can compare a historical draft with the wrong schema and reject it as stale; emission of incorrect filing bytes has not been demonstrated. Require the draft's legal coordinate or pinned capture, and preserve latest inspection only as non-filing metadata access.

### recursive-provider-census | high | Unowned nested fact declarations are omitted without refusal

The ownership validator misses `rogue/nested/0001-omitted.toml`; an isolated call reproduced acceptance. The full source receipt can therefore change for a declaration that no compiler consumes. Evidence: `dev/registry/compiler/fact_providers.py:303`. At the same time the existing exact-child-owner test fails against recursive ownership of the registered facts subtree. Define subtree ownership consistently, recursively refuse unowned fact declarations and reconcile the stale test with the authored layout.

### profile-envelope | medium | Unknown root tables are silently ignored

A temporary real profile-schema copy with an unknown top-level table passed the loader. Evidence: `src/cadrumo/domain/user_profile/loader.py:86`. The development parser must validate the entire envelope before projecting the typed schema; publication must additionally validate declared profile legal references at the existing legal-catalogue boundary.

### provider-enrollment-contract | medium | Dependency declarations are not executable receipts

Provider lifecycle fields and inherited domains do not yet drive component dependency validation. Current full-input hashing avoids a proven stale projection here, but these fields cannot justify a lazy dependency graph or selective publication. Evidence: `dev/registry/compiler/fact_providers.py:88`, line 196. Enroll explicit validated dependencies and reject missing/unknown domains. Add family schema/query/result/codec parity coverage; preserve full compilation.

### profile-record-bootstrap | high | Hidden schema reads can cross generations during secure record validation

Record defaults and validators call the raw profile loader, and application projections retain a separate process-lifetime schema cache. Migrating visible service callers alone would preserve mixed-generation behavior. Evidence: `src/cadrumo/domain/user_profile/values.py:236`, `src/cadrumo/application/user_profile/projections.py:42`. Require explicit pinned schema context at record construction/deserialization, remove the duplicate cache and preserve existing version mismatch and secure-storage behavior.

## Recommendations

Record an indexed-storage decision that makes profile schema declarations a first-class typed component, captures their exact input alongside AEAT and evidence roots, and removes runtime authoring-file access. Preserve the existing governed-fact schema and provider path; repair its coverage rather than replacing it with another facts registry.

Decide the typed loader layers, cache/generation contract and validation timing explicitly before implementation. Publish only fully validated complete generations. Keep taxpayer values and private evidence in encrypted persistence, outside the public authority database.

Plan a staged build and benchmark followed by one coherent runtime/package cutover, with no permanent JSON fallback or partial publication. Require schema-only invalidation, custom-candidate isolation, strict parser refusal, semantic round trips, dependency-cycle refusal, real held-reader publication and isolated installed profile/model/evidence operations.
