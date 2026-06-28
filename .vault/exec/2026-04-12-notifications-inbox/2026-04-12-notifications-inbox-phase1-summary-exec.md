---
tags:
  - "#exec"
  - "#notifications-inbox"
date: 2026-04-12
modified: '2026-04-12'
title: AEAT notifications inbox — phase 1 exec summary
related:
  - "[[2026-04-12-notifications-inbox-plan]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
  - "[[2026-04-12-notifications-inbox-research]]"
issue: wgergely/aeat#46
---

# exec summary: aeat notifications inbox — phase 1

End-to-end execution of `[[2026-04-12-notifications-inbox-plan]]` on
branch ``feature/46-notifications-inbox``.

## artifacts produced

### `src/aeat/inbox/` — new subpackage

- `__init__.py` — package docstring, public re-exports.
- `_errors.py` — `InboxError`, `InboxFetchError`,
  `InboxAcknowledgeError` (all under `aeat.core.errors.AeatError`).
- `_models.py` — strict+frozen pydantic v2:
  `NotificacionKind(StrEnum)`, `NotificacionPriority(StrEnum)`,
  `Notificacion(BaseModel)`, `Inbox(BaseModel)` with unique-id
  invariant.
- `_protocols.py` — `RawNotificacion` strict model and
  `NotificacionSource` runtime-checkable Protocol stubbing #43.
- `_classifier.py` — ordered rule table + `_APPEAL_WINDOWS` table.
  `classify()` returns `(OTRO, HIGH)` for any unmatched subject
  (ADR D3). `appeal_window_for()` / `compute_appeal_deadline()`.
- `_deadline.py` — `next_appeal_deadline()` helper.
- `_fetcher.py` — `InboxFetcher` composing source + classifier +
  disk persistence. Async `fetch_new` / `acknowledge` /
  synchronous `load_inbox` / `save_inbox`.
- Colocated tests: `test_models.py`, `test_classifier.py`,
  `test_deadline.py`, `test_fetcher.py`, `test_live_inbox.py`.

### `src/aeat/entrypoints/cli/inbox/` — new CLI sub-app

- `__init__.py` wires `fetch`, `list`, `show`, `ack`, `next-deadline`
  into the root `aeat` typer app.
- `_helpers.py` with a real file-backed `_FileBackedNotificacionSource`
  (not a mock — a concrete Protocol-conforming class).
- One file per subcommand + `test_cli.py`.
- Wired into `src/aeat/entrypoints/cli/__init__.py`.

### `src/aeat/config.py` + `env/.env.example`

- `AEAT_INBOX_DIR`, `AEAT_INBOX_PDF_DIR`, `AEAT_INBOX_ALERT_LEAD_DAYS`.
- `tests/test_config.py` alignment green.

### vault

- `.vault/research/2026-04-12-notifications-inbox-research.md`
- `.vault/adr/2026-04-12-notifications-inbox-adr.md`
- `.vault/plan/2026-04-12-notifications-inbox-plan.md`
- This exec summary.

## verification

- `uv run ruff check .` → **All checks passed**.
- `uv run ty check src tests` → **All checks passed**.
- `uv run pytest` → **442 passed, 1 skipped, 16 deselected** (live
  tests remain skipped until opt-in).
- `uv run prek run --all-files` → **All hooks passed**.

## acceptance matrix (wgergely/aeat#46)

| Requirement | Status |
|---|---|
| `src/aeat/inbox/` subpackage with public API | ✔ |
| Pydantic v2 strict everywhere | ✔ |
| `NotificacionKind` / `NotificacionPriority` as `StrEnum` | ✔ |
| `Notificacion` / `Inbox` models | ✔ |
| Classifier covers every `NotificacionKind` | ✔ |
| `UNCLASSIFIED → (OTRO, HIGH)` rigorously tested | ✔ |
| `InboxFetcher` composes source + persistence | ✔ |
| `next_appeal_deadline` helper | ✔ |
| CLI subcommands wired under `aeat inbox` | ✔ |
| Settings + env + alignment test green | ✔ |
| Unit tests colocated; live test opt-in | ✔ |
| No mocks/patches/fakes — real Protocol-conforming doubles | ✔ |
| Errors inherit from `AeatError` | ✔ |
| Logging via `aeat.core.logging.get_logger` | ✔ |
| Protocol stubs for #43, #8, #45 (no hard imports) | ✔ |
| `just lint && just typecheck && just test && just hooks` green | ✔ |

## notes for reviewer

- The inbox is **read-only** against AEAT (ADR D1). `aeat inbox ack`
  is local state only — the CLI echoes this fact on every ack.
- Calendar-day arithmetic is conservative (ADR D8). Business-day
  precision will land with #45 normatives.
- The file-backed `_FileBackedNotificacionSource` is a rebase-swap
  stub. Once #43 lands, replace it with a `StatusReader` adapter in
  `_helpers.build_fetcher()`; no other touch-point needed.
- The live test (`src/aeat/inbox/test_live_inbox.py`) imports
  `aeat.status` lazily and skips if it is not present. If it **is**
  present, it surfaces the #41 `playwright_stealth` bug verbatim
  (does not paper over it).
