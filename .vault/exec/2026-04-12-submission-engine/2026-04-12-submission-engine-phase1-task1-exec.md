---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Submission Engine — Execution Record
related:
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# exec step: filing submission engine

## plan reference

Executes every phase of
`[[2026-04-12-submission-engine-plan]]` in one combined record (the
plan's phase-1 through phase-5 collapsed into a single step because
every phase feeds strictly into the next and the whole feature ships
together).

## work performed

- **Phase 1 — schema + errors + protocols.** Shipped
  `src/aeat/adapters/outbound/aeat/export/_models.py` (pydantic v2 strict+frozen
  `SubmissionStatus` / `SubmissionAttempt` / `SubmittedFiling` with
  time-ordering and ACK-consistency `@model_validator`s, plus
  `make_submission_id` returning a stable SHA-256 prefix),
  `_errors.py` (`SubmissionError` and three subclasses, all rooted
  at `AeatError`, `Translatable` payload), `_protocols.py`
  (Protocol / pydantic stubs for #6 / #7 / #8 / #23 / #38 / #39 /
  #44), colocated `test_models.py` and `test_errors.py`.
- **Phase 2 — preflight + engine.** Shipped `_preflight.py` with
  four ordered gates, `_engine.py` with:
  - `SubmissionEngine.submit_draft(draft, *, dry_run=True,
    override_confirmation=False, today=None)`.
  - Double-gate live submission: requires BOTH
    `override_confirmation=True` AND
    `settings.aeat_submission_require_human_confirmation=True`.
  - Flat JSON persistence under `settings.aeat_submissions_dir`.
  - `load_submission` / `list_submissions` helpers for the CLI.
  - Colocated `test_preflight.py` (six gate branches) and
    `test_engine.py` (default-dry-run safety, double-gate refusal,
    persistence round-trip, list filtering).
- **Phase 3 — submitter ABC + Modelo 130 PoC.** Shipped
  `_submitters/__init__.py` (`Submitter` ABC with `dry_run`/
  `submit` coroutines), `_submitters/_contract.py`
  (`BrowserSessionLike` narrow Protocol), `_submitters/modelo130.py`
  (casilla-keyed form fill, screenshots at every step, Playwright
  trace start/stop, aborts before final "Firmar y Enviar" click in
  dry-run), `_submitters/test_modelo130.py` (recording-session
  double, happy-path dry-run/submit, unknown-casilla rejection).
- **Phase 4 — settings + CLI wiring.** Added four Settings fields
  (`aeat_submissions_dir`, `aeat_submission_dry_run_default`,
  `aeat_submission_require_human_confirmation`,
  `aeat_submission_browser_trace_dir`) with matching
  `env/.env.example` entries. Shipped `src/aeat/entrypoints/cli/submission/`
  Typer sub-app with `preflight`, `dry-run`, `submit`, `show`,
  `list` subcommands; `submit` refuses without
  `--i-understand-this-is-real`. CLI registered in
  `src/aeat/entrypoints/cli/__init__.py`.
- **Phase 5 — live rehearsal + verification.** Shipped
  `test_live_submission.py` gated on `AEAT_LIVE_TESTS=1`
  (`@pytest.mark.live`), always dry-run. Ran full verification
  matrix (ruff, ty, pytest, prek) — all green.

## tests added

| file | marker | cases |
| ---- | ------ | ----- |
| `src/aeat/adapters/outbound/aeat/export/test_models.py` | unit | 16 |
| `src/aeat/adapters/outbound/aeat/export/test_errors.py` | unit | 3 |
| `src/aeat/adapters/outbound/aeat/export/test_preflight.py` | unit | 6 |
| `src/aeat/adapters/outbound/aeat/export/test_engine.py` | unit | 6 |
| `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py` | unit | 4 |
| `src/aeat/entrypoints/cli/submission/test_cli.py` | unit | 8 |
| `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` | live | 1 (skipped) |

## verification matrix

- `uv run ruff check .` → clean.
- `uv run ty check src tests` → 0 diagnostics.
- `uv run pytest -q` → 362 passed, 1 skipped, 10 deselected.
- `uv run prek run --all-files` → all hooks pass.

## follow-ups

- Rebase-swap each Protocol stub for the real subpackage as #6, #7,
  #8, #23, #39, #44 merge.
- Once #10 storage is in use, migrate persisted filings from flat
  JSON to the SQLite audit table.
- Add Modelo 303 / 111 / 115 submitters as follow-up issues.
