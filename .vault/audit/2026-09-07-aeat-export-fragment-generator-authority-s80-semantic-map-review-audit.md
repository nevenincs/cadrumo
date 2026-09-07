---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4f8ffcc4019d98e3871a2cb3086a31499e22ce4cf6b44e5a76f9629a96333dee'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-31-aeat-export-fragment-generator-authority-source-defect-adjudication-adr]]"
---

# `aeat-export-fragment-generator-authority` audit: `S80 Modelo 390 2023 semantic map review`

## Scope

Reviewed `W04.P07.S80` against the accepted official-binary generator
authority, source-defect adjudication, and narrow-mechanism declaration
decisions. The review covered exact bundled-source identity, parser-owned
numbered and auxiliary anchor census, normalized cross-epoch semantic
ownership, the Page 2 relayout adjudications, binding and source retargeting,
render-profile evidence reuse, the Page 7 close-literal declaration, real
rendering, and strict lint and type gates.

## Findings

### unchanged-owner-reuse | medium | The 522-anchor reuse gate measures source stability but not semantic-owner stability

`test_m390_2023_reuses_522_anchors_and_pins_the_exact_page_2_relayout`
derives the exact nineteen changed parser anchors and proves that 522 parser
fields compare equal across the 2022 and 2023 sources. It then asserts owners
only for the nineteen changed cells. It never compares the 2023 semantic-map
entries for the 522 unchanged anchors with their 2022 adjudications. A change
to an unchanged anchor's `casilla_id`, producer, binding, literal, semantic
kind, or export-field identity can therefore remain green when the replacement
still resolves and renders, even though the Step expressly permits reuse only
when both source anchor and canonical owner are unchanged.

The current artefacts are correct despite the missing detector: an independent
normalized comparison found zero ownership mismatches across all 522 unchanged
anchors after replacing only the required 2022-to-2023 binding and source
identity tokens. The exact bundled file is 501,060 bytes with SHA-256
`179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7`;
the parser returns 541 numbered anchors and thirteen auxiliary anchors; the
nineteen changed keys are exactly Page 2 cells A83 through A101; and all 175
binding entries and all entry source references target 2023. The render profile
is byte-for-byte the 2022 reviewed profile after only the epoch and source-hash
retarget, and the complete exact-source render succeeds.

The hash-pinned source-defect addition stays narrow. Direct inspection of the
2023 workbook's `xl/sharedStrings.xml` found the twelve-character close form
for Pages 1 through 6 and 8, no twelve-character Page 7 form, and one
eleven-character Page 7 form; the parser exposes that form at Page 7 cell A53
in a twelve-byte slot. The declaration names exactly that source, digest,
sheet, cell, and published content, while the existing geometry guard remains
active. No matcher, shape test, or predicate was widened.

Resolution verified on re-review: `_normalized_reused_owner` now compares the
2022 and 2023 `SemanticMapEntry` values for every one of the 522 unchanged
parser keys. Its tuple covers export-field identity, semantic kind, all seven
mutually exclusive owner payload axes, legal references, and source references.
The only normalization maps the exact old source reference to the exact new
source reference and the revision-scoped `modelo-390-2022.` binding token to
`modelo-390-2023.`; every current old binding carries that token as its prefix.
No cast, `Any`, or type-ignore escape was introduced. The focused semantic-map
suite passed two tests, basedpyright reported zero errors, warnings, or notes,
and Ruff check and format-check passed on a stable HEAD bracket. The MEDIUM
finding is resolved.

### exec-template-annotation | low | The S80 execution record still carries a generated template comment

The feature-scoped `vault check annotations` reports the S80 execution record's
machine-owned guidance comment as one fixable warning. The recorded scope,
changed files, and focused verification results otherwise agree with the
reviewed implementation and reproduced checks.

Resolution verified on re-review: the execution-record template comment was
removed, and the feature-scoped annotation check now reports zero diagnostics.
The LOW finding is resolved.

## Recommendations

Resolve `unchanged-owner-reuse` by making the test compare every unchanged
2022/2023 semantic entry after a narrow normalization of only the exact source
reference and revision-scoped binding token. Use the concrete semantic-entry
and record-design field types at the helper boundaries; do not introduce a
cast, `Any`, or ignored type error. Keep the explicit nineteen-row delta-owner
table as the independent review record for A83 through A101.

Remove the generated comment from the S80 execution record through the
Vaultspec-owned body workflow before closing the Step, then refresh its body
hash and run the feature-scoped lifecycle checks.

Completed on re-review. No HIGH or MEDIUM findings remain for S80.
