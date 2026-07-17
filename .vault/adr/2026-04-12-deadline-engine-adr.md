---
tags:
  - "#adr"
  - "#deadline-engine"
date: '2026-04-12'
modified: '2026-07-17'
title: Filing-Deadline Computation Engine
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-deadline-engine-plan]]"
issue: wgergely/aeat#38
---

# architecture decision record: filing-deadline computation engine | (**status:** `accepted`)

## context

`aeat#38` introduces the project's first user-visible "answer-the-user"
output: given an autónomo profile and a target year, produce the typed
schedule of filings the autónomo is obliged to submit, with concrete
opens/closes/payment dates and a current `ObligationStatus`. The engine
is read-only — it never touches the storage layer, never files, never
mutates the catalogue/corpus/manuals.

The engine consumes the canonical modelo catalogue, registry-backed deadline
windows, and profile applicability facts through their public package
contracts. It does not carry local substitute catalogues or dormant resolver
paths.

## decision

1. **Single subpackage: `src/cadrumo/domain/deadlines/`.** Public API is
   exported from `cadrumo.domain.deadlines.__init__`. Internal modules are
   `_`-prefixed (`_models.py`, `_engine.py`, `_protocols.py`,
   `_errors.py`, `_calendar.py`, `_applies.py`). External callers
   import only from `cadrumo.domain.deadlines`.

2. **Pydantic v2 strict everywhere.** Every boundary-crossing type —
   `AutonomoProfile`, `FilingObligation`, `Schedule` — is a strict
   frozen pydantic v2 `BaseModel` with
   `model_config = ConfigDict(strict=True, frozen=True,
   extra="forbid")`. Closed enumerations (`IVARegime`,
   `ObligationStatus`) are `enum.StrEnum`. No dataclasses for any
   boundary-crossing type. No bare `dict[str, Any]` in any public
   signature or persisted payload.

3. **Pure-function engine.** `DeadlineEngine.compute(profile, year, *,
   today=None) -> Schedule` performs **no I/O** after construction.
   The engine reads its authoritative catalogue and deadline data through
   typed public contracts; the `compute` call performs no external writes.
   Inputs are never mutated. The same `(profile, year,
   today)` always produces an equal `Schedule` (modulo
   `generated_at`).

4. **Citation-grounded `applies_to`.** Every applicability rule lives
   in `_applies.py` as a pure function with the BOE / Manual práctico
   citation in the docstring. The truth tables are sourced from the
   research note (`[[2026-04-12-deadline-engine-research]]`), not
   invented.

5. **Calendar in code, not config.** The v1 engine carries a small
   in-code `_calendar.py` table mapping
   `(modelo, year, period_kind) -> CanonicalWindow`. Year-specific
   overrides from #17 corpus are honoured via the corpus Protocol when
   present, but the calendar table is the v1 source of truth so the
   engine is useful before #17 lands.

6. **Status thresholds.** `OVERDUE`, `DUE_TODAY`, `DUE_SOON`,
   `UPCOMING`. `DUE_SOON` defaults to a 14-day window driven by
   `AEAT_DEADLINE_DUE_SOON_DAYS`. `FILED` and `NOT_APPLICABLE` are
   never produced by the engine in v1; they are reserved for
   downstream consumers (#10 storage, #11 sync runner).

7. **Errors inherit from `cadrumo.core.errors.CadrumoError`.** The hierarchy is
   `DeadlineError → ProfileError | ScheduleComputationError`. No
   stdlib exceptions cross the public API.

8. **Logging.** Only `cadrumo.core.logging.get_logger(__name__)`. The engine
   logs at DEBUG only — it must not be chatty when called from the
   CLI or from `#11` sync.

9. **CLI surface.** A new typer sub-app `aeat deadlines` mounted on
   the existing root `aeat` CLI. Subcommands: `list`, `next`, `explain`.
   The CLI is pure glue: it parses arguments, resolves the canonical
   authorities, and calls `DeadlineEngine`.

10. **Settings.** Two additive fields in `cadrumo.core.config.Settings`:
    `aeat_default_profile_path: Path | None` and
    `aeat_deadline_due_soon_days: int = 14`. Both documented in
    `env/.env.example`; alignment enforced by `tests/test_config.py`.

## non-goals

- Persisting the `Schedule` to the storage layer — owned by #10.
- Filing anything (read-only engine).
- Notifications / alerts.
- Web UI.
- Parallel local copies of modelo, corpus, or manual authority.
- Modelos outside the autónomo set listed in the research note.
- Estimación objetiva (modelo 131) — not a v1 path.

## integration with #11 sync

The self-healing sync runner (#11) eventually calls
`DeadlineEngine.compute(profile, current_year)` to know which
`(modelo, period)` pairs to look for on AEAT. The runner stays
unchanged in v1; the integration is a future commit gated on this
issue landing and on `#11` being on `main`.

## consequences

- The engine is consumable through the canonical public catalogue and
  registry contracts. There is no bundled substitute authority.
- The in-code calendar table will need a yearly maintenance commit
  until #17 corpus carries the override stream. That commit is small
  and obvious — every entry has a citation.
