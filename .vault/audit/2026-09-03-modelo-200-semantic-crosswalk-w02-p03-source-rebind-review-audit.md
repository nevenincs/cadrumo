---
tags:
  - '#audit'
  - '#modelo-200-semantic-crosswalk'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8fcd9acddc704c057cc35784b3e9f4d2d9c13bcb23c2218214c7b4ae1054852c'
related:
  - "[[2026-09-02-modelo-200-semantic-crosswalk-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace modelo-200-semantic-crosswalk with a kebab-case feature tag, e.g. #foo-bar.
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

# `modelo-200-semantic-crosswalk` audit: `W02.P03 source-rebind review`

## Scope

Independent review of W02.P03 S05 and S06: the source-rebind planner, its
mutation surface, and focused detector tests. The review checked target-map
ownership, source identity, byte preservation, refusal coverage, isolation,
and publication safety.

## Findings

### source-rebind-transaction | high | A multi-file apply can publish a partial rebind

`apply_m200_source_rebind_plan` completes preflight before writing, but then
calls the one-file atomic writer in a loop over 965 paths. An I/O failure after
one replacement leaves the canonical registry partly rebound, with no journal,
rollback tree, recovery protocol, or failure-injection test. The next run
detects partial application, but cannot restore the original declaration
sources. This violates the phase's atomic mutation requirement.

## Recommendations

Implement a transactional staged-tree or per-file rollback protocol with a
durable journal, then test a deliberately interrupted cutover to prove that
the canonical tree is either wholly unchanged or wholly rebound.
