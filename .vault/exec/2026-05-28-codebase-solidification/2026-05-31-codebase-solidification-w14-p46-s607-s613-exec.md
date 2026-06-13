---
step_id: "S607-S613"
date: 2026-05-31
modified: '2026-05-31'
campaign: codebase-solidification
wave: W14
phase: P46
commit: 6309171ac
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W14.P46 S607-S613 Step Record

## Steps executed

- **S607** — `application/auth/_acquisition_lock.py:188`: added `BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN` inline on `except Exception:`.
- **S608** — `application/auth/_sessions.py:592/:598`: added `BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN` on both teardown `except Exception:` sites.
- **S609** — `adapters/outbound/aeat/sede/_browser_stage.py:5`: moved `import logging` to `TYPE_CHECKING` block (option a — no runtime logging instantiation in this file; `from __future__ import annotations` makes all annotations strings at runtime).
- **S610** — `entrypoints/cli/_log_levels.py:14`: added `LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE` marker on `import logging` (option b — constants-only use at module scope; migrating to `aeat.core.logging` would require broader refactor).
- **S611** — introduced `file_stat_fingerprint(path: Path) -> tuple[str, int, int]` in `aeat.core.paths`; migrated 4 callers (`domain/categories/_registry.py`, `domain/iva/_catalogue.py`, `application/topics/__init__.py`, `domain/normatives/_loader.py`); normatives OSError wrapper preserved at call-site.
- **S612** — `domain/calculations/registry/_renta_web_open_oracle.py`: extracted `_RENTA_WEB_OPEN_DEFAULT_YEAR: Final[int] = 2025`; migrated both `year=2025` sites; refactored long `planned_operations` return to extract `template` / `app_url` locals (fixes E501).
- **S613** — `src/aeat/test_w14_p46_survivor_closure.py`: 14 tests covering all 6 structural closures + 5 prior inventory ratchet existence + content checks.

## Post-condition gates

- Grep `def _file_fingerprint` across `src/aeat/`: **0 survivors** (S611 gate passed).
- `ruff check` on all 12 modified files: **all checks passed**.
- `pyright` on all 12 modified files: **0 errors** (2 pre-existing warnings in unmodified code paths).
- `pytest src/aeat/test_w14_p46_survivor_closure.py`: **14/14 passed**.
- `pytest src/aeat/test_broad_except_and_any_return_rationale.py src/aeat/test_utf8_enrollment_inventory.py src/aeat/test_ratchet_extensions_and_marker_completion.py`: **18/18 passed** (W11/W12 ratchets green).
- Broader affected module suite (351 tests): **350 passed, 1 pre-existing failure** in `test_catalogue_verification.py::test_committed_registry_tree_has_required_model_law_coverage` (registry TOML coverage gap, unrelated to this campaign).

## Collision signal

`git diff` on all target files at start: **no non-authored WIP** on any target file.

## Commit

`6309171ac` — `audit(W14.P46.S607-S613): broad-except rationale markers, logging TYPE_CHECKING, file_stat_fingerprint dedup, oracle year constant`

## Files touched

- `pyproject.toml` — S105 per-file-ignore for W14 test file
- `src/aeat/adapters/outbound/aeat/sede/_browser_stage.py` — S609
- `src/aeat/application/auth/_acquisition_lock.py` — S607
- `src/aeat/application/auth/_sessions.py` — S608 + pre-existing RUF100 fixes
- `src/aeat/application/topics/__init__.py` — S611 caller migration
- `src/aeat/core/paths.py` — S611 canonical `file_stat_fingerprint`
- `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py` — S612
- `src/aeat/domain/categories/_registry.py` — S611 caller migration
- `src/aeat/domain/iva/_catalogue.py` — S611 caller migration
- `src/aeat/domain/normatives/_loader.py` — S611 caller migration
- `src/aeat/entrypoints/cli/_log_levels.py` — S610
- `src/aeat/test_w14_p46_survivor_closure.py` — S613 (new file)
