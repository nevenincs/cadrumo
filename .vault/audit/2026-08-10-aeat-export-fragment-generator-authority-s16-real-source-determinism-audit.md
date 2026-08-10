---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f8d269d5f3b499e18b32d60993a09e1c8fc7abf41d75609c7bcfa8a73caee17b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
