---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6507323dc03b98f36cb26be47064ec753daa9de63dd426d6e69a4ce7241bd090'
related: []
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

# `profile-password-custody` audit: `s231 catalan translation review`

## Scope

Review every S231 Catalan translation for accuracy, completeness, structural
token preservation, punctuation, PO validity, and absence of English fallback.

## Findings

### s231-catalan-translation-review | medium | use established terminology for scoped agent personas

The first translation used the literal false friend `persones d'agent
acotades`. It was replaced with the catalogue's established `perfils d'agent
d'abast limitat`, which final review found idiomatic and faithful.

No open findings remain. All ten formerly blank or fuzzy messages preserve
commands, code spans, link targets, Markdown, and source meaning. The download
labels use the correct colon punctuation.

## Recommendations

Close S231. Leave Hungarian translation completion to S232.
