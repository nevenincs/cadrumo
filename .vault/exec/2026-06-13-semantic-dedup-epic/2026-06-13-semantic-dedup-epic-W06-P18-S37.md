---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S37'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# A1 Add core.hashing canonical-JSON content-hash helper and route the cross-layer json+sha256 sites through it

## Scope

- `src/aeat/core/hashing.py`

## Description

- Added `canonical_json_bytes` and `content_hash_hex` to `core.hashing` as the
  single canonical-JSON content-addressing primitive; exported both.
- Confirmed all 13 target files were peer-clean before editing.
- Routed the 12 substitutable cross-layer sites through `content_hash_hex`
  (calc-revision, filing-record, verification-report, bucket-event, ledger
  manual/export x2, repair-integrity, invoice-id, transaction fingerprints x2,
  filing/amendment truncated x2) and the llm usage storage write through
  `canonical_json_bytes`; `ruff --fix` dropped the now-unused `sha256_hex`/
  `json`/`hashlib` imports.

## Outcome

Committed as `6112a72d1`, tagged `relocation:content_hash_hex` (13 files,
+59/-69). Verified the kernel is byte-identical to every converted inline form
(plain + `ensure_ascii=True` variants), so all content hashes/ids are unchanged;
244 hash/fingerprint/roundtrip tests across the touched packages green; full
collect-only clean.

## Notes

The split-fingerprint at `transactions/_models.py:686` uses `ensure_ascii=False`
(raw UTF-8) — NOT substitutable by the default-`ensure_ascii=True` kernel; left
as-is (constraint-divergent), so `transactions._models` retains its `sha256_hex`
import for that one site. Fixed an initial `.....core` (5-dot) import typo in
`llm/_usage.py` down to `....core`.
