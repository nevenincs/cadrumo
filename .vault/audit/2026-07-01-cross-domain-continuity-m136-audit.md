---
tags:
  - '#audit'
  - '#cross-domain-continuity-m136'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cross-domain-continuity-m136 with a kebab-case feature tag, e.g. #foo-bar.
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

# `cross-domain-continuity-m136` audit: `Modelo 136 Registry Grounding Review`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Modelo 136 Registry Grounding Review | {level} | {summary}

     followed by a paragraph carrying the detail. Modelo 136 Registry Grounding Review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### modelo-136-corpus-blob-fingerprints | high | Registry source fingerprints match dirty worktree bytes, not committed corpus blobs

The M136 source catalogue fingerprints for `aeat-modelo-136-procedure-record`, `boe-modelo-136-2018-amendment-hac-763`, and `boe-modelo-136-current-form-text` do not match the Git blobs committed by `fee68502d`. They match the current dirty worktree bytes instead, so the targeted registry validator passes locally but a clean checkout materialising the committed LF-normalised blobs will fail `verify_source_catalogue` with byte-count and SHA-256 mismatches. Observed committed blob fingerprints were `aeat-modelo-136-procedure-record` `12134` bytes / `2b77a36f81be91a92a12abc3f2648a0530746e0630f9a8d635f857a218bad99a` versus registry `12273` / `bbea6c7427006799cf2ab9f5f15974b00b5a1268f4d3b2d7a7df9aa5001775fb`, `boe-modelo-136-2018-amendment-hac-763` `48722` / `b4e10ed3f1fb9bc11e12b11192eefd6a37d60c413ebef9e80e02287bdf82f5fb` versus registry `48856` / `6f342ba1e89a577ccf760ec144832830986f0e09ed75fceb3841e6bd7f95c2e0`, and `boe-modelo-136-current-form-text` `71323` / `37c8fd6459eed642a64ffcc318113229adb2d90eabb7e4e0d5e446348b4cbac5` versus registry `72252` / `aad837e393a9e0ec0a399887859e3e6e1792e8383ecc92951fc7db479afda486`. The `5e7bdd11a` `.gitattributes` sidecar protects `*.html` and `*.pdf` only after the affected HTML blob was already normalised, and it does not protect the `.txt` form extraction; the sidecar therefore does not repair the committed evidence bytes for this lane.

Resolution 2026-07-01: resolved by cataloguing the committed LF-normalised blob fingerprints for all three M136 source refs and by making the model-local `.txt` form extraction explicitly `text eol=lf`. Validation now compares `verify_source_catalogue` raw file bytes against the same bytes a clean checkout materialises.

## Recommendations

<!-- Actionable recommendations -->
