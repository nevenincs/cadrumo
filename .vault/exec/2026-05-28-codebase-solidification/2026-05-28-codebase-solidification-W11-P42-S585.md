---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S585
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W11.P42.S585`

Extended `src/aeat/test_utf8_enrollment_inventory.py` to AST-walk ALL production files under `src/aeat/`.

- Modified: `src/aeat/test_utf8_enrollment_inventory.py`

## Approach

Replaced the fixed `_ENROLLED_MODULES` allowlist with a full-tree ratchet pattern:

- `_all_production_files()` walks every `*.py` under `src/aeat/`, skipping `test_*` and `core/external_constants.py`.
- `_KNOWN_VIOLATING_FILES` (77 files) lists the pre-existing backlog from W07/W09 campaigns. These are skipped in the current test, but tracked for future cleanup.
- Any file NOT in `_KNOWN_VIOLATING_FILES` must have zero bare `"utf-8"` violations.

## Allowlist criteria for hash sites

Lines containing `hashlib`, `hmac`, `sha256`, `sha1`, or `md5` are exempt — the encoding is protocol-mandated for digest input, not an application text-I/O choice.

## Structural prevention

A new file added with bare `"utf-8"` literals fails immediately unless explicitly added to `_KNOWN_VIOLATING_FILES`. The task instruction prohibits adding new violators to that set; the developer must fix instead. This prevents the W11 regression class permanently.

## Test result

`test_no_bare_utf8_literals_in_production_files` — PASSED (753 clean files scanned, 77 ratcheted)
