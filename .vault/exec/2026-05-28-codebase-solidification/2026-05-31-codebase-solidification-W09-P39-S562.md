---
step_id: S562
phase: P39
wave: W09
date: 2026-05-31
modified: '2026-05-31'
status: closed
agent: coder-gamma13
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W09.P39.S562-S568 — locale + pydantic boundary hardening

## Steps Closed

S562, S563, S564, S565, S566, S567, S568

## Changes Landed

### S562 — wizard status tab-key through tr()
- `src/aeat/application/wizard/_commands.py` line 907: `"status\t{verb}"` → `f"{tr('application.wizard.output_labels.status')}\t{verb_label}"`
- All 4 locale files (`en.yml`, `es.yml`, `ca.yml`, `hu.yml`): added `status:` key under `output_labels` block with locale-appropriate values (status / estado / estat / állapot).
- `src/aeat/application/wizard/test_commands.py`: updated `_EXPECTED_STATUS_LABEL` assertion to use `tr('application.wizard.output_labels.status')` so the test drives from locale authority.

### S563 — catalogue f-string sites documented as bounded survivors
- `src/aeat/locales/_ast_scanner.py`: added inline documentation block on `_DYNAMIC_TRANSLATION_ROOTS` naming each wizard._catalogue f-string pattern (confirm prompts + enum-choice labels) as a bounded dynamic-dispatch survivor covered by the `wizard.*` namespace marker.

### S564 — Google API TypedDicts
- `src/aeat/adapters/outbound/google/_api.py`: defined `GoogleDriveFile`, `GoogleSheetsRange`, `GoogleSpreadsheet` TypedDicts (inheritance-split pattern to work around `from __future__ import annotations` + `Required[]` deferral in Python 3.13). `GoogleApiResponseBody` alias retained for `execute_request` return type.

### S565 — OAuth client payload typed boundary
- `src/aeat/entrypoints/cli/_config/_google.py`: added `OAuthClientPayload: TypedDict` (for documentation) and `_OAuthClientWrapper: BaseModel` (pydantic, `extra="ignore"`) for runtime validation. Replaced `isinstance(payload, dict) or "installed" not in payload` + inner isinstance checks with `_OAuthClientWrapper.model_validate(raw_payload)`.

### S566 — InvoiceRowPayload TypedDict
- `src/aeat/application/invoices/_importing.py`: added `InvoiceRowPayload(TypedDict, total=False)` with all fields used by the import pipeline. Updated `_decode_invoice_payload` return type from `tuple[Mapping[str, object], ...]` to `tuple[InvoiceRowPayload, ...]`. Updated `_synthesise_single_line_if_needed` parameter type from `dict[str, object]` to `dict[str, Any]`.

### S567 — Orphan namespace __init__ modules documented
- `src/aeat/application/storage/__init__.py`: docstring-only → added namespace-container intent paragraph explaining callers must import from subpackages directly.
- `src/aeat/domain/calculations/__init__.py`: same pattern.
- Decision: retain (not delete) — both serve as intentional namespace-container `__init__` files; zero callers import from the top-level `__init__` directly (confirmed by grep).

### S568 — Aggregate real-behavior test
- `src/aeat/test_w09_p39_locale_pydantic.py`: 19 tests covering all 7 steps. All pass.

## Verification

- `pytest src/aeat/test_w09_p39_locale_pydantic.py` — 19 passed
- `pytest src/aeat/application/wizard/test_commands.py` — 2 passed
- `pytest src/aeat/application/invoices/ src/aeat/locales/` — 97 passed
- `ruff check` — clean on all touched files (1 pre-existing RUF100 in `_api.py` not introduced here)
- `python -m aeat.locales audit` — all 4 locale files ok
