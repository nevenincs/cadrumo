---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S306
plan: "[[2026-05-26-cross-domain-continuity-plan]]"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W02.P11.S306 — --all-profiles flag on aeat app overview calendar

## What was done

Added `--all-profiles` boolean flag to `aeat app overview calendar`.

### Implementation

`src/aeat/entrypoints/cli/_overview.py`:

- New `all_profiles: bool` parameter with `--all-profiles` Typer option.
  Help text served via `tr("cli.overview.calendar.all_profiles_help")`.
- When set, delegates to `_overview_calendar_all_profiles(ctx, ...)`.
- `_overview_calendar_all_profiles`: iterates every active bucket from
  `list_profile_buckets()`, opens each with `profile_storage_session`,
  loads the bucket's `WorkflowState`, and calls `build_overview_calendar`
  once per profile. Unreadable buckets emit a `profile_skipped` line and
  continue rather than aborting the scan.
- Output structured with a leading `profile\t{bucket_id}\t{label}` line
  per profile so callers can distinguish entries. JSON payload wraps
  per-profile calendars as `{"profiles": [...]}`.
- When not set: existing single-profile path is unchanged.

### Locale

New key `cli.overview.calendar.all_profiles_help` scaffolded via
`python -m aeat.locales scaffold` and prose filled in all four locales
(es, en, ca, hu). Redundant key
`application.user_profile.errors.duplicate_tax_id_scan_unreadable_profile`
(orphaned from S305 locale work) cleaned by scaffold at the same time.
`python -m aeat.locales audit` passes with zero drift.

### Regression test

`src/aeat/entrypoints/cli/test_overview_calendar_verb.py` —
`test_all_profiles_flag_iterates_every_registered_profile`:

- Registers two profiles ("operator" from the autouse fixture and "Second
  Operator" created inside the test).
- Invokes `--all-profiles --allow-incomplete --from 2026-01-01 --to
  2026-03-31`.
- Asserts exit code 0, both profile labels appear in the output, and
  exactly two `profile\t` header lines are present.

## Gate results

- `pytest test_overview_calendar_verb.py`: 6 passed
- `ruff check` + `ruff format --check`: clean
- `python -m aeat.locales audit`: ca/en/es/hu all ok
