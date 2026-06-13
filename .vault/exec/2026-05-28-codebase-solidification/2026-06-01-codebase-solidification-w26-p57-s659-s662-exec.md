---
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
step_id: S659
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P57 — S659/S660/S661/S662

## Steps executed

- **S659**: Cluster B click-stub markers (8 sites, `entrypoints/cli/_doc_reference.py`)
- **S660**: Cluster A continuation pydantic model_config markers (17 sites across `_config_payloads.py`, `_root_payloads.py`, `_config/_google_payloads.py`, `_config/_profile_census_payloads.py`, `_registry_payloads.py`)
- **S661**: Clusters C/D/E/F markers (10 sites: `_stdio.py`, `_loader.py`, `_schema.py`, `_actions.py`, `diagnostics.py`, `repair_integrity.py`)
- **S662**: Created `src/aeat/test_w26_p57_closure.py` verifying all markers present, allowlist size == 49, ratchet green

## Allowlist accounting

| Batch | Cluster | Sites | Token |
|-------|---------|-------|-------|
| S659 | B (click stubs) | 8 | `TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING` |
| S660 | A cont. | 17 | `TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR` |
| S661 | C (ctypes) | 1 | `TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES` |
| S661 | D (TOML key) | 3 | `TYPE-IGNORE-RATIONALE-TOML-STR-KEY-ERASURE` |
| S661 | E (getattr) | 2 | `TYPE-IGNORE-RATIONALE-GENERIC-GETATTR-BOUNDED` |
| S661 | F (CM proto) | 4 | `TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL` |
| **Total** | | **35** | |

Allowlist: 84 → 49 (35 entries removed).

Note: ratchet line numbers for `_modelo.py` updated to reflect pre-existing WIP from concurrent campaign (lines shifted +2 near line 440, +2 near 1267 due to peer edits at `describe_modelo` and `formulas` functions). No marker added; only the recorded line numbers corrected.

## Test outcome

`pytest src/aeat/test_type_ignore_rationale_inventory.py src/aeat/test_w26_p57_closure.py` — 6 passed.
