---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-01'
modified: '2026-06-01'
step_id: S657
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P56 — S657 + S658: type-ignore paydown classification + first batch

## S657 — Classification audit

Created `.vault/audit/2026-05-31-codebase-solidification-audit.md` with the
99-site inventory bucketed as:

| Bucket   | Count |
|----------|-------|
| Trivial  | 45    |
| Moderate | 42    |
| Hard     | 12    |
| **Total**| **99**|

Trivial cluster A (31 sites): pydantic `model_config` class-variable assignment
(`[assignment]` raised by mypy, unavoidable without mypy plugin).

Trivial clusters B-F: click stub missing (8), ctypes Windows platform (1),
TOML str-key erasure (3), generic getattr bounded (2), runtime CM protocol (4).

## S658 — 15-site batch paydown

Paid down 15 trivial sites from cluster A (pydantic `model_config`):

- `entrypoints/cli/_overview_payloads.py` — 5 sites (original lines 80, 101, 110, 117, 127)
- `entrypoints/cli/_registry_corpus_payloads.py` — 7 sites (original lines 83, 94, 107, 120, 138, 154, 171)
- `entrypoints/cli/_registry_payloads.py` — 3 sites (original lines 34, 55, 74)

Each site received `# TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR` on
the line immediately before the `# type: ignore[assignment]`.

Allowlist shrunk from 99 to **84** entries.

`_registry_payloads.py` lines 87/106/123/139 were shifted to 90/109/126/142 by
marker insertions; allowlist updated to track new live positions.

## Verification

- `test_type_ignore_rationale_inventory.py` — 1 passed
- `test_w26_p56_closure.py` — 3 passed (markers present, allowlist=84, ratchet green)
- Prior-wave ratchets (utf8, cast-rationale, enum-constant, etc.) — 101 passed

Files touched:
- `src/aeat/entrypoints/cli/_overview_payloads.py`
- `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`
- `src/aeat/entrypoints/cli/_registry_payloads.py`
- `src/aeat/test_type_ignore_rationale_inventory.py`
- `src/aeat/test_w26_p56_closure.py`
- `.vault/audit/2026-05-31-codebase-solidification-audit.md`
