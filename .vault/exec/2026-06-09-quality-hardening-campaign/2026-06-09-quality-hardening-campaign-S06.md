---
step_id: S06
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S06: QHC-003 cognitive-complexity slice 3

## Outcome

Four functions cleared from the live cognitive-complexity over-threshold list
(threshold 20), worst-first. The live inventory was regenerated before and after
via `python -m dev.audit.complexity`: the over-threshold cognitive count dropped
from **12 to 8**. Every extraction is strictly behaviour-preserving (same
outputs, same error types / `translated_message` keys, same control-flow
ordering, same event/finding emission); each is paired against the existing
real-behaviour test surface (registry-authority fixtures, real-corpus PDFs — no
mocks/stubs/monkeypatch). One function (`_resume_from_storage_state_locked`,
cognitive 25) was deliberately **skipped**: it lives on the AEAT auth
storage-state resume path (a security/session-restore surface), which the slice
mandate excludes absent a byte-identity proof harness.

## Live inventory at start (cognitive > 20, worst-first)

```
31  application/calculations/_binding_prefill.py::_gather_observations
25  adapters/inbound/declaracion/_parser.py::_extract_profile_values
25  adapters/outbound/aeat/auth/_authenticator.py::...::_resume_from_storage_state_locked  (SKIPPED — auth/storage-state)
25  application/modelo/_m210_rate.py::resolve_m210_rate
25  application/modelo/_profile_binding.py::resolve_profile_sourced_bindings
24  application/modelo/_result_summary.py::calculation_result_summary
24  domain/calculations/registry/_applicability.py::ModeloApplicabilityRule::evaluate
24  entrypoints/cli/_errors.py::command_error_boundary
24  entrypoints/cli/_overview.py::overview_calendar
23  application/workflow/_resume.py::resolve_modelo_workflow_resume_target
22  domain/transactions/_llm.py::parse_response
21  domain/contribuyente/_descendant_facts.py::descendant_list_from_facts
```

## Function 1 — `_gather_observations` (cognitive 31 -> 5), commit `050d36171`

`src/aeat/application/calculations/_binding_prefill.py`. The previous-filing
binding walk carried two interleaved branches in one body: the
`per_grupo_member` cross-member fan-in (353<-322 aggregation) and the
single-key load with secure Modelo 303 IVA-history merge. Extracted:

- `_gather_grouped_member_observations(req_key, *, repository, needed, seen_member)`
  — the fan-in branch; mutates the shared `needed` / `seen_member` accumulators
  in place to preserve member-index sequencing (object identity preserved).
- `_gathered_from_payload(payload)` — the R2 carry gate for a single-key payload
  (divergent stamp -> `None`; missing/indeterminate -> advisory set).
- `_gather_single_key_observation(...)` — single-key load + Modelo 303 IVA
  history merge.

Helpers ≤7 cognitive. The 390 fan-in and the 303 IVA-history merge are both
exercised by existing tests (`test_modelo_390_prefill_compares_annual_totals...`,
`test_modelo_303_local_iva_recurrence_preserves_filed_history_source_kind`).
6/6 `test_binding_prefill.py` green; full `calculations/tests/` 295 passed.

## Function 2 — `_extract_profile_values` (cognitive 25 -> 7), commit `fc1e884b4`

`src/aeat/adapters/inbound/declaracion/_parser.py`. Extracted the per-target
hit-resolution-and-classification arm and the failure-raise tail:

- `_TargetClassification` (frozen slotted dataclass) — one target's outcome:
  exactly one of `value` / `missing` / `malformed` / `ambiguous`.
- `_classify_target(target, *, pages, pages_words)` — resolves one target's hits
  into that tagged outcome (bbox-without-words -> missing, no hits -> missing,
  multiple -> ambiguous, unparseable amount -> malformed, else the
  `ExtractedCasilla`).
- `_raise_extraction_failed(profile, *, missing, malformed, ambiguous, coverage)`
  — the degraded-extraction `DeclaracionParseError` with identical
  `translated_message`, context, and typed tuples.

Helpers ≤8 cognitive. Covered by real-corpus extraction round-trips and the
coverage-failure case (`test_parser_fails_when_registry_profile_targets_are_missing`).
27/27 `test_parser_boundary_part2.py` green; 75 parser-boundary tests passed.

