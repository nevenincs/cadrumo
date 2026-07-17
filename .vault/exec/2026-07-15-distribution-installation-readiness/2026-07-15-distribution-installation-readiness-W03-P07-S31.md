---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S31'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Record cohort source digests runtime platform client command transcript result and destination

## Scope

- `dev/packaging/evidence.py`

## Description

- Define one strict versioned result schema for cohort, runtime, client,
  acquisition, executed commands, verdict, observation time, and destination.
- Copy the complete validated release-cohort artifact inventory and manifest digest
  into every evidence record.
- Content-address each record and refuse altered content, changed cohort bytes,
  replacement of prior evidence, non-timezone timestamps, and passing results with
  failed commands or mismatched destination versions.
- Restrict result status to passed or failed so missing and skipped execution cannot
  masquerade as evidence.
- Digest full command streams and retain only explicitly selected safe excerpts.
- Preserve the existing successful-smoke checkpoint path during migration to the new
  cohort evidence contract.

## Outcome

- `cadrumo.distribution-evidence.v1` binds the exact source commit and tag, cohort
  version and identifier, release-manifest digest, every artifact path and digest,
  operating system, release, architecture, Python identity, optional real client
  identity, acquisition source, command transcript, assertions, observations, and
  destination.
- Evidence filenames include both the row and content digest and are written without
  replacing a retained result.
- Full standard output and error streams are hashed rather than persisted, avoiding
  accidental retention of unrelated sensitive runtime output while preserving drift
  detection.
- Focused formatting, Ruff, and type checks passed. Six direct filesystem and process
  tests passed, including an actually executed command, exact-cohort roundtrip,
  evidence mutation rejection, cohort-byte mutation rejection, nonzero-command
  rejection, skipped-status rejection, and legacy checkpoint behavior.

## Notes

- This step establishes the record authority. Required-row aggregation and blocking
  release-readiness policy remain in `S32` and `S33`; platform and client workflow rows
  must emit this contract as they are completed.
