---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6c70ba95f02d79f982a9bab33cb678645741523d027aa1558ce4f999095716d9'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-24-deadline-window-revision-authority-W03-P08-S22]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
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

# `deadline-window-revision-authority` audit: `s22 projection test review`

## Scope

Reviewed Step `W03.P08.S22` against its plan, ADR, research, Step record,
canonical authority implementation, selector, and semantic-coordinate surfaces.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### s22 projection test review | {level} | {summary}

     followed by a paragraph carrying the detail. s22 projection test review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### s22-projection-test-review | low | Clean review with no implementation defects

No actionable defect was found. Expected ownership reuses `select_revision`, and
qualifier identity reuses `deadline_window_semantic_coordinates`; the test declares no
new selector, resolver, parser, cadence authority, horizon, catalogue, qualifier
vocabulary, ordering implementation, or deduplication path. Counter equality plus the
independent length assertion preserves exact multiplicity. Atomic-coordinate uniqueness
and the Modelo 210 case preserve qualified variants. Ordered subsequence comparison
proves modelo-filter invariance, and repeated projection equality covers deterministic
behaviour. The 2022-2026 scope keeps future 2027 gaps and unrelated completeness work
from weakening the projection proof.

Focused Ruff passed. Focused pytest cannot enter either test body because the
concurrently edited, unrelated Modelo 390 corpus fails bundled-authority construction.
That fail-closed error is not a test-design defect; no skip, xfail, mock, stub, or
validation bypass was introduced.

## Recommendations

No S22 code change is recommended. Keep S22 open and rerun the focused pytest target
after the unrelated Modelo 390 corpus is valid.
