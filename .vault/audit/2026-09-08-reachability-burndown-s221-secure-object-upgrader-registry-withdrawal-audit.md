---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:900209fcb71f3717ed8eee5d5df3a1f7da36e801266cd75f73e6a8ea62b1116c'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S221]]"
  - "[[2026-07-08-released-data-durability-adr]]"
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
---

# `reachability-burndown` audit: `S221 secure object upgrader registry withdrawal review`

## Scope

Independent review of W05.P12.S221, covering the secure-object schema-lineage API removal, exact-current row decoding, deleted synthetic chain and orphan repository-upgrade tests, retained decode-order and inner-envelope detectors, amended durability decisions, cadence guidance, and Step Record evidence.

## Findings

No critical, high, medium, or low findings.

The removed upgrader registry was empty in production. No composition root registered a hop, no real prior-version fixture entered a production repository reader, and the register/deregister, missing-hop, and byte-chain APIs were exercised only by synthetic tests. The deleted repository schema-lineage test manufactured its own old payload and registration, so it did not establish a durable historical read contract.

The live row boundary remains fail-closed and correctly ordered. `ensure_schema_version_readable` distinguishes newer rows with `schema_version_from_future` and older rows with `schema_upgrade_path_missing`, preserving namespace, stored version, expected version, and missing-from-version context. The row codec invokes this exact-current check and namespace registration before revision verification and AEAD decryption. Consequently neither older nor future ciphertext reaches decryption. For admitted current rows, stored and expected versions are equal, so returning the plaintext directly and recording `max_supported_version` preserves the row's version and payload exactly.

Material inner-envelope protection remains. The version and classification predicates are still live, the version-shape detector still rejects ordering comparisons, and the derivation gate still discovers live readers from production syntax, rejects restated literals with a planted positive, and accepts namespace-derived constants and inline namespace attributes as negative controls. Real secure-object repository suites continue to cover current writes and roundtrips.

The amended durability and compatibility ADRs explicitly require upgrade machinery only alongside a real released prior shape and a production reader/restorability proof, so the deletion is architecturally consistent. The Step Record honestly reports clean residue and Ruff, 79 focused passes, the orphan reduction to 12, and exact movement to 308 unused symbols with 61 unreachable modules and 2029/2091 reachable shipped modules. Independent execution of the narrow schema-lineage and decode-order subset passed all 12 tests.

## Recommendations

Approve W05.P12.S221. When an actual released schema transition occurs, add its reader or migration and prior-byte production-path proof in that transition; do not recreate an empty registry or synthetic chain census in advance.
