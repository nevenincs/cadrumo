---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:69c82f8542522cee517a8764cdf8a13c7d79fcf9d9f961057f4c861c7c0a9e54'
step_id: 'S83'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# repair the real M303-quarter-to-M390 end-to-end suite to law-select each live split M303 revision and make all four scenarios pass without restoring or tolerating the retired revision id

## Scope

- `src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py`

## Description

- Select every quarterly M303 work-unit revision through the validated registry authority using the filing year and typed period.
- Remove the retired `2023-y-siguientes` fixture token without an alias, fallback, or mirrored selector.
- Align the real export checks with the live revisions' filing-grade layout withdrawal and retain the local filing-to-M390 reconciliation path.
- Match the cross-period advisory assertion to the production relation origin code.

## Outcome

The implementation-time exact run passed all four real encrypted-SQLite end-to-end scenarios in 32.70 seconds. The suite exercises both 2024 split revisions (`2024-hasta-08-y-2t` and `2024-desde-09-y-3t`) and the 2025 revision through production law selection. Verification, local filing, observation persistence, M390 annual fold-in, and typed withdrawn-export refusals remain live-behaviour assertions.

At formal review time, the same exact module was blocked before reaching an S83 assertion because concurrent untracked legal-source catalogues still declared draft review status and strict registry loading refused them. This is a current shared-worktree verification boundary, not a passing rerun and not an S83 target defect. S83 does not tolerate or modify those peer-owned drafts.

The implementation-time `ruff format --check` and `ruff check` runs passed for the target, and `basedpyright` reported zero errors, warnings, or notes. The target contains no retired revision token.

## Notes

Formal review at 2026-08-12 re-ran the exact module serially and observed all four scenarios green in 32.20 seconds, so the review-time obstruction recorded above has cleared and the implementation-time result is confirmed at HEAD.

Scope narrowing, recorded per the campaign's scope-change protocol. The first scenario previously asserted a written fichero-BOE artefact (byte size, non-empty payload, the tax id present in the bytes) and now asserts a typed `ModeloExportUnsupportedError` refusal instead. The narrowing is truthful, not a workaround: an independent authority probe confirmed that every live M303 revision the suite law-selects carries an absent or empty `export_layouts` definition, so refusal is the only correct production behaviour available. What the standing goal still asks for that this excludes: an end-to-end proof that ledger input reaches real filing-grade fixed-width BYTES for M303. No scenario in this suite proves that today, and no other suite was substituted for it. That proof returns only when a filing-grade `export_layouts` definition is authored for a live M303 revision.

Why the narrowing is principled rather than a defect, established after the paragraph above was written and recorded here so the two facts are read together. Every Modelo 303 revision carries a support-removal decision withdrawing the fixed-width layout from filing grade, on the stated ground that its official record design contains producer fields with no canonical typed producer authority and that retaining a partial layout would permit silent under-declaration. The refusal the suite now asserts is therefore the correct behaviour rather than a tolerated one, and the withdrawal is a recorded judgement rather than lost data. Read alone, that fact reads comfortably. Read alone, so does the narrowing above. The truth is the pair: the withdrawal is principled AND nothing in the tree currently proves ledger input reaching real filing-grade fixed-width bytes for Modelo 303. Neither half may be cited without the other, and the typed producer authority whose absence forced the withdrawal is owned by a separate campaign, not by this one.

The cross-period advisory assertion was corrected from `app_filing` to `registry_relation` because the fact carries `requirement.origin.value`, the origin of the cross-period requirement, not the observation source kind. The prior value could never match, so the helper returned an empty set against an assertion demanding all four quarters. The non-official basis is still asserted directly through the persisted observation's `source_kind == "app_filing"`, and the advisory is only ever emitted on the `app_filing` admission branch, so the corrected assertion is strictly stronger than the one it replaced.

The repository-wide retired-revision structural gate remains red outside this Step's scope: ten occurrences remain across `test_modelo_303_deductible_evidence_gate.py`, `test_modelo_303_official_box_under_declaration.py`, `test_diff.py`, `test_modelo_180_round_trip.py`, and `test_modelo_reconcile_verb.py`. Those pre-existing or concurrent paths were not modified. That surface is carried forward as its own intake step under the P11 protocol rather than absorbed here, because widening this Step's scope silently is forbidden. No data loss or destructive Git operation occurred.
