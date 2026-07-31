---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-07-31'
body_hash: 'sha256:bf56b956cec0ae55ca94f33558391e5116e53f2f410179f032f4b3a531c9574d'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P05.S06`

Confirmed the developer-facing locales CLI module
`src/aeat/locales/cli.py` carries no `doctor`-namespaced string
constants, dictionary entries, or display strings that need updating.
The module is a thin wrapper around `LocaleManager` that walks the
filesystem dynamically; the renamed namespace flows through the YAML
data the manager reads, not through any hardcoded string in this
file. The sentence-case boundary label introduced in P05.S05 is
emitted via `_rewrite_text_prefix_to_sentence_case` in the CLI
boundary, not via the locales CLI tool.

- Modified: none (no-op confirmation step).

## Tests

`rg "doctor|repair" src/aeat/locales/cli.py` returns no hits.
