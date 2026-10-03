# Work creation, form editing, and inventory

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-085` · **Topic:** [Modelo work and revision lifecycle, part 2: verification, workbench and workspace](../topics/modelo-work-and-revision-lifecycle-part-2.md)

<!-- preserved:article -->
**Scope:** 19 files under `src/cadrumo/application/modelo`, totaling 4,581 lines, 196,475 bytes, and 42,935 measured proxy tokens. All eight bounded-reader pages were read in order. This is static analysis only; the application was not run and no tests were executed. The token count is the manifest's `o200k_base` proxy.

## Capabilities and mechanisms

The work-create operation creates or resumes a Modelo work unit for one exact profile and filing period. Before writing, it loads the profile, applies foral-region and registry-derived applicability checks, requires the existing profile baseline and target revision to be ready, validates the law-selected revision, and parses the optional causante CCAA. A permitted `allow_not_applicable` bypass is carried explicitly into the result rather than hidden. Four ceded regional-tax model codes (600, 620, 650 and 660) receive jurisdiction-specific redirection; the policy avoids maintaining a broad hard-coded list of all AEAT capabilities. Create preparation and effect handling (`src/cadrumo/application/modelo/work_create_operation.py`), applicability and regional-tax policy (`src/cadrumo/application/modelo/work_create_policy.py`), result and terminal-receipt correlation (`src/cadrumo/application/modelo/work_create_operation.py`)

The create request is profile-bound and period-scoped. Applicability refusals are the only detailed refusal released through the public projector, and the projector verifies their terminal refusal code, detail reference and `NONE` effect. Success reports whether a unit was reused or updated, any applied rename, applicability bypass and M100 filing-obligation advisories. Preparation can refuse without changing state; before the ensure/create path the effect becomes `UNKNOWN`, then settles to `UPDATED` for a new unit or rename and `NONE` for an unchanged reuse. The operation supports CLI and TUI, is recorded and cooperative/idempotent, and awaits cancellation through its irreversible section.

The work form is the canonical editor view built from a work review, the pinned registry revision's declared layout, the calculation head, the current edit admission and the requested language. Every casilla must appear once on a declared page, as a working figure, or in an explicitly unplaced list; a duplicated, undefined or omitted field is refused. If the layout is absent or belongs to another registry revision, the fallback is a read-only inspection form ordered by printed box. Form assembly and layout totality (`src/cadrumo/application/modelo/work_form.py`), inspection fallback (`src/cadrumo/application/modelo/work_form_inspection.py`)

Each field carries a semantic casilla/binding address, value, localized label and help, source, origin, editability, required status, formula/binding provenance, constraints, legal references and blockers. Origins distinguish entered, imported, calculated, needed, cleared, not applicable, failed calculation, optional empty and default-to-confirm. The form claims a manual entry only when the current revision's operator layer records it; a held required or nonzero value with no such record is unattributed and asks for confirmation, while an optional zero remains empty. Binding-source policy and edit admission determine whether the filer types directly, overrides a source, corrects the profile, or has no edit. An override to a bound casilla is addressed to its feeding binding. Field projection (`src/cadrumo/application/modelo/work_form_field_projection.py`), origin and editability rules (`src/cadrumo/application/modelo/work_form_field_state.py`), form field contract (`src/cadrumo/application/modelo/work_form_models.py`)

Layout rendering supports pages and conditional applicability, sections, grids, repeating records, binding inputs, aliases and design constants. Page conditions return unknown when available data cannot decide. Repeating data comes only from saved calculation channels and declared export-record relationships; missing legacy channels or unsupported records remain unknown, while an explicitly saved empty detail family can be known-empty. Row indices are preserved, and the reader does not query sources or recalculate. Design-fixed values and printed rates are only shown where their exported decimal scale is declared; grounded rates require exactly one rate-specific ledger binding, and zero literals mean placeholders. The form does not infer a rate from neighboring rows or treat a printed rate as proof of the calculation's applied rate. Repeating-record projection (`src/cadrumo/application/modelo/work_form_records.py`), layout and design constants (`src/cadrumo/application/modelo/work_form_layout.py`), rate grounding and declared scale (`src/cadrumo/application/modelo/work_form_rates.py`)

Source display identifies a binding's family and names earlier filings only when a supported provider and temporal anchor identify them. If a calculation actually replayed an imported AEAT draft, that snapshot takes precedence as the displayed source. Labels disclose when language falls back to Spanish, quotes an official Spanish heading, or remains technical; unnamed boxes are described without exposing their identifier as a human label. Earlier-filing and AEAT source derivation (`src/cadrumo/application/modelo/work_form_sources.py`), localization disclosure (`src/cadrumo/application/modelo/work_form_localization.py`)

The loaded form adds the canonical deadline window, holiday-coverage status, replayed AEAT import time, latest export and recorded filing status. If territory-specific holidays or a holiday calendar are unavailable, the deadline retains a coverage marker instead of being presented as fully final. Filing means Cadrumo recorded a filing transition; the model explicitly says that this did not send anything to AEAT. Filed declarations close to editing and require a correction workflow. Settlement direction comes from declared official result-disposition rules, not the sign alone; role-only results remain direction-unknown, missing operands remain unknown, and a carry/refund election is called out where applicable. Form-change reporting compares field value and origin by semantic address and lists added or removed fields. Form loader, deadline and export facts (`src/cadrumo/application/modelo/work_form_service.py`), filing and settlement states (`src/cadrumo/application/modelo/work_form_models.py`), settlement derivation (`src/cadrumo/application/modelo/work_form_result.py`), form-change projection (`src/cadrumo/application/modelo/work_form_service.py`)

Verification findings and calculation notes are presented as filer actions. Blocking findings sort first; the form maps them to attention levels and localized action keys, suppresses a calculation note when verification already reports the same cause, and avoids repeating a missing-input note after the current check has classified it. Finding actions and attention (`src/cadrumo/application/modelo/work_form_models.py`), note/finding de-duplication (`src/cadrumo/application/modelo/work_form_notes.py`)

The work inventory operation returns profile-bound work metadata without calculation values. Operators may include discarded units; otherwise the projection rejects any non-draft row. Reads are recorded, nonmutating and encrypted in result custody. Inventory discovery requires whole-profile consent, unlike the period-scoped create operation. Inventory projection and executor (`src/cadrumo/application/modelo/work_inventory_operation.py`), whole-profile access policy (`src/cadrumo/application/modelo/work_inventory_operation.py`)

## Knowledge, safety, and implementation assessment

The form's knowledge is assembled from registry schemas/layouts, review results, revision and operator-layer provenance, declared export mappings, saved detail rows, verification reports, profile admission, AEAT draft snapshots, event history and deadline calendars. It labels generated versus reviewed layouts and exposes uncertainty rather than silently filling it. It does not independently certify that generated layouts, translations, calculations or legal references match current official material.

The strongest local safeguards are exact-profile/period binding, declared revision and applicability checks, explicit operation effects, terminal-receipt/result correlation, total layout accounting, source-based edit policy, persisted-entry provenance, unknown-versus-zero row handling, and hard closure for filed work. A conditional point for synthesis is the create-policy helper: if profile projection raises validation error, that helper returns no applicability refusal and relies on downstream readiness gates to reject unusable profile data. Verify that every create path enforces those gates before writing. Work-form projections contain taxpayer amounts, identifiers, filing status and dates; caller authorization and frontend handling remain outside this chunk. No assigned test files were present, so calculation effects, layout behavior, rate inference, and correction closure were not exercised.

## Dependencies and follow-up

Synthesis should connect creation to work lifecycle persistence and operation admission; form inputs to edit admission and source-policy definitions; repeating rows to calculation persistence and filing replay; and deadlines to the canonical holiday resolver. Confirm malformed-profile behavior at the complete create boundary, that recorded filing always disables write admissions, and that result projections stay protected in CLI/TUI callers. Check the event store used for latest-export display and how stale exports are surfaced to the operator.

## Complete assigned-file coverage

All 19 assigned source files were read completely through pages 1–8.

- work_create_operation.py (`src/cadrumo/application/modelo/work_create_operation.py`)
- work_create_policy.py (`src/cadrumo/application/modelo/work_create_policy.py`)
- work_form.py (`src/cadrumo/application/modelo/work_form.py`)
- work_form_context.py (`src/cadrumo/application/modelo/work_form_context.py`)
- work_form_counts.py (`src/cadrumo/application/modelo/work_form_counts.py`)
- work_form_errors.py (`src/cadrumo/application/modelo/work_form_errors.py`)
- work_form_field_projection.py (`src/cadrumo/application/modelo/work_form_field_projection.py`)
- work_form_field_state.py (`src/cadrumo/application/modelo/work_form_field_state.py`)
- work_form_inspection.py (`src/cadrumo/application/modelo/work_form_inspection.py`)
- work_form_layout.py (`src/cadrumo/application/modelo/work_form_layout.py`)
- work_form_localization.py (`src/cadrumo/application/modelo/work_form_localization.py`)
- work_form_models.py (`src/cadrumo/application/modelo/work_form_models.py`)
- work_form_notes.py (`src/cadrumo/application/modelo/work_form_notes.py`)
- work_form_rates.py (`src/cadrumo/application/modelo/work_form_rates.py`)
- work_form_records.py (`src/cadrumo/application/modelo/work_form_records.py`)
- work_form_result.py (`src/cadrumo/application/modelo/work_form_result.py`)
- work_form_service.py (`src/cadrumo/application/modelo/work_form_service.py`)
- work_form_sources.py (`src/cadrumo/application/modelo/work_form_sources.py`)
- work_inventory_operation.py (`src/cadrumo/application/modelo/work_inventory_operation.py`)
<!-- /preserved:article -->
