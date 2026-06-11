---
tags:
  - '#audit'
  - '#calendar-filing-semantics'
date: '2026-06-05'
related:
  - '[[2026-06-05-calendar-filing-semantics-reference]]'
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` Code Review

## CALENDAR-FILING-001 | HIGH | Calculation observations are promoted to justificante-verified without justificante proof

`src/aeat/application/overview/__init__.py` maps every calculation observation whose `source_kind` is `aeat_sede_justificante` to `aeat_submission_state=JUSTIFICANTE_VERIFIED` and `justificante_verified=True`. That source kind is not a sufficient proof of a verified justificante PDF. `src/aeat/application/live/__init__.py` persists all captured filed-declaration observations through `persist_filed_calculation_observation` with that same source kind, and the filed-declaration registry conversion in `src/aeat/adapters/outbound/aeat/sede/_declarations.py` explicitly rejects casillas sourced from `justificante_pdf`; the promoted calculation observation can therefore be backed by `submitted_file` or declaration-PDF extraction rather than justificante verification. The existing filed-capture tests also construct persisted calculation observations with only a `submitted_file` artefact.

This collapses the reference's required distinction between AEAT-side submitted evidence and stricter justificante verification. A calendar entry can show `aeat=justificante_verified` and `justificante=true` for an observation that proves AEAT filed-data capture, but not that a justificante PDF was imported or verified. The fix should carry explicit artefact/evidence provenance into calculation observations, or avoid treating calculation observations as justificante-verified unless the stored metadata proves `justificante_pdf`. Add a regression where an `aeat_sede_justificante` calculation observation derived from `submitted_file` remains AEAT-observed but not justificante-verified.

Resolution 2026-06-05: fixed. Calculation observations now project only to `submitted_observed` with `justificante_verified=False`. The calendar additionally reads encrypted filed-declaration observations and promotes to `justificante_verified` only when a matching stored `justificante_pdf` artefact is present. Regression coverage was added for non-verifying calculation observations, stored justificante promotion, storageless justificante non-promotion, and filing-event promotion.

## CALENDAR-FILING-002 | HIGH | `--all-profiles` reads calculation observations from the ambient active profile

`src/aeat/entrypoints/cli/_overview.py` passes `bucket_id` to `ModeloRecordCatalogueRepository`, but constructs `CalculationObservationRepository()` without the loop bucket. In single-profile mode the ambient active bucket normally matches the requested bucket, but in `_overview_calendar_all_profiles` the temporary `profile_storage_session(bucket_id)` is used only while loading the profile record; after that context exits, `_local_calendar_filing_evidence(bucket_id, events)` reads calculation observations from the process active profile, not necessarily from the profile currently being rendered.

Because the evidence merge key is only `(modelo, filing_year, period)`, an active profile's persisted calculation observation can be attached to another profile's calendar row whenever those three values match. That is both a semantic error and a cross-profile privacy leak in the local-only storage path. Construct `CalculationObservationRepository(bucket_id=bucket_id)` or keep all per-profile evidence reads inside the profile storage session. Add a two-profile CLI regression where only one bucket has a persisted calculation observation and `--all-profiles` does not show that evidence under the other profile.

Resolution 2026-06-05: fixed. The all-profiles loop now builds profile values, taxpayer projection, live events, filed-declaration evidence, and calculation-observation evidence inside the target `profile_storage_session(bucket_id)`. A storage-backed two-profile regression proves evidence remains scoped to the owning profile.

## CALENDAR-FILING-003 | MEDIUM | Regression tests miss the storage and negative-evidence paths that carry the highest risk

The new application tests use real domain records and are useful for the local-record and expedientes-event merge behavior, and the CLI test uses real local live snapshot services. However, no test persists a `CalculationObservationRepository` row and verifies how it appears in `overview calendar`, no test covers the `--all-profiles` bucket-scoping path for filing evidence, and no test proves that non-justificante AEAT filed-data observations stay separate from `justificante_verified`.

This leaves the two highest-risk semantics unguarded: bucket-scoped local-only reads and the distinction between AEAT filed-data capture and justificante verification. Add focused real-behavior tests using the existing secure profile storage fixtures and repository APIs rather than monkeypatching command helpers.

Resolution 2026-06-05: fixed. Focused tests now cover the calculation-observation negative path, filed-declaration justificante positive/negative paths, event promotion, and real secure-storage profile scoping through repository APIs.

## CALENDAR-FILING-004 | HIGH | Stored justificante projection accepts dangling manifest references as verification

`src/aeat/application/overview/__init__.py` promotes a filed-declaration observation to `JUSTIFICANTE_VERIFIED` when an artefact has `kind == "justificante_pdf"`, a truthy `storage_ref`, and `byte_count > 0`. That checks the observation manifest only; it does not prove that the referenced justificante artefact is present in the encrypted artefact namespace, loadable through `FiledDeclaracionObservationStore.load_artefact`, or consistent with the artefact metadata. `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` also persists and lists observation manifests independently from artefact bodies, and `FiledDeclaracionArtefact.storage_ref` is only a bounded string field. A valid but dangling `secure-object:financial:...` reference can therefore become `justificante_verified=True`.

The current regression `test_filed_declaration_observation_with_stored_justificante_marks_verified` demonstrates this gap because it creates an in-memory artefact with a synthetic `secure-object:financial:` reference and no stored body, yet expects verification. The calendar semantics require justificante verification to come from an explicit stored `justificante_pdf` artefact, not from manifest metadata alone. The fix should make the projection receive store-verified artefact provenance, or make the store listing validate the referenced artefact exists and matches the recorded `sha256`/`byte_count` before calendar evidence can become `JUSTIFICANTE_VERIFIED`.

Resolution 2026-06-05: fixed. The CLI calendar storage loader now validates `justificante_pdf` artefacts by loading the encrypted artefact body and checking both byte count and SHA-256 before passing the observation into calendar evidence projection. Unreadable or mismatched justificante artefact refs are stripped from the observation copy, which leaves the filing at `submitted_observed` rather than `justificante_verified`. A secure-storage regression persists one valid justificante artefact and one dangling manifest ref and proves only the loadable artefact verifies.

## CALENDAR-FILING-005 | MEDIUM | Calendar JSON contract does not schema-bound the new filing evidence fields

`src/aeat/entrypoints/cli/_overview_payloads.py` defines `OverviewCalendarEntryPayload` and `OverviewCalendarEventPayload`, including the new filing-evidence fields, but `OverviewCalendarResult` still declares `entries`, `events`, `warnings`, `suppressed_entries`, and `profiles` as `list[dict]` and allows extra fields. In `--all-profiles`, each profile embeds `"calendar": cal.model_dump(mode="json")` inside another raw dict. As a result the registered CLI schema does not validate `filing_evidence`, `aeat_submission_state`, `justificante_verified`, or nested all-profile calendar shapes.

This weakens the new calendar-filing contract: a future regression could omit, rename, or mistype the dual filing states while the JSON contract still accepts the payload. The fix should wire the existing nested payload models into `OverviewCalendarResult` and add typed profile-calendar payloads, or otherwise introduce bounded schemas for the polymorphic single-profile and all-profiles calendar result shapes.

Resolution 2026-06-05: fixed. `OverviewCalendarResult` now uses typed nested payloads for entries, events, warnings, suppressed rows, all-profile profile blocks, full nested calendars, completeness, ranges, and filing evidence. The all-profiles JSON command was rerun successfully after the schema tightening.

## CALENDAR-FILING-006 | HIGH | Modelo external evidence can verify calendar entries without persisted taxpayer-bound justificante metadata

`src/aeat/application/overview/_calendar.py` promoted `ModeloRecord.external_evidence.kind` values `aeat_justificante_pdf` and `aeat_live_capture` directly to `aeat_submission_state=JUSTIFICANTE_VERIFIED` with `justificante_verified=True`. That left a fail-open path after the cross-period clean-state work tightened import and filing gates: a legacy or dangling Modelo record could make the calendar claim justificante verification without resolving a secure persisted `Justificante` row, without matching the rendered taxpayer tax ID, and without matching the Modelo/year/period obligation.

This reintroduced the application-vs-real-world filing ambiguity the calendar is supposed to expose. A local record could still indicate an external baseline, and an AEAT accepted flag could still indicate observed acceptance, but justificante verification must require metadata that binds the CSV/reference to the taxpayer and period.

Resolution 2026-06-11: fixed. `calendar_filing_evidence_from_sources` now accepts already-loaded justificante metadata and an expected taxpayer tax ID. Modelo-record evidence only becomes `JUSTIFICANTE_VERIFIED` when `reference_id` resolves to a persisted justificante whose CSV, Modelo, ejercicio, period, and tax ID match the calendar obligation. The overview CLI loads `JustificanteRepository` inside the active profile storage session and passes the active or iterated profile tax ID for single-profile and `--all-profiles` calendars. Regression tests cover missing metadata, wrong-taxpayer metadata, wrong Modelo/year/period metadata, matching persisted metadata, and a storage-backed CLI aggregation path.

Verification 2026-06-11: `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed with 51 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed with 9 tests. `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.

## CALENDAR-FILING-007 | HIGH | Filed-declaration justificante evidence is not taxpayer-bound

`src/aeat/application/overview/_calendar.py` accepted a stored `justificante_pdf` artefact on any `FiledDeclaracionObservation` as `JUSTIFICANTE_VERIFIED` without checking that the observation's `authenticated_identity` matched the taxpayer whose calendar was being rendered. Because filed observations are merged by Modelo/year/period, a wrong-profile or mis-scoped persisted observation could attach AEAT submitted and justificante-verified evidence to another taxpayer's obligation row.

Resolution 2026-06-11: fixed. `calendar_filing_evidence_from_sources` now passes `expected_tax_id` into filed-declaration observation projection. When supplied, the projection refuses observations whose `authenticated_identity` differs from the rendered taxpayer. The overview CLI already supplies the expected tax ID for single-profile and `--all-profiles` calendar rendering. A regression proves a loadable justificante artefact for a different authenticated identity yields no calendar filing evidence.

Verification 2026-06-11: `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed with 52 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed with 9 tests. `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
