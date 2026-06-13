---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: W02.P04.S10,W03.P05.S19,W03.P06.S27,W04.P07.S29
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# Calendar Censo Reconciliation Warning

## Scope

This execution slice hardens the overview calendar when obligations are derived
from profile facts that have not been reconciled against live AEAT Modelo 036 /
censo evidence. It does not close the censo-positive live rows because AEAT G313
again returned no readable censo for the authenticated live profile.

## Implementation

- `build_overview_calendar` now accepts
  `live_censo_verified_profile_keys`. When supplied, active Modelo obligations
  whose applicability cannot be tied to any censo-stamped enrolment path receive
  a blocking `CalendarWarning` with code `censo.enrolment_unverified`.
- `app overview calendar` passes censo-stamped `UserProfileFact.source` paths
  from the active encrypted profile, and the `--all-profiles` branch applies the
  same logic per profile.
- `config profile censo apply` passes the same censo provenance into its
  post-apply calendar summary so the censo enrolment surface and overview
  surface agree.
- The warning fix command is `aeat config profile censo pull && aeat config
  profile censo apply`.
- Calendar strict mode now refuses unresolved profile checks with wording that
  covers both defaulted profile fields and unverified censo enrolment.
- The censo CLI sub-app is decorated with the shared CLI error boundary before
  mounting, so direct `profile_app` tests and root CLI behavior both surface
  typed refusals instead of INTERNAL errors.
- `AeatAccessGate` now treats a loaded pytest module as test execution when the
  explicit `pytest_current_test` seam is not supplied. This covers Click runner
  isolation hiding `PYTEST_CURRENT_TEST` while preserving the explicit operator
  context seam.

## Live Evidence

Authenticated live status for the isolated Clave Movil profile remained ready
and authenticated.

`config profile censo pull` reached AEAT and refused:

- `AEAT sede G313 returned no readable censo for profile <profile-id>; confirm
  your certificate or Clave is registered against this NIF.`

Because no readable censo snapshot exists, the positive censo apply/reconcile
proof remains blocked.

`app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`
returned a live-profile calendar with:

- entries for modelos `100`, `303`, `390`, and `721`,
- an AEAT notification projected as a `message` event,
- every active filing obligation carrying `justificante_required=true` and
  `justificante_verified=false`,
- warning `censo.enrolment_unverified` affecting modelos `100`, `303`, `390`,
  and `721`.

Strict calendar mode refused with:

- `Calendar has unresolved profile checks: censo.enrolment_unverified. Run the
  warning fix command or pass --allow-incomplete to inspect the provisional
  calendar.`

Filed-history live spot check remained pull-only:

- `app live filed list --modelo 303 --from-year 2026 --to-year 2026` returned
  `row_count=0`, `failed_count=0`.

The command drift guard remained intact:

- source search for `pull-all|pull_all` only found guard tests,
- `app live filed pull-all --help` refused with `No such command 'pull-all'. Did
  you mean 'pull'?`.

## RAG Discovery

Required `vaultspec-rag search` was attempted again with a high timeout:

- `.venv\Scripts\vaultspec-rag.exe search --timeout 3600 "calendar censo live Modelo 036 reconciliation warning profile derived obligaciones AEAT justificante"`

The command timed out after 604 seconds. Earlier `uv run vaultspec-rag search`
attempts also timed out or were blocked by the local editable-script lock. This
execution therefore uses direct code discovery plus the recorded RAG timeout as
a tooling blocker.

## Verification

Used `.venv\Scripts\python.exe` / `.venv\Scripts\aeat.exe` directly after `uv`
became blocked on a locked editable `aeat.exe` script.

- `python -m ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/tests/test_override.py src/aeat/entrypoints/cli/_config/_profile_censo.py` passed.
- `python -m ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed earlier in the slice.
- `python -m pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/core/access_gate/tests/test_override.py -q` passed: 32 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/overview/tests src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_overview_explain_verb.py -q` passed: 189 passed.

## Open Rows

- `W02.P04.S10` remains open: live censo/Modelo 036 did not return readable
  facts, so profile reconciliation could not be positively proven.
- `W03.P05.S19` remains open for authenticated censo-fact-driven obligations,
  although local CLI behavior and post-apply projection are now covered.
- `W03.P06.S27` remains open for censo-backed projection but has positive
  notification-to-calendar projection and explicit censo-unverified warning
  behavior.
- `W04.P07.S29` is partially satisfied by the focused gates above, but broader
  live/backend sweep gates remain open.
