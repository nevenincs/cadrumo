---
tags:
  - '#audit'
  - '#issue-604-m390-real-parse'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:4e66e968d9174f94b21da9ea6635d6f0e97b8abb95a79c8bad2fca1309ecd87d'
related: []
---

# `issue-604-m390-real-parse` audit: `M390 real declaration parsing implementation review`

## Scope

Fresh-context review of implementation commit `887362fa9f1015d4f8d2bf2b5eebdf2d86ca7a84`
against its parent and current branch HEAD. The audit covered the exact M390 2021
record-design applicability epoch, parser authority-grade selection, extraction-profile
casilla identity, existing reproduced-render expectations, filing-capability declarations,
and every non-M390 legal-source fingerprint restamp. Focused registry, parser-boundary,
capability-probe, source-grounding, verification-chain, and reproduced-render gates were
run. Production code was not modified.

## Findings

### reproduced-render-grade | high | The enrolled 2021 specimen breaks five focused parser coverage tests

`test_real_render_extraction_coverage.py` selects each specimen's extraction profile by
calling `ValidatedRegistryAuthority.snapshot` without a grade, so the call requests the
default filing rung. The new M390 2021 revision intentionally has no export layout and is
applicability-grade; consequently all four parameterized checks that reach the 2021
specimen plus the aggregate blank-box guard fail in `_check_snapshot_filing_capability`.
The production parser was correctly changed to request applicability grade, but the
real/reproduced-render gate that is meant to certify the same profile selection was not
migrated. Focused execution produced 5 failures and 47 passes. This is integration-blocking
because the issue's newly enrolled specimen makes an existing owning test module red.

### stale-casilla-expectation | medium | The 2021 exact-set fixture still names the retired rate-blind box-26 identity

`_M390_REPLACEMENT_ABSENT` in `test_real_render_extraction_coverage.py` still contains
`iva.anual.autorepercutido.intracomunitaria`, while the implementation correctly changed
box 26 to the exact `iva.anual.aic.bienes.tipo-21.cuota` target in the 2021 profile and in
`test_parser_boundary_m390.py`. Because the exact-set test computes expected coverage as
declared targets minus this stale set, the obsolete id no longer removes any declared
target and the blank new box-26 target would be incorrectly expected as present once the
grade failure above is repaired. The stale expectation therefore masks a second focused
regression behind the first refusal.

### filing-surface-claim | medium | An applicability-only revision advertises a filing application surface it cannot honor

The new 2021 application-link fragment declares `surface = "filing"` and names
`cadrumo.application.filing` even though the revision explicitly says filing layout
authority is not claimed and carries no export layout. Filing-grade snapshot construction
correctly refuses this revision, while registry inspection folds application-link surfaces
directly and therefore reports the filing surface as declared. This creates contradictory
capability evidence: the authority grade and runtime filing gate say filing is unavailable,
but the application-link inventory advertises it. The current closure validator forces
casilla-bearing revisions to carry either a filing or communication link, so resolving this
honestly requires a deliberate schema/closure decision for observation-only parser
casillas rather than retaining a knowingly false filing consumer.

No critical findings were identified. The parser's explicit
`RegistryAuthorityGrade.APPLICABILITY` request is correctly scoped, the 2021 temporal
selector is exact and rejects unsupported epochs, and all six non-M390 restamps match the
canonical tracked bytes and SHA-256 digests. The enrolled M390 2021 workbook fingerprint
also matches its tracked canonical artifact.

## Recommendations

- For `reproduced-render-grade`, request applicability-grade authority in the profile
  selection test helper, matching the production parser, and rerun the entire reproduced
  render coverage module.
- For `stale-casilla-expectation`, replace the obsolete rate-blind box-26 id with
  `iva.anual.aic.bienes.tipo-21.cuota` in the 2021 absent-set expectation and prove the
  exact extracted set remains faithful to the reproduced declaration.
- For `filing-surface-claim`, make and record the schema decision for parser-only casillas:
  introduce or reuse an honest observation/extractor lifecycle surface and update closure,
  or otherwise prevent application-link inventory from representing an unavailable filing
  capability. Do not solve it by adding a non-authoritative 2021 export layout.
- Do not integrate the commit or close issue 604 until the two focused test regressions are
  green and the contradictory filing-surface declaration is removed or formally resolved.

## Resolution verification

Corrective commit `87510861e781abb46d451a6fa2a95adc72b2038b` resolves all settled
findings. The reproduced-render helper now explicitly requests applicability-grade
authority, and the entire formerly failing real/reproduced-render module passes. Its M390
2021 absent-set now uses the exact `iva.anual.aic.bienes.tipo-21.cuota` identity. The
2021 registry revision no longer declares a filing link or filing consumer; its only
application surface is `extractor`, it remains applicability-grade, and it still carries
no export layout. The closure validator now recognizes an applicability-grade extractor
as the lifecycle owner for observation-only casillas, removing the prior need for a false
filing declaration.

The additionally exposed blank-box defect is also closed. Box 662 now uses a geometric
`bbox_anchored` target that reads only to the right of the printed box number, so a blank
box remains absent instead of being fabricated as `662.00`. The end-to-end blank-box guard
confirms the fixture contains the printed `662` marker and that no value is extracted.

Verification at current HEAD:

- Formerly failing real/reproduced-render coverage, M390 verification chain, temporal
  epochs, and capability-probe parity: 76 passed.
- M390 parser boundary, application-link/schema closure, and enrolled-source grounding:
  43 passed.
- No new severity-ranked findings were identified in the corrective diff.

The implementation is now safe to integrate, and issue 604 is safe to close.
