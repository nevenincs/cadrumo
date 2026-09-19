---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0a3a7723f34892cb6229dd0a13519902e43e0df79a7821c27126ea4cacc60c84'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S16 real-source determinism review`

## Scope

Audit the claimed S16 real-source determinism and repository-check proof against the accepted generator-authority decision.

## Findings

### real-source-proof | high | The current S16 harness cannot prove real-source regeneration

The bundled 2025 Modelo 200 record-design parser yields approximately 76 fixed sheets and 6,800 fields plus the `DP200000` variable envelope. The available check harness instead joins a two-field synthetic intermediate and freshly renders its comparison tree. A source-file digest assertion would therefore attest only metadata while granting a green result for synthetic output. The committed Modelo 200 export tree is manual bootstrap material and the governing ADR forbids it as a generation input or correctness oracle. No persisted exact-anchor semantic map or generated target tree exists yet, so a real parser-backed repository check has no authorised input or comparison target.

## Recommendations

- Keep S16 open and remove any synthetic test labelled as a real-source or repository proof.
- Obtain an architecture ruling on reordering or splitting S16 behind semantic-map authorship and generated-tree publication for the selected real revision.
- After that prerequisite lands, make the check call `load_record_design_intermediate` against the hash-verified binary, join the complete persisted semantic map, compare two isolated candidates, and compare each to an independently published generated target. Keep direct/single-file and legacy paths as explicit refusal cases.
