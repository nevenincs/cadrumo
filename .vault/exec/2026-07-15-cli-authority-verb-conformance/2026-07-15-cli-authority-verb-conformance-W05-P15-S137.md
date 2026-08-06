---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:df8fee6fd1a407e13bcfbbdf790e5d1efeb1a6b84ec23fa20c3bba589052d996'
step_id: 'S137'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert exact new schema keys, removed-key absence, exclusivity, and secret-free results

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Add a registry-wide recursive scan asserting no registered result schema, nor any payload model nested inside one, declares a secret-bearing field.
- Add an anti-tautology proof planting a secret directly and one level below a nested payload, requiring the scan to report both.
- Add an exact-key and exclusivity gate for the passphrase, recovery, and reset result keys, refusing two custody keys that share one schema class.
- Add a field enrolment gate pinning the audited secret-free field set of every custody envelope.
- Add an absence gate for the retired lock, rekey, flat scoped reset, legacy show-recovery and verify-recovery, sandbox-use, and modelo audit replay keys.
- Materialise the registry through the live command tree before each scan so a lazily-imported payload module cannot leave the registry partly populated.

## Outcome

Modified `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py` only, additively: 220 insertions, one import line extended.

The confidentiality invariant now has teeth. The forbidden-name set is derived from the confidentiality contract rather than from the current tree, and deliberately excludes metadata *about* a secret: a probe of the live registry (295 schemas) found eleven fields matching a naive sensitive-substring pattern, and every one proved to be non-secret metadata such as a boolean `has_secret`, a secret-store directory path, an AEAT period code, or LLM token counts. A substring gate would have red-lined all eleven and invited weakening; the exact-name rule distinguishes carrying a secret from describing one.

Each of the four gates was mutation-verified to fire on the exact defect it guards, not merely to pass: resurrecting a retired key, adding a field to a custody result, pointing two custody keys at one schema class, and planting a `mnemonic` field on a registered result each produced the expected failure with a precise diagnostic. A gate that cannot fail would have been worthless here.

Verification: the full conformance module runs 159 passed with `-m ""` and `-n0`, so no marker filter deselected a lane and no serial test was held out of an xdist run. `ruff check`, `ruff format --check`, and `just check-types` are clean.

## Notes

The Phase premise did not hold. Thirteen of the fourteen Steps assigned in this Phase were already satisfied in the tree, landed under the successor plans this document was split into rather than under its own Wave records, so the low exec-record count for the Wave understated real progress. S137 was the single Step carrying genuine unlanded work: the conformance module contained no secret-free, removed-key, exclusivity, or enrolment assertion before this change.

No production code was modified. The scan found no confidentiality defect to repair, so this Step lands the gate that keeps it that way rather than a fix.

The plan's own status header still reports 64 of 254 Steps complete while the CLI reports 158 of 284, and it instructs readers not to execute from this document. That header is stale and contradicts the live counts; reconciling it is outside this Step's scope and is reported to the coordinator.
