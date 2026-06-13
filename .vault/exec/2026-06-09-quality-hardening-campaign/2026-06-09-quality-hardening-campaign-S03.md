---
step_id: S03
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S03: QHC-003 cognitive-complexity burn-down, slice 2

## Outcome

Cleared four cognitive hotspots below threshold 20 via behaviour-preserving
helper extraction, each paired with focused real-behaviour tests. The live
worst-first inventory dropped from **17** to **13** functions over the cognitive
threshold of 20.

Live inventory at start (regenerated with `uv run --no-sync python -m
dev.audit.complexity`, full output to disk): 254 cyclomatic grade C+, 8
maintainability < A, 17 cognitive > 20. The audit's QHC-016/QHC-017 prose was
stale: `_workbook_export.py::_apply_styling` (flagged peer-WIP-locked in
QHC-017) was clean at HEAD and clearable.

## Functions cleared (worst-first)

| Function | Before | After | Commit |
|----------|--------|-------|--------|
| `application/storage/calc_sheets/_workbook_export.py::_apply_styling` | 27 | < 20 | `6ec53306d` |
| `domain/calculations/registry/_remote_state_guard.py::RemoteStateGuardPolicy._validate_policy` | 27 | < 20 | `fc0c7eba3` |
| `domain/calculations/registry/_validate_semantic_role_typos.py::_semantic_role_looks_like_typo` | 27 | < 20 | `b3b37ffec` |
| `adapters/outbound/aeat/sede/_declarations.py::_capture_filed_declaration_observation_from_row` | 26 | < 20 | `2f7c9e7dc` |

No extracted helper exceeds the ~12 helper budget; none appears on the
grade-C+ or cognitive over-threshold lists after extraction.

## Per-function detail

### `_apply_styling` (27 -> below)

Six independent styling phases (base font, styled ranges, column widths, frozen
views, auto filters, print setup) extracted into `_apply_base_font`,
`_apply_styled_ranges`, `_apply_column_widths`, `_apply_frozen_views`,
`_apply_auto_filters`, `_apply_print_setup`. Phase order preserved exactly:
base font first (later styled overrides win), then widths/freezes/filters, then
print setup. Each helper takes a precise typed facet sequence
(`Sequence[SheetStyledRange]`, etc.); the four facet records were added to the
`_records` import. The `family` resolution (`plan.font_family or
WORKBOOK_FONT_FAMILY`) stays in the orchestrator and is threaded to the two
font helpers.

