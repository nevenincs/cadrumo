---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f064383e3ec7ad1d05c527308e820388d554b45fa5dff3431795546462fd1299'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s01 inventory review`

## Scope

Reviewed the `W01.P01.S01` changes in `dev/audit/object_names.py` against the
accepted inventory contract, its research and repository reference, and the
current focused tests. The review covered complete declaration serialization,
line-independent qualified binding locators, schema-qualified finding IDs, raw
source-byte hashes, the canonical inventory digest, deterministic ordering,
identity collision safety, and compatibility of the existing text and JSON
surfaces. No implementation or test file was changed by this review.

The live repository inventory emitted 61,453 declaration records and 2,288
findings. Its 2,288 finding IDs were unique. The focused suite completed with 22
passing tests, and Ruff reported no issue for the implementation and its focused
test module. The existing text renderer is unchanged, while the JSON surface
retains `findings` and `summary` and adds only inventory fields and per-finding
identity evidence.

## Findings

### inventory-contract-tests | medium | New digest and drift guarantees lack detector-teeth coverage

The production change emits raw-byte `source_hash` values, a canonical
`inventory_digest`, schema-qualified finding IDs, and binding-occurrence locators,
but the focused tests currently assert only one redeclaration locator, overload
occurrence coalescing, and whole-JSON equality after reversing a declaration
sequence. They do not prove that a raw byte change changes the affected source
hash and inventory digest, that unrelated line movement preserves a finding ID,
that declaration records are complete for modules and symbols, or that source
drift is visible while deterministic reruns remain byte-for-byte stable. These
are execution preconditions for the later manifest and replay stages, so a defect
in hash input, canonical projection, or identity membership could pass the
present suite. This is an open verification finding assigned to the planned
`W01.P01.S02` test step; it does not identify a defect in the reviewed production
algorithm.

## Recommendations

Resolve `inventory-contract-tests` in `W01.P01.S02` with isolated filesystem
fixtures that prove raw-byte hashing, digest stability and sensitivity,
line-movement-stable finding IDs, distinct binding occurrences, complete module
and symbol records, and deterministic JSON across reruns and input ordering.
Include a representative drift mutation so the detector demonstrates both its
normal path and its refusal-enabling evidence in the same suite.
