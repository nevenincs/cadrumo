---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:e997db0d126ceee71a77dc6be65d2801a1a5d4afe2232e7206004df50a6dea8b'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-edition-authoring with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-edition-authoring` audit: `Minimal registry storage implementation`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Minimal registry storage implementation | {level} | {summary}

     followed by a paragraph carrying the detail. Minimal registry storage implementation is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### apply-preflight | high | A late concurrent edit can leave a partially published modelo

`pack_modelo` validates and mutates each write target in the same loop (`compact.py:186-193`), then does the same for deletions (`compact.py:194-198`). If a later target changed, disappeared, or became newly occupied after the earlier whole-tree check, the function raises only after earlier replacements have landed; the CLI then catches the exception and continues to other modelos. The final fingerprint check is later still (`compact.py:199-200`), so an edit to an otherwise untouched file also detects drift only after all planned writes and deletions. The retained backup makes recovery possible but does not satisfy the promised all-or-nothing publication boundary. The focused tests have no concurrent-edit detector tooth and therefore cannot catch this partial-apply path. Preflight the complete live fingerprint and every exact write/delete condition immediately before the first mutation, and publish through a recoverable atomic strategy or roll back owned mutations on any failure.

### comment-association | medium | Packing preserves comment text but destroys its declaration association

`toml_comments` returns only the text from `#` onward (`compact.py:60-85`), and packing concatenates every extracted comment at the beginning of `0001-declarations.toml` (`compact.py:141-147`). A trailing evidence or label comment that originally identified one row is therefore detached from that row; indentation, blank-line grouping, fragment boundaries, and placement are also discarded. The test at `test_compact.py:43-51` checks only the extracted comment list, so it positively passes this lossy relocation while naming comment preservation. Preserve each comment with its declaration (or retain an explicit source-to-member association) and add a fixture proving row-specific trailing and leading comments remain attributable after consolidation.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
