---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:884b9c1c0b359db92309912cbf369b74d5d12abf797454884998ee07f26198e5'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-entrypoint-separation with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-entrypoint-separation` audit: `p03 verification publication`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### p03 verification publication | {level} | {summary}

     followed by a paragraph carrying the detail. p03 verification publication is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### stale-published-tui-route-docs | medium | Published documentation still names the retired global request and deleted destination module

The generated locale catalogues at `docs/locales/{ca,es,hu}/LC_MESSAGES/download.po` retain the
message "Add `--tui` to work in a full-screen interface instead:". The API document
`docs/api/cadrumo.entrypoints.tui.rst` still includes the deleted
`cadrumo.entrypoints.tui.destination_session` module, and its dedicated API page remains. These
published artefacts contradict the new `aeat app tui` seam and leave documentation referencing a
module P02 removed. Regenerate or update the owning documentation outputs and remove the obsolete
API page before closing P03.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
