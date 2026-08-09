---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8228f73dfcee0bbf35e5e1a94ff40b6b80c3274b702f7af9d4a550b8d4ea1cd5'
step_id: 'S22'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Ground and fix the silent tax-id/regime default: an absent profile yields NIF 00000000T and regime GENERAL across CLI surfaces instead of refusing or flagging the gap, per the per-operation-axis audit's finding two

## Scope

- `src/cadrumo/application/user_profile/_projections.py`

## Description

- Re-read the governing audit (`.vault/audit/2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit.md`) in full before touching any code, per this project's mandate that a finding's "still-a-gap" conclusion must be recomputed at report time, not trusted from when it was written. The audit document itself records that a concurrent session already investigated and closed this exact finding after this Step was opened: an exhaustive sweep of all twelve real `_profile_to_taxpayer`/`projection_for_taxpayer` call sites (not the originally-miscounted fourteen) classified 5 as structurally guarded by `_FILING_BASELINE_PROFILE_PATHS` (the placeholder can never reach a persisted/exported artefact), 3 as genuinely harmful and fixed, 4 as not identity-bearing, and 1 as withdrawn after a three-way probe showed the claimed consequence did not reproduce.
- Verified the three fix claims live against current `HEAD`, not by trusting the audit's prose: `_modelo_records_cli.py:275` reads `_declared_tax_id(...)` (not the fabricated projection) before building `expected_tax_id`; `_overview.py:330` does the same for the calendar evidence matchers; `_ledger_support.py`'s `_resolve_source_jurisdiction` returns `None` (not a hardcoded `"ES"`) for an undeclared `fiscal_residency`, matching the impatriado aggregation's documented never-silently-coerced-to-ES invariant.
- Confirmed the export path specifically - the one surface where a fabricated NIF reaching a filed artefact would have been a live regulatory hazard - is guarded structurally: `identity.tax_id` is a member of `_FILING_BASELINE_PROFILE_PATHS`, so `require_profile_ready_for_work_unit` refuses an undeclared identity on the DECLARED record before export's header build ever runs.
- `projection_for_taxpayer`'s `tax_id_default`/`iva_regime_default` parameters themselves were deliberately left unchanged: they exist so the calendar/deadline-schedule computation (which needs a stable `TaxpayerProfile` shape to determine which modelos apply, independent of the NIF string's content) can run for an incomplete profile without raising, while every site that treats the tax_id as meaningful IDENTITY (matching against external evidence) now reads the declared value through `_declared_tax_id` or an equivalent instead.

## Outcome

No code change in this Step. This finding was already fixed by the concurrent session's own investigation and commits before this Step ran; verification here is the confirmation that those fixes are present and correct in the current tree, not a re-implementation.

## Verification

Direct inspection of the current tree (not a git-history check, per this session's standing instruction to leave git entirely alone):

- `Grep "expected_tax_id|_declared_tax_id" src/cadrumo/entrypoints/cli/_modelo_records_cli.py` -> line 275 reads `_declared_tax_id(...)`.
- `Grep "_declared_tax_id|expected_tax_id" src/cadrumo/entrypoints/cli/_overview.py` -> line 330 reads `_declared_tax_id(record)`.
- `Read src/cadrumo/entrypoints/cli/_ledger_support.py:244-273` -> `_resolve_source_jurisdiction` returns `None` for `fiscal_residency is None` (line 272), never `"ES"`.

These three sites are exactly the three the audit's outcome section names as fixed, confirmed present against the live file content rather than re-derived from the audit's own prose.

## Notes

The plan Step's original scope (`_projections.py`) named the DECLARATION site of the defaults, but the audit's own investigation - re-verified here - found the correct remediation was at the CONSUMPTION sites (each call site choosing whether to read the declared value or the fabricated projection), not at the declaration, because the projection's fabricated defaults are legitimately needed by non-identity-bearing consumers (calendar status/agenda/backlog/explain, deadline scheduling). Narrowing `tax_id_default`/`iva_regime_default` to non-defaulting at the projection layer, as the audit's ORIGINAL (pre-investigation) remediation proposed, would have broken those legitimate consumers; the investigation correctly superseded that proposal with the consumption-site fix actually shipped.
