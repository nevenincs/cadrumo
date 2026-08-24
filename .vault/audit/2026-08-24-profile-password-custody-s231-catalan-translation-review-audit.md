---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7d4e7af06780d50687af82fae83001849e885812207573f2e78f26c65941b36b'
related: []
---

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
