---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:43e86aec9b30e9c8425431271319587243648cf585661471244a4a03011a6978'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# `secure-storage-performance-hardening` audit: `s17 exact command spec gate review`

## Scope

The review attacked S17's sole-authority scanner for broad exemptions, false positives,
alias and reflection bypasses, assignment shapes, nontermination, and missing bite tests.

## Findings

### s17-exact-command-spec-gate-review | high | resolved broad runtime projection exemption

The first revision exempted the whole error-decoration module. The final gate allows only
the exact same-object callback wrapper and continues to reject structural construction,
decorators, registration, and metadata assignment everywhere outside the compiler.

### s17-exact-command-spec-gate-review | medium | resolved false positives and reflection bypasses

Registrar matching is now call-shape aware, so unrelated `register(record)` calls remain
valid while structural app registration bites. Constant folding, alias propagation,
reflective lookup/mutation, nested targets, and dictionary metadata assignment all have
independent negatives. Conflicting constants use a monotone lattice and cannot oscillate.
The final focused suite and Ruff pass with no blocking finding.

## Recommendations

Retain both static adversarial scanning and dynamic live-graph parity; neither should be
weakened or replaced with a hardcoded command count.
