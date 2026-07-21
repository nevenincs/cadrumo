---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S40'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# run the independent campaign-close honesty review (vaultspec-code-reviewer against the ADR, plan, and commit range), persist it as a vault audit, and track every surfaced item as a new Step with a verification gate (aeat-campaign-close-honesty-review)

## Scope

- `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`

## Description

- Re-read the cross-period prorrata ADR, the current L3 plan, the feature reference, the W06 deferral records, and the rolling campaign audit.
- Re-grounded the review through vault and code search, then confirmed the live source-mesh disposition, registry taxonomy carve-out, calculation advisory helpers, register carry code, and focused test surfaces.
- Reviewed the feature commit trail for the prorrata paths and compared the checked plan rows with their exec-record outcomes.
- Confirmed the W06 deferred axes are honestly tracked: especial per-input apportionment, sectores diferenciados, Art. 104.Tres special/exclusion treatment, and Art. 105.Cinco remain schema-backed follow-ups rather than claimed live behavior.
- Surfaced one open campaign-close finding: `W04.P07.S30` is checked but its exec record says the `PRORRATA_REGULARIZACION` source-mesh promotion was deferred due to non-authored `_source_mesh.py` WIP, and current code still lists the source kind in `DEFERRED_SOURCE_KIND_TARGETS`.
- Added `W06.P09.S41` with a verification gate to promote `PRORRATA_REGULARIZACION` once `_source_mesh.py` is owner-clean, including mesh enrollment, taxonomy-carve-out removal, mesh parity, AEAT manual oracle, and M303 prorrata advisory checks.

## Outcome

- S40 is complete as the independent honesty review step.
- The campaign is not honestly complete: `W06.P09.S41` remains open and is the next work item.
- No production code was edited by this review.

## Notes

- Verification passed: focused prorrata close-review test slice (48 passed).
- Verification passed: `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata`.
- Verification passed: `uv run --no-sync vaultspec-core vault check frontmatter --feature cross-period-prorrata`.