## Function 3 — `resolve_m210_rate` (cognitive 25 -> 8), commit `6442afa95`

`src/aeat/application/modelo/_m210_rate.py`. Extracted the baseline lookup, the
Convenio (treaty) override branch, and the shared finding builder:

- `_m210_blocking_finding(...)` — the BLOCKING_RULE finding builder, deduping the
  three near-identical `ModeloVerificationFinding` constructions (kind/severity
  shared).
- `_resolve_baseline_rate(baseline_param, tipo_renta, year) -> (rate, ok)` —
  `ok` is False only on an arithmetic/parse failure of a matched bracket (caller
  then short-circuits to `(None, [])`, identical to the original).
- `_resolve_convenio_rate(convenio_param, *, country_code, tipo_renta, year)` —
  the entire treaty branch including the `m210-convenio-rate-missing` and
  `m210-convenio-rate-not-yet-authored` BLOCKING findings.

Helpers ≤12 cognitive (`_resolve_convenio_rate` exactly 12). All five branches
(GB match, MA override + anti-tautology mutation, AR NOT_YET_AUTHORED, ZW
missing, resident deferred) covered by real registry-authority tests.
17/17 `test_modelo_210_convenio_rate_resolution.py` green.

## Function 4 — `resolve_profile_sourced_bindings` (cognitive 25 -> 10), commit `0d11d24ae`

`src/aeat/application/modelo/_profile_binding.py`. Extracted the per-binding
three-channel routing (date / enum / decimal) with its two validation raises:

- `_ResolvedBindingChannels` (slotted dataclass) — mutable accumulator holding
  the three channel dicts; object identity preserved across the loop.
- `_route_resolved_binding(binding_id, value, *, is_date_channel, is_enum_channel, channels)`
  — routes one already-non-None fact into its channel, raising
  `date_value_type_invalid` for a non-date date-channel fact and
  `enum_boolean_invalid` for a bool enum-channel fact (identical
  `translated_message` keys and context).

The `value is None` skip was hoisted into the caller loop ahead of routing —
behaviour-identical, since the original skipped None in every one of the three
branches. The `dataclasses.field` import is aliased `dataclass_field` to avoid
collision with the pre-existing `for field in section.fields` loop variable in
`_profile_fact_index`. Helpers ≤10 cognitive (the pre-existing
`_inject_derived_family_facts` at 16 was not touched). All three channels plus
both raise paths covered. 44 tests across `test_profile_binding.py`,
`test_profile_binding_real_path.py`, `test_borrador_binding.py` green.

## Verification gate

- Live re-run after slice: `python -m dev.audit.complexity` reports cognitive
  over-threshold **8** (down from 12); all four targets absent from the list.
  Per-function `complexipy` confirms each refactored function < 20 and every new
  helper ≤12.
- `uv run --no-sync ruff check <file>` clean on every modified module before its
  commit.
- Focused real-behaviour tests green per function (6 + 75 + 17 + 44).
- Core-struct docstring links truthful on all four modules (the two failing
  docstring-gate entries — `overview._calendar`, registry
  `_validate_orden_aplicabilidad` — are pre-existing, in files this slice did not
  touch; reported as out-of-scope below).

## Skips / out-of-scope

- `_resume_from_storage_state_locked` (cognitive 25) — SKIPPED: AEAT auth
  storage-state resume path; security/session-restore surface excluded by the
  slice mandate without a byte-identity proof harness.
- `test_docstring_core_struct_links` shows 2 pre-existing failures in
  `aeat.application.overview._calendar::calendar_filing_evidence_from_sources` and
  `aeat.domain.calculations.registry._validate_orden_aplicabilidad::orden_aplicabilidad_hard_failures`.
  Neither file is touched by this slice and neither carries my local edits;
  out-of-scope (different campaign / peer surface).

## Commits

- `050d36171` refactor(qhc-003): extract helpers from _gather_observations (cognitive 31->5)
- `fc1e884b4` refactor(qhc-003): extract helpers from _extract_profile_values (cognitive 25->7)
- `6442afa95` refactor(qhc-003): extract helpers from resolve_m210_rate (cognitive 25->8)
- `0d11d24ae` refactor(qhc-003): extract helpers from resolve_profile_sourced_bindings (cognitive 25->10)
