---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S25'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add local session telemetry recording per-call trajectory records with session ids

## Scope

- `src/aeat/entrypoints/mcp/_telemetry.py`

## Description

- Author `src/aeat/entrypoints/mcp/_telemetry.py`: per-call trajectory
  records with session ids, appended as JSONL under
  `<aeat_local_storage_root>/telemetry/` (same state-root derivation as the
  diagnostic log).
- LOAD-BEARING PRIVACY DECISION (coordinator): records are METADATA-ONLY —
  tool name, command key, confirmation route, error flag, duration, and
  SHA-256 content hashes of arguments/result — never payloads. A tool result
  carries taxpayer figures; persisting it in plaintext telemetry would breach
  `sensitive-financial-data-secure-storage-only`. Hashes keep records
  comparable (flywheel dedup) with zero figure exposure; full payloads exist
  only in the eval harness's in-memory LiveTrajectory during measurement runs.
- `read_session_records` provides the strict typed roundtrip surface.

## Outcome

Authored by the coordinator. Verified at commit: strict save→load roundtrip;
sequence ordering; the result payload string is absent from the on-disk file
while its hash is present. Ruff clean. Commit follows this record's SHA chain;
server wiring (S23) lands after the W02 executor releases `_server.py`.

## Notes

None.
