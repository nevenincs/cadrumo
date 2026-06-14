---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S37'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S37 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The A1 Add core.hashing canonical-JSON content-hash helper and route the cross-layer json+sha256 sites through it and ## Scope

- `src/aeat/core/hashing.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
