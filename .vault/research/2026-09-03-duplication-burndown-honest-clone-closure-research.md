---
tags:
  - '#research'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:82f4de96d5838795741e2d4a62dd449adc3100c289e6567ee4f45df87369df8f'
related:
  - "[[2026-07-14-honest-all-green-adr]]"
  - "[[2026-07-17-duplication-evidence-repair-adr]]"
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace duplication-burndown with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `duplication-burndown` research: `honest clone closure`

<!-- Lead: the question, why it matters to `duplication-burndown`, and what was
     concluded - the evidence picture, not a decision. -->

## Findings

<!-- One ### subsection per line of inquiry. Claim first, evidence after.
     Anchor every non-obvious claim to a re-fetchable locator (URL,
     `file:line`, commit SHA, `package@version`, RFC number). Link, do not
     copy. Pin versions, dates, numbers. State each fact once: link what a
     related vault document already records; do not repeat what an earlier
     section establishes. Name alternatives and why kept or rejected. State
     what was not investigated. Cut anything that changes no decision. -->

## Sources

<!-- Each locator cited above, once: `path:line` backtick locators for code,
     bare URLs for external references. Flag unverified general-knowledge
     claims. -->
