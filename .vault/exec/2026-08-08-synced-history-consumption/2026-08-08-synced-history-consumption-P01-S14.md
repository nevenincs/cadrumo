---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:1fd007f160146932177c95ac35c960b330a5713c7c4f03ac846a026b7dc7dd34'
step_id: 'S14'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Wire the no-AEAT-history notice and stop it misdirecting a Sociedades filer, which is what remains of this row after S21 closed its bound-casilla half. S21 made the absent bound carry loud with two registry-declared narrowings, so the silence half of the original scope is delivered and is deliberately not restated here. The suffered-retencion carries S21 excluded are correctly excluded and are NOT part of this row either, since telling a taxpayer their filing is missing is wrong advice when the payer files it. They have their own row. What is left is the surface. Measured by running the shipped CLI over a real isolated encrypted profile holding a Sociedades taxpayer and zero calculation observations, the overview status envelope emits four notices and the no-AEAT-history code is not among them, because the builder has NO production caller at all: it is defined in the overview evidence module, re-exported through the calendar module and the package facade, and referenced nowhere else in shipped code except its own test. So the notice reaches nobody today, and the history-onboarding row that added it is checked without its deliverable. Two things must both hold once it is wired. Its predicate returns None on the FIRST observation carrying an official AEAT source kind, so a single pulled row from any modelo silences it while a Sociedades history has still never arrived, which is the partial-reach case. And its suggestion names the whole-history sweep, which the capture planner diverts modelo 200 and 202 away from into typed unsupported rows, so for a Sociedades-only filer it recommends a verb that structurally cannot fetch what it names. Gate: the notice reaches an operator surface proven by running that surface rather than by reading a caller, it is not silenced by an unrelated pulled observation, it does not recommend a verb that cannot reach the data, and all four locale catalogues carry real values rather than the key-echo placeholder they hold today

## Scope

- `src/cadrumo/application/overview`
- `src/cadrumo/entrypoints/cli`

## Description

- Add a `tax_route: TaxRoute | None = None` keyword parameter to the
  application builder `no_aeat_history_notice`. A Sociedades filer
  (`TaxRoute.IMPUESTO_SOCIEDADES`) now returns a notice carrying no action
  and its own route-specific message, because the bulk filed-data capture
  planner structurally diverts Modelo 200 and 202 into typed unsupported
  rows, so the whole-history-sweep suggestion can never fetch what this
  taxpayer's own direct-tax obligation is. Every other route (including
  `None`, unknown) keeps today's suggestion unchanged.
- Add a shared CLI-layer projector, `overview_no_aeat_history_notice`, next
  to the sibling evidence loaders in the CLI's local-evidence module: reads
  persisted calculation observations, calls the application builder, and
  resolves the action through the live action resolver so its `cli_path`
  is populated the way every other envelope notice's action is. Degrades to
  no advisory on a read failure, matching every sibling loader.
- Wire that one projector into BOTH surfaces that previously diverged: the
  `overview status` envelope (the measured gap - it never called the
  builder at all) and the `config profile status` full-screen surface
  (already wired, now delegating to the same function instead of carrying
  its own duplicate read-and-resolve logic).
- Add a real locale key, `overview.no_aeat_history_sociedades`, with real
  translated values in all four catalogues via `dev.locales set` (the
  scaffold intentionally omits, never echoes, a key with no authored
  value yet).
- Add unit coverage for the new `tax_route` branch (every other route keeps
  the sweep suggestion; the Sociedades route carries no action; the
  predicate still silences on any official observation regardless of
  route; the Sociedades message is real, translated, and distinct from the
  generic one) and a new real-CLI integration test module driving the
  shipped CLI over three real isolated encrypted profiles: a natural
  person (keeps the sweep action), a Sociedades filer (no action), and a
  Sociedades filer with one pulled Modelo 303 observation (the notice is
  silenced too, proving the carve-out narrows the suggestion, never the
  predicate).

## Outcome

`aeat app overview status --format json` now carries the
`overview.no_aeat_history` notice for a workable profile with no
AEAT-confirmed observation - the row's own measured defect, reproduced and
closed. A Sociedades filer sees the notice with no action rather than a
verb that can never reach Modelo 200/202; every other taxpayer keeps the
whole-history-sweep suggestion unchanged. The full-screen `config profile
status` surface and the machine envelope now share one producer, so they
cannot diverge again.

Verification: the new unit tests (5 added, 12 total in the module) and the
existing wiring test (`test_status_notices_wiring.py`, 8 total across both
files) are green. The new real-CLI integration module
(`test_overview_status_no_aeat_history_notice.py`) drives the actual
shipped CLI end to end - real isolated encrypted profile, real registry,
real observation store, no mocks - and all 3 tests pass together (532s).
`ruff check`, `ruff format --check` and `ty check` are clean on every
touched file; `dev.quality.types`'s tree-wide summary (47 pre-existing
diagnostics, none in a touched file) is unchanged before and after.
`dev.locales audit` and `dev.locales scaffold --check` are clean across all
four catalogues.

The broader `application/overview/tests/` and
`entrypoints/cli/_config/tests/` suites were run for regression coverage.
Confirmed unrelated by `git diff` showing zero changes to the failing
files: `test_explain.py`/`_explain.py` (a peer's in-flight
`iva.roi_enrolled` work) and `test_agenda.py` (a deadline-schedule
partition duplicate, unrelated to notices); and
`test_status_indexed_fact_masking.py` (four failures on indexed-fact label
masking and a mojibake character - the diff against `_status_frontend.py`
touches only `build_active_profile_notices` / `_no_aeat_history_notice`,
never `_build_fact_rows` or masking). The pre-existing
`application/aggregation/tests/` failure set (5 failures, all IVA
deduction-authority and profile-binding fingerprint drift, unrelated to
overview) is unchanged from the count already recorded on the prior row.

## Notes

The row's own prose ("referenced nowhere else in shipped code except its
own test") was stale against HEAD: `_status_frontend.py` already called the
builder in production code for the `config profile status` TUI surface.
Re-read at HEAD, the substance of the row's gate held regardless - the
machine-facing `overview status` envelope, the surface the row's own
measurement names and the one an autonomous operator actually parses,
never called it. Wiring one shared function into both surfaces closes the
gap the row measured without contradicting or duplicating the TUI's
existing (correct) behaviour.

The Sociedades no-action design over recommending an alternate verb (e.g.
`live filed discover`): the discovery verb has no registered operator-action
catalogue entry, and fabricating one under-specified for this row's narrow
need would be scope creep against a narrow, well-grounded fix. No action is
honest; a wrong one is misdirection - which is exactly the defect this row
exists to close.
