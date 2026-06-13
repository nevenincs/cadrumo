---
tags:
  - "#plan"
  - "#notifications-inbox"
date: 2026-04-12
modified: '2026-04-12'
title: AEAT notifications inbox — plan
related:
  - "[[2026-04-12-notifications-inbox-research]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
issue: wgergely/aeat#46
---

# plan: aeat notifications inbox

Derived from `[[2026-04-12-notifications-inbox-research]]` and
`[[2026-04-12-notifications-inbox-adr]]`. Target:
`feature/46-notifications-inbox`.

## phase-1: schema, errors, protocol stubs

- `src/aeat/inbox/__init__.py` — package docstring, public re-exports.
- `src/aeat/inbox/_errors.py` — `InboxError`, `InboxFetchError`,
  `InboxAcknowledgeError` under `aeat.core.errors.AeatError`.
- `src/aeat/inbox/_models.py` — strict+frozen pydantic v2:
  `NotificacionKind(StrEnum)`, `NotificacionPriority(StrEnum)`,
  `Notificacion(BaseModel)`, `Inbox(BaseModel)` (wraps
  `dict[str, Notificacion]` with unique-id validation).
- `src/aeat/inbox/_protocols.py` — `RawNotificacion` pydantic model
  (the shape #43 returns) and `NotificacionSource` runtime-checkable
  Protocol with `async fetch_notificaciones(*, since) -> tuple[RawNotificacion, ...]`.

## phase-2: classifier, fetcher, deadline math

- `src/aeat/inbox/_classifier.py` — `_RULES` ordered tuple, `_APPEAL_WINDOWS`
  table, `classify(raw) -> tuple[NotificacionKind, NotificacionPriority]`,
  `appeal_window_for(kind) -> timedelta | None`.
- `src/aeat/inbox/_fetcher.py` — `InboxFetcher` constructs from a
  `NotificacionSource`, a `Path` for the PDF dir, and a `Path` for
  the inbox file. Methods:
  - `async fetch_new(*, since)` — pulls from source, classifies,
    downloads PDFs (if the source provides them — #43 stubs can
    return paths directly), computes `appeal_deadline` from
    `effective_at + appeal_window_for(kind)`, persists to inbox file,
    returns the tuple of new notifications.
  - `async acknowledge(notificacion_id, *, by)` — mutates the record,
    persists, returns the updated notification.
  - `load_inbox() -> Inbox` / `save_inbox(inbox)` helpers.
- `src/aeat/inbox/_deadline.py` — `next_appeal_deadline(inbox, *, today)`
  returns the earliest `CRITICAL`/`HIGH` notification with a
  non-None, non-past deadline, or `None`. Also the helper used by
  `aeat inbox next-deadline`.

## phase-3: settings + env

- Add `aeat_inbox_dir: Path`, `aeat_inbox_pdf_dir: Path`,
  `aeat_inbox_alert_lead_days: int` to `src/aeat/config.py`.
- Add matching entries to `env/.env.example` under a new
  `# -- Notifications inbox (#46) --` section.
- `tests/test_config.py` already drives the alignment check.

## phase-4: cli

- `src/aeat/entrypoints/cli/inbox/` — typer sub-app.
  - `__init__.py` wires 5 commands: `fetch`, `list`, `show`, `ack`,
    `next-deadline`.
  - `_helpers.py` constructs an `InboxFetcher` with a concrete
    `_CliNotificacionSource` — v1 reads from a JSON file the user
    points at via `AEAT_INBOX_DIR / "source.json"` (real file-backed
    source, not a mock). Rebase swaps this for the real #43
    `StatusReader` adapter.
  - `fetch.py`, `list.py`, `show.py`, `ack.py`, `next_deadline.py`.
- Wire into `src/aeat/entrypoints/cli/__init__.py` as
  `app.add_typer(inbox_module.app, name="inbox", ...)`.

## phase-5: tests

Colocated under `src/aeat/inbox/`:

- `test_models.py` — schema round-trip, `Inbox` unique-id check,
  strict validation rejections.
- `test_classifier.py` — every rule against real-shaped fixture
  payloads, `UNCLASSIFIED → (OTRO, HIGH)` rigorously parameterized.
- `test_deadline.py` — appeal-window math per kind; `next_appeal_deadline`
  picks earliest, ignores ack'd, ignores past, respects alert lead.
- `test_fetcher.py` — concrete `NotificacionSource` double (real
  class, no mocks); fetch → classify → persist → reload;
  acknowledge round-trip.
- `test_live_inbox.py` — `@pytest.mark.live`, skipped by default;
  opt-in via `AEAT_LIVE_TESTS_ENABLED=1`. Single fetch + ack
  round-trip against the real #43 status reader when it lands.
  Until then, imports `aeat.status` lazily and skips with a clear
  reason if the module is not present. Flags the #41 stealth bug
  explicitly if raised.
- `src/aeat/entrypoints/cli/inbox/test_cli.py` — typer runner drives each
  subcommand against a deterministic temp inbox dir.

## phase-6: vault exec records + code review

- `.vault/exec/2026-04-12-notifications-inbox/` — one step record
  per phase + a phase summary.
- vaultspec-code-review skill run over the full changeset.

## plan review

**Outcome:** APPROVED. Self-review against the ADR checks every
non-goal is respected, every D-decision has a step that implements
it, and there are no cross-module hard imports from in-flight
branches. The plan matches the acceptance criteria in wgergely/aeat#46
1:1.

- Public API discipline: every consumer imports from `aeat.inbox`.  ✔
- Pydantic v2 strict everywhere.                                    ✔
- Classifier covers every `NotificacionKind`.                       ✔
- `UNCLASSIFIED → HIGH` rule tested exhaustively.                   ✔
- Protocol stubs for #43, #8, #45 (no hard imports).                ✔
- CLI wired through chore/4's typer surface.                        ✔
- Settings + env + `tests/test_config.py` alignment.                ✔
- Unit + opt-in live tests, no mocks.                               ✔
- Errors inherit from `AeatError`.                                  ✔
- Logging via `aeat.core.logging.get_logger(__name__)`.                  ✔

Proceeding to execute.
