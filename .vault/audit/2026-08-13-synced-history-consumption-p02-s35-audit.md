---
tags:
  - '#audit'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b6c9ed8267cff956f04bd2c6ac31ec33c79bba672bdee4687ca3f8ed3ffd090c'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# `synced-history-consumption` audit: `p02 s35`

## Scope

Fresh-context review of the uncommitted P02.S35 legal-catalogue additions,
Modelo 353 construct and dependency classification, focused registry test,
and the S35 plan and execution artefacts. The review read the governing plan,
ADR and research, inspected the diff from `HEAD`, confirmed the cited LIVA
provisions against the bundled BOE corpus and live BOE consolidated text, and
checked the loaded-registry closure path for duplicate classification authority.

Focused evidence: `ruff check` for `test_modelo_353_registry.py` passed;
that test file passed 11 tests; and `aeat app registry verify` passed with 73
modelos and 94 revisions. The adjacent Modelo 353 continuity and carry-taxonomy
suite was then run as the integration check named by the S35 execution record.
Final re-review reran Ruff on both focused test files, the continuity and
Modelo 353 registry suite (14 passed), the cross-modelo carry-taxonomy suite
(8 passed), and `aeat app registry verify` successfully.

## Findings

### p02-s35-exec-frontmatter | high | Resolved during review

The initial P02.S35 execution record omitted the closing YAML delimiter after
`related`, so `vault check all` parsed its entire body as frontmatter and reported
four frontmatter errors plus an illegal body wiki-link. The executor corrected
the delimiter at line 12 during this review. Re-inspection confirms the closing
delimiter is present; this finding is retained because the step had been marked
complete before its closure record was valid.

### p02-s35-continuity-fixture | high | Resolved during review

The focused command recorded in the execution record,
`pytest -q -n0 test_modelo_353_grupo_aggregation_continuity.py test_cross_modelo_carry_taxonomy.py`,
produced three failures and eight passes. Each failure begins at
`test_modelo_353_grupo_aggregation_continuity.py:116`, where the fixture creates
an `IvaLedgerObservation` without the exact deduction authority newly required by
that real input model. The failure occurs before Modelo 322 carry resolution, so
it neither disproves the classification nor proves its live aggregation path.
The taxonomy portion passed. The execution record accurately records the failure,
but the passing classification test is insufficient to close the integration
evidence while this focused suite remains red. The executor subsequently added
the required `DOMESTIC_CURRENT` invoice-evidence provenance only to the
SOPORTADO fixture rows. The re-run of the continuity suite plus the Modelo 353
registry test passed all 14 tests, so the real model precondition remains strict
and the integration evidence is now green.

### p02-s35-canonical-classification | low | No duplicate authority found

The legal entries have one canonical home in `iva.toml`; all three resolve to
anchored bundled BOE corpus text. Live BOE cross-check confirms the same group
subject, regime-condition and aggregated-self-assessment propositions. The one
Modelo 322 classification is owned by the one Modelo 353 aggregate construct,
and the existing validator requires that it cover all three direct
`previous_filing` bindings and their inherited grounding. This is the intended
single classification rather than duplicated per-binding treatment or a shim.

## Recommendations

Retain the corrected execution frontmatter and the narrowly grounded fixture
provenance. The re-run now passes, so no open S35 finding remains. Keep the
classification and legal entries as the sole authority unless a later change
exposes a genuine source-modelo or construct-coverage defect.
