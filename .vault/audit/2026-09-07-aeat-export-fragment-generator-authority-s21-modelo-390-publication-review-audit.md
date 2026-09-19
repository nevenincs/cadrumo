---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:312e8297ba21f2d4ed39ebe859fc436df413aaa98595e28db78b208ffde5a0af'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S21 Modelo 390 generated-tree publication review`

## Scope

Reviewed the four Modelo 390 publications against the canonical generator, publication, provenance, loader, candidate-isolation, source-defect, temporal-selection, and no-fallback boundaries. The review includes the generated package members, live construct references, removed manual trees, consumed bootstrap declarations, drift-gate enrolment, and strict typing of the edited tests.

## Findings

No HIGH or MEDIUM findings remain.

Each 2022-2025 package was rendered and published by the privileged pipeline CLI only after its independently staged candidate validated. After each publication, the exact superseded `export_layouts` directory was deleted and that revision's construct was retargeted before the next revision loaded, so no later publication relied on a mixed manual/generated authority. The final full registry selects exactly one generated layout for each law-selected year.

The generated-tree gate now enrolls all four exact revision/source/epoch/year tuples. Candidate staging excludes both export directory forms, applies source defects only to the two hash-pinned affected sources, and carries the full continuity witness. The bootstrap roster has returned to its unrelated still-unpublished Modelo 200 target; no Modelo 390 authorization outlives its cause.

The edited tests add no cast, `Any`, type ignore, or checker suppression.

## Recommendations

Close S21 and the S79 publication dependency once the bounded generated-tree and CLI checks finish cleanly. Continue the campaign by replacing the gate's remaining hand-maintained enrolment denominator with the law-selectable declared projection and explicit evidence-carrying exclusions.
