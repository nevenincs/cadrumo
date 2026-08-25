---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:100a5035b96314877031bf9ec38f79040a9ebd2169e03ca84cd3bb025fbff88c'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-password-custody` audit: `S259 M220 grounding review`

## Scope

Reviewed `W06.P12.S259` at current HEAD, with provenance traced through commits
`2b8164c1ae` and `62e45d6c59`. The review checked the Modelo 220 2025 revision,
its legal and record-design source identities, exact applicability windows,
revision selection, and the literal widened-2026 refusal snapshot in
`test_catalogue_verification.py`. The focused refusal test was executed directly
and passed. A mandatory post-S260 re-review then ran the complete M220-focused
selection set with 11 passing tests and the exact healthy referential-preflight
witness with 1 passing test. Production code and registry data were not modified.

## Findings

No findings. The 2025 revision is bounded by both `valid_from` / `valid_to` and
the period selector to calendar 2025. Its legal source identity names the 2025
declaration product even though the approving Orden was published in 2026, and
the source's `applies_from` / `applies_to` window is exactly 2025. The cited AEAT
record design is likewise `aeat-dr-220-2025`; no 2026 design or approving
authority is borrowed.

The refusal test asserts the committed 2025 bounds, proves 2025 selection,
requires literal 2026 selection to raise `NoRevisionForPeriodError`, then widens
only the selector in an immutable copy and proves the shared source-coverage
predicate still rejects the 2025 record design at 2026-12-31. This is a
non-tautological regression witness for the exact temporal overclaim S259 closes.

The post-S260 current state retains the exact same closed identities and windows:
`aeat-dr-220-2025` is an AEAT layout-authority source bounded from 2025-01-01
through 2025-12-31, and `boe-modelo-220-2025-form` truthfully names the 2025
declaration product approved by the 2026-published Orden while carrying that
same 2025 applicability window. The full M220 selection matrix and healthy
referential preflight both pass, so the intervening Modelo 182 repair introduced
no cross-model regression. No finding is open at any severity.

## Recommendations

No remediation is required for S259. Preserve the closed 2025 source window and
the literal 2026 refusal witness until a separately grounded 2026 Modelo 220
record design and approving authority are enrolled.
