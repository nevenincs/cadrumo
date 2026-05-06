---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` Code Review

Topic: adherence, code duplication, and testing parity across implemented
modelo registry definitions and registry-model tests.

Audit surface: `registry/aeat/modelos/*.toml`,
`registry/aeat/legal/*.toml`, `src/aeat/domain/calculations/registry`, and
`src/aeat/domain/calculations/registry/test_modelo_*_registry.py`.

Rewrite scope: audit record plus one terminology cleanup in a current registry
test; no schema, formula, or compatibility behaviour changes.

CTR-PARITY-001 | HIGH | Formula-bearing Modelos 111, 130, and 131 lack model-specific registry parity tests
 The TOML registry contains filing-grade casillas and formulas for Modelos 111,
 130, and 131, but there is no `test_modelo_111_registry.py`,
 `test_modelo_130_registry.py`, or `test_modelo_131_registry.py`. There is
 related application-level coverage for draft building, verification,
 reconciliation, deadlines, and workflows, but the current testing shape is not
 parity-equivalent to Modelos 115, 123, 180, 190, and 193. Add dedicated tests
 that load the real registry, validate the modelo, build snapshots, assert
 construct ownership, calculate representative formulas, check legal/source
 traces, and exercise negative paths where source inputs are required.

CTR-PARITY-002 | HIGH | Modelos 111, 130, and 131 still lack construct ownership in TOML
 The validator accepts these modelos, but their formula-bearing revisions have
 no `constructs` entries. This is inconsistent with the accepted parent-child
 ADR model now used by Modelos 115, 123, 180, 190, 193, 200, 232, 347, 349,
 720, and 840. Add construct rows that own casillas, formulas, parameters,
 export layouts, extraction profiles, live/static references, workbook refs,
 verification expectations, deadline windows, and application links.

CTR-PARITY-003 | MEDIUM | Annual relation tests for Modelos 190 and 193 lack fail-fast negative observation coverage
 Modelos 190 and 193 have real relation-resolution and calculation tests, but
 unlike Modelo 180 they do not yet prove missing or duplicate source-period
 observations fail hard. Add negative tests using real
 `RegistryFilingObservation` inputs and `RegistryValidationError` expectations
 so annual-summary dependencies have consistent failure semantics across
 180/190/193.

CTR-PARITY-004 | MEDIUM | Source/legal test signals are uneven across model-specific registry tests
 Modelos 115, 123, 180, 190, 193, 200, 202, 347, 349, and 840 rely primarily on
 model validation for source/legal closure, while Modelos 232 and 720 include
 stronger direct corpus/source checks. The validator passing is necessary, but
 test shape should be standardized so every model-specific registry test either
 has an explicit source/legal closure assertion or delegates to a shared
 generalized source/legal consistency test with per-model coverage.

CTR-PARITY-005 | MEDIUM | Informative/evidence modelos use inconsistent workflow-surface policy
 Informative or evidence-only modelos do not all declare the same workflow
 surfaces. Modelos 232 and 720 include review, approval, reconciliation, and
 workflow links, while Modelos 347, 349, and 840 currently have narrower
 surface sets. If a modelo is supported for filing-grade review/export/import,
 the application-link policy should be explicit and shared; if a surface is not
 legally or operationally supported, the TOML should carry an explicit reviewed
 support-removal decision rather than silent absence.

CTR-PARITY-006 | LOW | Uncommitted Modelo 202 registry text contains development-flow language
 The working tree currently contains `registry/aeat/modelos/202.toml` with a
 comment that refers to an implementation wave step. This is outside the
 committed surface audited here, but it violates the ADR direction against
 transient development metadata inside registry definitions. Remove the comment
 or rewrite it as durable source/legal rationale before the 202 slice is
 committed.

CTR-PARITY-007 | LOW | Historical revision terminology should avoid legacy framing
 A Modelo 123 test name used `legacy` for the 2019-2023 revision. That has been
 renamed to `historical_revision_calculates_prior_layout_totals` so the test
 describes official temporal variation rather than an old implementation state.

Verification:

- Registry validation over loaded modelos: passed for 100, 111, 115, 123, 130,
  131, 180, 190, 193, 200, 202, 232, 347, 349, 720, and 840.
- Focused model-registry pytest set: 95 passed in 174.31 seconds.
- Full `test_modelo_*_registry.py` batch including heavy Renta and uncommitted
  slices timed out at 244 seconds before completion; no failure was observed
  before timeout.
- Focused Modelo 123 cleanup checks passed with `ruff`, `ty`, and pytest.