Tests: added `test_offline_workbook_applies_print_setup_to_every_tab` to
`test_modelo_export_styling.py` — the print-setup phase was the only previously
uncovered phase. It asserts landscape, fit-to-one-page-width, fitToPage, and the
repeat-header defined name against a real serialized M130 workbook. The expected
`print_title_rows` value (`$1:$1`, openpyxl's absolute on-save normalisation)
was derived from the actual serialized form, not hand-asserted. All 58
calc_sheets tests green.

### `RemoteStateGuardPolicy._validate_policy` (27 -> below)

Fourteen classification/evidence-tier/auth/synthetic-data validation
predicates split into four cohesive static methods by axis:
`_validate_evidence_tier`, `_validate_allowed_hosts_presence`,
`_validate_authentication_consistency`, `_validate_synthetic_data_consistency`.
Every `RegistryValidationError` message preserved verbatim. The only ordering
change (public-read synthetic check vs authenticated-read auth check) is
behaviour-equivalent: the two predicates are keyed on mutually-exclusive
classifications, so no input can match both and the within-classification order
is unchanged.

Tests: added five focused message-locking tests
(`test_public_read_surface_synthetic_data_message_is_classification_specific`,
`test_authenticated_read_surface_requires_authentication_message`,
`test_forbidden_stateful_surface_rejects_synthetic_data`,
`test_open_simulator_must_not_require_authentication`,
`test_live_policy_must_declare_allowed_hosts`) pinning the classification-keyed
message contract across the phase split. All 40 guard tests + 44 consumer tests
(live-parity, authenticated-simulator) green.

### `_semantic_role_looks_like_typo` (27 -> below)

The expensive length-bucketed near-match scan extracted into
`_scan_length_buckets_for_typo_twin`, and the inner per-candidate filter chain
(identity skip, fast O(N) prefix/suffix check, unique-character-set filter,
SequenceMatcher ratio, tax-domain + axis sibling exemptions) into
`_candidate_is_typo_twin`. The cheap-to-expensive ordering and early-exit
semantics preserved exactly; the trailing two sibling checks collapsed per
SIM103 (`return not semantic_roles_are_axis_siblings(...)`) — behaviour-
identical because the tax-domain check still short-circuits first.

Tests: added `TestSemanticRoleTypoTwinHelpers` (5 tests) exercising the
extracted helpers directly at the boundary — identity skip, single-char
substitution twin, axis-sibling exemption (which faithfully observes that the
fast-check budget rejects ascendiente/descendiente before the sibling
exemption is reached), and the bucket scan's positive/negative paths. All 42
semantic-role tests green.

### `_capture_filed_declaration_observation_from_row` (26 -> below)

The deeply-nested submitted-file extraction-coverage block (the dominant
complexity driver: a `try resolve_export_layout / parse / coverage` ladder
with an M303 special case) extracted as a pure helper
`_submitted_file_coverage_for_casillas(snapshot, body, casillas) -> float` in
`_declarations_observations.py`, alongside its peer leaf helpers. The helper
absorbs the M303 "no exports" -> 1.0 case and the xml_dictionary / page-03
fallback short-circuits; the live capture routine retains its outer
`except (RegistryValidationError, SedeParseError)` that records
`metadata["submitted_file_extraction_error"]`. Promoted to the observations
module's `__all__` (a top-level surface for that package) so the consumer
imports it through the package boundary. Removed five now-unused imports from
`_declarations.py` (`Modelo`, `bundled_path`, `parse_export_payload`,
`resolve_export_layout`, `_is_modelo_303_page_03_fallback`,
`_submitted_file_extraction_coverage`).

Tests: added
`test_submitted_file_coverage_scores_fully_extracted_modelo_130_filing` to
`test_declarations_part2.py`. It derives the expected coverage independently by
re-parsing the export layout (not by hand-computing a formula) and asserts the
composed helper agrees, confirming the M130 redacted submitted file scores 1.0.
All 51 declaration tests green.

## Skips

- `adapters/persistence/storage/sql/_secure_object_migration.py::ensure_deterministic_object_keys`
  (26, the current over-threshold leader). **SKIPPED per the slice brief's
  special-caution clause:** it touches secure-storage key derivation where
  byte-identical key computation is the invariant. Extracting helpers risks
  perturbing the deterministic `object_key` HMAC computation, and I could not
  prove byte-identity with a roundtrip/equality test against real repository
  rows within this slice's scope. Left for a dedicated slice with a
  roundtrip-proof harness rather than risked.

## Verification gate

- Focused tests green per function (58 / 40+44 / 42 / 51).
- `uv run --no-sync ruff check` clean on all eight touched files (one SIM103 and
  three import-order auto-fixes applied).
- Scoped complexity re-run after each commit: each cleared function absent from
  the over-threshold list; live count 17 -> 16 -> 15 -> 14 -> 13.
- Core-struct docstring link gate: the 2 failures observed
  (`test_modules_that_use_a_core_struct_link_it`,
  `test_public_functions_link_anchor_parameters`) are in 6 peer-WIP modules
  (`_cross_period_clean_state`, `overview`, `registry`, modelo, cli config/work
  — all in the uncommitted working tree from concurrent campaigns), NOT in any
  file this slice touched. The sede `_declarations.py` docstring still
  cross-links its core structs (`RegistrySnapshot`, `ModeloRevision`,
  `CasillaObservation`, `ValidatedRegistryAuthority`).

## Commits

- `6ec53306d` refactor(qhc-003): extract helpers from _apply_styling (cognitive 27->below)
- `fc0c7eba3` refactor(qhc-003): extract helpers from RemoteStateGuardPolicy._validate_policy (cognitive 27->below)
- `b3b37ffec` refactor(qhc-003): extract helpers from _semantic_role_looks_like_typo (cognitive 27->below)
- `2f7c9e7dc` refactor(qhc-003): extract _submitted_file_coverage_for_casillas from _capture_filed_declaration_observation_from_row (cognitive 26->below)
