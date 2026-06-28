---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S44-001 | MEDIUM | Plaintext absence proof does not cover provider sidecar artifacts
`W05.P10.S44` adds a real-behavior encrypted round trip through `SecureObjectRepository`, `iter_all_records_raw`, `LocalFileSystemProvider`, and the remote mirror inspection functions. The new test proves the fetched mirrored object payload and persisted manifest payload do not contain the sentinel plaintext. It does not inspect the provider's full remote artifact set, including filesystem sidecars and filenames produced by `LocalFileSystemProvider.put`. A regression that leaked plaintext through a provider label, sidecar JSON field, or generated object name could still pass because `LocalFileSystemProvider.get` returns only the object payload and typed metadata, not the raw sidecar contents. Since the step is intended to prove plaintext does not reach the remote mirror, the test should scan or otherwise assert over every file persisted under the mirror root, not only the fetched object bytes and manifest bytes.

## S44-002 | LOW | Opaque mirror test bypasses registered namespace policy
The S44 test uses an ad hoc namespace value and constructs `SecureObjectRepository` without `STORAGE_NAMESPACE_REGISTRY`. That still exercises the encryption and provider boundaries, and it avoids fakes, mocks, stubs, monkeypatches, skips, and xfails. However, `W05.P10` follows the namespace-registry remote mirror policy work, where production namespaces default to ciphertext-with-metadata and require revision plus integrity metadata. Because the test bypasses that registry binding, it does not prove the opaque mirror behavior under a registered production namespace contract. Prefer binding the production registry and using an existing ciphertext-mirror namespace, or adding an explicit test-only registry entry if this fixture namespace must remain synthetic.

## S44-003 | INFO | No HIGH or CRITICAL findings
The reviewed S44 addition is a focused real-behavior test and the focused suite passed with `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py`. No HIGH or CRITICAL findings were identified.

## S44-004 | INFO | S44-001 resolved by full mirror artifact scan
The remediated S44 test now scans every artifact under the mirror provider root and asserts both relative artifact paths and raw file bytes do not contain the plaintext sentinel. This covers payload objects, manifest objects, sidecar JSON files, and generated filenames rather than only values returned through `LocalFileSystemProvider.get`. The previous S44-001 plaintext-leak proof gap is resolved.

## S44-005 | LOW | S44-002 narrowed: registry namespace is used, but repository enforcement is still not bound
The ad hoc namespace concern from S44-002 is resolved: the test now loads `google_oauth_metadata` from `STORAGE_NAMESPACE_REGISTRY`, writes under that registered namespace value, uses the namespace definition's sensitivity, and asserts `CIPHERTEXT_WITH_METADATA` plus required revision and integrity metadata. The remaining gap is narrower: `SecureObjectRepository` is still constructed without `namespace_registry=STORAGE_NAMESPACE_REGISTRY`, so `_registered_namespace_definition` returns `None` and write-policy enforcement is not exercised at the secure-object boundary. The test proves alignment with a production namespace definition, but it does not prove that a registry-bound repository would reject a namespace, sensitivity, or schema mismatch on this mirror path.

## S44-006 | INFO | No HIGH or CRITICAL findings after remediation
No HIGH or CRITICAL findings were identified in the remediated S44 surface. Local validation was reported as ruff passing, focused pytest passing with 21 tests, and diff check passing; this re-review did not rerun those gates.

## S44-007 | INFO | S44-005 resolved by registry-bound repository construction
The final S44 test now constructs `SecureObjectRepository` with `namespace_registry=STORAGE_NAMESPACE_REGISTRY` while using the registered `google_oauth_metadata` namespace definition for namespace, sensitivity, and remote mirror policy assertions. This exercises the secure-object write policy under the same registry binding that enforces registered namespace, sensitivity, and schema contracts. The previous S44-005 residual enforcement gap is resolved. No HIGH or CRITICAL findings were identified in this final short re-review. Local validation was reported as ruff passing, focused pytest passing with 21 tests, and diff check passing; this re-review did not rerun those gates.
