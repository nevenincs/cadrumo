---
tags:
  - '#plan'
  - '#modelo-head-digest-performance'
date: '2026-11-15'
tier: L1
related:
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-11-09-modelo-runtime-performance-snapshot-dedupe-adr]]'
modified: '2026-11-15'
body_schema: body-v2
body_hash: 'sha256:75c7eb0f403c62328f96ee389370f1759bc21c39a67342d047bd412af4b550e4'
---

# `modelo-head-digest-performance` plan

## Description

Approved 2026-11-15

Authorization is the operator's OPTIMIZATION instruction and full loop brief to fix measured fundamental performance causes while preserving every tax result and protection. This unit addresses repeated materialization of the saved public registry body during calculation-head hashing. The accepted edit contract requires the full current work/head baseline, including lifecycle-only changes with unchanged revision identity. The accepted snapshot-deduplication decision requires the saved captured rendering, complete hydration and digest/identity verification, exact generation and profile confidentiality. This is internal execution under those constraints: no persisted shape, digest algorithm, wire contract, authority or caching policy changes. No new costly decision is introduced.

The full canonical head remains byte-for-byte identical. Serialize fresh private head/lifecycle fields every invocation; use the existing public registry-payload owner for the already hydrated saved snapshot. Canonicalize that ordinary value into an immutable invocation-local token, release its transient dictionary, and compose it at the exact nested member in the existing envelope through core hashing. The token's public constructor must canonical-encode a normal value; no API accepts unchecked JSON bytes. Add no persistent/global cache, raw-fragment bypass, current-authority substitution or skipped validation. Keep complete projection round-trip checking, revision/CAS checks, pinning, custody and encryption untouched.

## Steps

- [x] `S01` - Compose exact current calculation head bytes without rewalking the large immutable registry fragment and prove parity refusal and cold performance; `src/cadrumo/core/hashing.py, src/cadrumo/application/modelo/edit_services.py, src/cadrumo/core/tests/test_hashing.py, src/cadrumo/application/modelo/tests/test_calculation_head_digest.py and src/cadrumo/adapters/persistence/profile/tests/test_calculation_catalogue_saved_before_a_registry_field.py`.
- [ ] `S02` - Record post-landing persona parity and actual native timing for the landed digest optimization without claiming unmet global latency targets; `.vault/plan/2026-11-15-modelo-head-digest-performance-plan.md and its owning audit and ledger`.

## Parallelization

S01 is sequential. The gpt-6-astra medium architect owns only core/hashing.py, application/modelo/edit_services.py, core/tests/test_hashing.py and application/modelo/tests/test_calculation_head_digest.py under src/cadrumo. The architect additionally owns adapters/persistence/profile/tests/test_calculation_catalogue_saved_before_a_registry_field.py for historical encrypted-storage parity; this routine verification scope correction keeps the two production files unchanged. The orchestrator owns the plan, ledger, audit, feature index, shared gates, review and commit. Terra and Luna summarize context and logs read-only. No edits to ACCEPTANCE's dev paths, FRONTEND UI or DESKTOP native paths. Serialize all merges/adds/commits under the shared lane lock and stage owned paths only.

## Verification

Core tests compare exact bytes to the existing canonical encoder for nested objects, ordering, Unicode and escaping, numeric/null values and invalid inputs. Reject missing/non-object paths, duplicate inserted members, non-string member keys and any unchecked raw-byte ingress without changing ordinary canonical encoding behavior.

Application tests use real synthetic calculation heads and owning serializers. Compare the complete canonical envelope and digest against the existing full model_dump route in all five filing lifecycle states. Cover absent head/rendering, lifecycle-only changes with unchanged ID, same-coordinate snapshot copies, saved versus current authority, directory identities/labels, serializer identity changes, Unicode/numeric encodings, legacy hydrated snapshots and material refusal paths. Never cache private or public fragments across invocations/profiles. Preserve the full round-trip self-check.

Add a meaningful cold invocation performance guard, counting fragment preparation in every optimized call. Measure ordinary wall and process CPU separately, and retained/peak allocations separately; cProfile times are investigative only. Reuse actual owning serializers, not mocked substitutes. Run the five-state filing-state/form parity suite, real edit baseline/refusal tests, Ruff/format, configured types, import boundaries and year/complexity delta. Disclose unchanged baseline failures by exact differential, with no suppressions.

ACCEPTANCE reruns the persona table on landing and must report all existing rows identical. DESKTOP measures native open, page return and post-export latency on the rebuilt head; no native speedup is claimed from a digest-only microbenchmark. Complete one integrated review before handing a single proven source SHA to INTEGRATOR alone, copying PRIME.
