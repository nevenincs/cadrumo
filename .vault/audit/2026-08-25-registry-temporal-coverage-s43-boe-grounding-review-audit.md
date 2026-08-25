---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:965ad7f93fa3f656dffe712eab077a738e22334ee21274c2abbe546544bd45c7'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-W02-P05-S43]]"
---

# `registry-temporal-coverage` audit: `S43 BOE grounding review`

## Scope

Independent review of S43's Modelo 038 June-2024 boundary after the initial
implementation selected the correct design and periods but cited only the 2002
enabling order. Scope covered official BOE corpus, legal catalogue entries,
both live revisions and constructs, selector proof, grade and layout status,
and the historical inspection receipt.

## Findings

### amendment-boundary-uncited | high | closed: June 2024 selection resolves to exact BOE provisions

Closed. The official `BOE-A-2024-13049` corpus and canonical sidecars expose
article one and the sole final provision as distinct units.
`orden-hac-646-2024:art-1` grounds the IRUS design change and
`orden-hac-646-2024:df-unica` grounds first application to June 2024. Both
selected revisions and constructs cite the pair. The focused regression pins
the operative text, refuses pre-June periods and proves a widened May selector
is not covered by the selected design source.

The 2005 PDF remains unselected with no epoch or applicability window. Modelo
038 remains applicability-grade, inspection-only and without an export layout.
The peer Modelo 714 change was not modified.

### raw-corpus-trailing-whitespace | low | closed: official HTML is mechanically normalized

Closed. Trailing spaces were removed from the bundled official HTML without
changing its legal text. The canonical preprocessor regenerated the paired
JSON source digest while the extracted Markdown remained byte-identical. Both
legal units and their required phrases continue to resolve through production
verification.

## Recommendations

No further S43 remediation is required. A predecessor revision still requires
official evidence of its complete applicability window.
