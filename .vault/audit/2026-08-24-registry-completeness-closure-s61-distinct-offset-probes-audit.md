---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6dec9ef458a5f9d64a00233c0d9ffcf03e1337276f097a239ab7080c8460d8b8'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S61 distinct offset probes`

## Scope

Independent review of commit `8e001a9dee` for `W01.P02.S61`: distinct `(record_id, field_id)` identities, emitted-byte position overlap refusal, checked-offset count integrity, and the regression's mutation bite. The review covers `dev/registry/filing_export_proof.py` and `dev/registry/tests/test_filing_export_live_proof.py` without modifying production code.

## Findings

No findings. `FilingExportLiveProofEntry` refuses repeated official field identities before an entry can be used. Payload acceptance then records every declared field byte range before returning a proof, rejecting an intersection before the repeated probe can contribute to `checked_official_offsets`. The fixed-width renderer separately requires encoded literal width to equal the declared byte length, so the reviewed range geometry matches emitted bytes. The existing digest, extent, literal-position, and non-executable-export refusals remain intact.

An external runtime mutation replaced only the emitted-position guard with the otherwise identical acceptance flow. The committed overlap regression then failed because it reached the second literal mismatch rather than the required distinct-position refusal, confirming the test would reject a weakened guard. Focused Ruff passed; the commit records the existing focused suite as 11 passed.

## Recommendations

No follow-up is required for S61. Preserve both identity and byte-range checks whenever the live filing-export proof carrier or checked-offset evidence changes.
