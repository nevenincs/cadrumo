---
step_id: "S587"
plan: "[[2026-05-28-codebase-solidification-plan]]"
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W11.P43 S587-S593 — axis finishers

Steps S587 through S593 closed in single execution run by coder-beta15.

## S587 — diagnostics teardown BROAD-EXCEPT-RATIONALE markers

Added `BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-TEARDOWN` token to both `except Exception` clauses at `diagnostics.py:424` (context close) and `diagnostics.py:428` (session close). Teardown must complete unconditionally across heterogeneous async exceptions from playwright internals.

## S588 — diagnostics integrity-probe BROAD-EXCEPT-RATIONALE marker

Added `BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-INTEGRITY-PROBE` token to `diagnostics.py:569` integrity-probe loop except clause. Per-namespace fallback must not abort the loop.

## S589 — diagnostics record-read rationale token

Replaced `# pragma: no cover - record unreadability handled by storage checks` with `# pragma: no cover  # BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-RECORD-READ: record unreadability handled by upstream storage checks; suppression is final-fallback only.` preserving the coverage pragma.

## S590 — wizard next label localised

Wrapped `_commands.py:910` hardcoded `"next"` string through `tr('application.wizard.output_labels.next')`. Added locale key `application.wizard.output_labels.next` to en/es/ca/hu catalogues via `python -m aeat.locales set`.

## S591 — _PdfWord TypeAlias disposition

Chose option (c): document as adapter-internal alias. Rationale: pdfplumber's `Page.extract_words()` returns dicts whose full key-set varies by version and page content; a TypedDict would require `total=False` with all possible keys and would break silently on upstream pdfplumber releases. `_PdfWord` is consumed exclusively within `_parser.py`. Added `ADAPTER-INTERNAL-ALIAS-RATIONALE-PDFWORD` comment block above the alias.

## S592 — _local.py sidecar cast

Changed `_load_sidecar` return type from `dict[str, object]` to `Mapping[str, object]`. Added `typing.cast(Mapping[str, object], raw)` after the isinstance guard. Added `CAST-RATIONALE-SIDECAR-MAPPING` comment. All callers use `.get()` which is valid on `Mapping`.

## S593 — aggregate test

Created `src/aeat/test_w11_p43_axis_finishers.py` with 14 tests covering all four axes. All 14 pass.

## Commit

`1cb42e7ff` — `chore(W11.P43): close S587-S593 axis-finisher steps`

## Files touched

- `src/aeat/application/diagnostics.py`
- `src/aeat/application/wizard/_commands.py`
- `src/aeat/adapters/inbound/declaracion/_parser.py`
- `src/aeat/adapters/outbound/storage/_local.py`
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`
- `src/aeat/test_w11_p43_axis_finishers.py` (new)
