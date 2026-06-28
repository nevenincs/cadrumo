---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W03.P05.S18 / W02.P04.S10 live auth retry and bulk pull limit

## Scope

Retry the operator-mediated live read sequence against a fresh isolated
profile root, verify the current `pull`-only live surfaces, and harden the
filed-history bulk `pull --limit` path discovered during the live sweep.

## Description

- Created an isolated runtime root at `var/live-auth-20260613-operator-run2`
  with a process-only secure-store passphrase to exercise profile creation
  without relying on the shared default profile.
- Created profile `live-auth-20260613-run2`, configured Cl@ve Movil, and
  verified identity alignment before live login.
- Ran both non-QR and QR Cl@ve login attempts; both reached AEAT wait pages
  with verification-code evidence but timed out without an authenticated
  session.
- Recorded diagnostic IDs `20260613T113749Z`, `20260613T114031Z`, and
  `20260613T114920Z` with phone state `operator_did_not_check`.
- Ran bounded live read commands for censo, filed list, filed pull,
  expedientes, notifications, justificante, and calendar projection. Live
  read commands failed closed at auth except the local calendar projection,
  which rendered no AEAT events and no observed filings.
- Fixed `app live filed pull --from-year --to-year --limit` so the advertised
  bounded bulk acquisition path is valid under `pull` and no `pull-all`
  surface is needed.
- Tightened the live runner fallback timeout to `120000` ms so the script does
  not set a value rejected by settings validation when `.env` is absent.

## Outcome

Live AEAT authentication remains blocked by Cl@ve completion timeout. No live
Modelo 036/censo snapshot, filed history, justificante, notification,
expediente, or live-backed submitted calendar evidence was captured.

The local calendar failed honestly: it showed 19 locally derived obligation
entries, `events=0`, `censo_enrolment=unverified`, `aeat=not_observed`, and
the remediation warning `censo.enrolment_unverified` with fix command
`aeat config profile censo pull && aeat config profile censo apply`.

The CLI drift found during the live sweep is fixed: bulk filed acquisition can
now be bounded with `app live filed pull --from-year YEAR --to-year YEAR
--limit N`; the command reaches the auth gate instead of failing local
validation.

Verification:

- `uv run aeat config profile create live-auth-20260613-run2 ...` completed.
- `uv run aeat config auth configure --provider clave_movil` completed.
- `uv run aeat config auth status --provider clave_movil` reported configured,
  available, unauthenticated, identity alignment matches.
- `uv run aeat config auth login --provider clave_movil --fresh --reset-lock`
  timed out in non-QR mode with diagnostic `20260613T113749Z`.
- `AEAT_CLAVE_PREFER_NON_QR=false uv run aeat config auth login --provider
  clave_movil --fresh --reset-lock` timed out in QR mode with diagnostic
  `20260613T114031Z`.
- `uv run aeat app live filed pull --from-year 2025 --to-year 2026 --limit
  10` reached auth and timed out with diagnostic `20260613T114920Z`.
- `uv run ruff check src/aeat/application/live/_filed_data_capture.py
  src/aeat/entrypoints/cli/_app_live.py
  src/aeat/application/live/tests/test_filed_bulk_capture.py
  src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py
  -q --tb=short` passed with 6 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_bulk_pull_accepts_limit_without_pull_all
  src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all
  src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all
  src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases
  -q --tb=short` passed with 4 tests.
- `rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat/entrypoints
  src/aeat/application src/aeat/domain docs/how-to` found only negative guard
  tests.

## Notes

This record does not claim a successful live AEAT read. The remaining blocker
is operator-mediated Cl@ve completion after AEAT presents the verification
code/wait page.
