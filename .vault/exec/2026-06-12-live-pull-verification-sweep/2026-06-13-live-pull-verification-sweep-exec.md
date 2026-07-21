---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W02.P04.S14 / W03.P06.S27 justificante capture calendar enrolment

## Scope

Connected direct live justificante captures to the overview calendar and filing
evidence projection without changing the meaning of a local Modelo filing
record. A local `ModeloRecord` still means the in-app calculation was marked
ready to file. A verified live justificante capture can now show the separate
AEAT axis: the period was actually submitted at AEAT and has parsed
justificante metadata.

RAG discovery was rerun with:

- `uv run vaultspec-rag search --timeout 180 "direct justificante capture calendar filing evidence snapshot no local ModeloRecord verified receipt"`

## Implementation

`src/aeat/application/live/_justificante.py` now exposes
`register_capture_justificante_metadata`. It parses the persisted capture PDF,
requires the parsed CSV to match the captured CSV, requires the parsed
modelo/year/typed Period axis to match the snapshot, and saves the
`JustificanteRepository` metadata. It does not stamp or create a local filing
record.

`capture_justificante_snapshot_outcome` now registers that metadata immediately
after persisting the authenticated snapshot and before the best-effort local
filing-record stamp. The old stamp semantics remain: no local filing record
means no local filing evidence is stamped and the outcome still reports
`filing_evidence_stamped=False`.

`src/aeat/application/overview/_calendar.py` now projects verified live
justificante captures into calendar events and filing evidence rows. Projection
requires an active capture snapshot plus matching persisted Justificante
metadata by CSV/model/year/typed Period/taxpayer. The resulting row carries
`local_filing_state=not_ready_to_file` unless a separate local Modelo record is
also present, while the AEAT side is
`aeat_submission_state=justificante_verified`.

`src/aeat/entrypoints/cli/_overview.py` now loads
`JustificanteCaptureSnapshotService` and `JustificanteRepository` for calendar
event and filing-evidence aggregation. This keeps `aeat app overview calendar`
local-only while letting prior authenticated pulls appear in the calendar.

## Verification

Static and focused behavior gates run:

- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/__init__.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short` reported 56 passed.
- `uv run pytest -m "" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q --tb=short` reported 20 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short` reported 120 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short` reported 2 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q --tb=short` reported 4 passed.
- `uv run pytest -m "" src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py -q --tb=short` reported 13 passed.
- `uv run aeat app live filed --help` showed `list`, `pull`, and
  `pull-sources`; no `pull-all`.
- `uv run aeat app live justificante --help` showed `pull`, `list`, and
  `view`.
- `uv run aeat app overview calendar --help` confirmed the overview calendar
  remains local-only.
- `rg -n "pull-all|pull_all|pull all|Pull all|capture-all|capture_all" src/aeat/entrypoints/cli src/aeat/application/live src/aeat/application/overview` found only tests that assert forbidden aliases stay absent.

## Live status

The authenticated runner remains blocked before fresh live proof. The latest
state in `var/aeat/live-auth-run/live-auth-20260613-ready-auth.log` is:
`runner initialized; waiting for operator passphrase`.

Earlier entries in the same log show the current AEAT Clave path reaching the
representation gate and refusing because the own-name continuation was not
available. No successful fresh live censo pull, filed-history pull,
justificante pull, notification pull, expediente pull, or live-backed calendar
render was captured in this slice.

## Carry Forward

Keep `W02.P04.S10` through `W02.P04.S16`, `W03.P05.S18` through
`W03.P05.S24`, `W03.P06.S26`, `W04.P07.S28`, `W04.P07.S30`, and the final
closeout rows open until a real authenticated operator run completes. The
implementation is locally verified, but live AEAT verification is not complete.

## Continuation: explicit metadata enrolment contract

Follow-up hardening separated three facts in the live justificante pull outcome
and CLI payload:

- the authenticated snapshot was persisted;
- parsed Justificante metadata was enrolled and can feed calendar evidence;
- a local ModeloRecord was or was not stamped.

`JustificanteCaptureOutcome` now exposes
`justificante_metadata_registered` independently from
`filing_evidence_stamped`. The CLI payload for `aeat app live justificante pull`
now carries `justificante_metadata_registered`, `calendar_evidence_available`,
and `modelo_filing_record_required`. Text output mirrors those fields and, when
no local ModeloRecord was stamped, prints the import command shape:
`aeat app modelo filing-record import WORK_UNIT_ID --evidence-kind aeat_live_capture --evidence-id CSV --set CASILLA=VALUE`.

This keeps the clean-state invariant intact. A direct receipt capture can make
the AEAT submission visible in the calendar, but it cannot unlock cross-period
calculation dependencies until a full external baseline import provides the
submitted casilla values and a current ModeloRecord.

Additional verification:

- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `uv run pytest -m "" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q --tb=short` reported 24 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short` reported 94 passed.
- `uv run aeat app modelo filing-record import --help` confirmed the import command path and options exist.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py -q --tb=short` reported 148 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_pull_help_locale_keys_do_not_use_capture_all_names -q --tb=short` reported 4 passed.

Live status remains unchanged: the runner log still ends at
`runner initialized; waiting for operator passphrase`; no fresh live AEAT proof
was captured in this continuation.
