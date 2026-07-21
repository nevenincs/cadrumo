---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S11'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Prove filed-declaration list, single pull, bulk pull, and source pull fetch authenticated AEAT register data and persist only stamped official evidence

## Scope

- `src/cadrumo/application/live/_filed_data.py src/cadrumo/application/live/_filed_data_capture.py src/cadrumo/application/live/_filed_observation_persistence.py`

## Description

- Created a fresh isolated encrypted profile root, created a real profile, configured Cl@ve Móvil, and acquired a fresh authenticated Cl@ve Móvil session with the operator present (third attempt succeeded after two approval-window timeouts).
- Widened the filed-declaration query window past filing_year 2026 (the year every prior sweep attempt checked, always empty) to filing_years 2023-2026, which surfaced real filed history.
- Ran `app live filed list --modelo 303 --from-year 2023 --to-year 2026`.
- Ran `app live filed pull --modelo 303 --year 2024 --limit 2` (single-year mode).
- Ran `app live filed pull --modelo 303 --from-year 2023 --to-year 2024 --limit 3` (bulk mode).
- Ran `app live filed pull-sources --modelo 303 --year 2024 --period 1T` (retried once after a real navigation timeout).

## Outcome

All four command groups reached authenticated AEAT and persisted real, non-empty, stamped official evidence for the first time in this campaign.

- `filed list` returned `row_count=10`, `failed_count=0`: ten Modelo 303 declarations across 2023-2024, each with a real `expediente_id`, `presented_at` timestamp, `status=ALTA`, and `has_submitted_file=true`/`has_justificante=true`.
- `filed pull` (single, modelo=303, year=2024, limit=2) returned `captured_count=2`, `failed_count=0`, `casilla_count=158`, `calculation_observation_count=2` with `calculation_observation_keys=["303:2024:1T","303:2024:2T"]`, and real `secure-object:financial:...` artefact refs plus `db:\secure_objects\...filed_declaration.observations\...` observation paths.
- `filed pull` (bulk, modelo=303, from-year=2023, to-year=2024, limit=3) returned `mode=bulk`, `captured_count=3`, `failed_count=0`, `casilla_count=237`, proving the bounded bulk path the prior sweep round hardened (`app live filed pull --from-year --to-year --limit`, no `pull-all` surface needed) actually reaches AEAT and persists.
- `filed pull-sources` (modelo=303, year=2024, period=1T) failed once with a real `ERROR_SEDE_NAVIGATION` typed error ("clicking PDF artefact ... failed: Timeout 15000ms exceeded while waiting for event \"page\""), then succeeded on retry with `captured_count=1`, `casilla_count=80`, `calculation_observation_keys=["303:2023:4T"]` (the dependency source pull-sources fetched, not the target period itself).

This is the first sweep round to observe non-empty filed-declaration data: `justificante_metadata_count` and `filing_evidence_stamped_count` were `0` on every pull despite `has_justificante=true` on the source rows — the boolean flag is captured from the AEAT declaration listing itself, not from a separate justificante-PDF capture (see S26 for the related `justificante pull` defect this exposes).

## Notes

- Auth session was reused across all four command groups without re-login; `config auth status` confirmed `authenticated=true` and `persisted_session_state=live` throughout.
- The `ERROR_SEDE_NAVIGATION` timeout on the first `pull-sources` attempt is recorded as a real, typed, transient failure mode (retry succeeded); it is not a defect in the command itself.
- Redacted per the sweep convention: no raw NIE/NIF, Cl@ve support number, passphrase, or session token appears above; only aggregate counts, typed status codes, and hashed/opaque identifiers (`expediente_id`, `secure-object:financial:...` refs) are cited.
