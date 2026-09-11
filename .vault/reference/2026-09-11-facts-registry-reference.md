---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:438dfd0d8a57299c0452fa6338c25d9511c0d00a25f63e58e2a86d85642a0abc'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace facts-registry with a kebab-case feature tag, e.g. #foo-bar.
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

# `facts-registry` reference: retired global legal-parameter provider

The accepted governed-fact ADR, the active plan, the shared-catalogue loader,
its schema, and focused loader tests were examined after the last raw
`[parameters.*]` declaration was removed from the legal corpus.

## Summary

`RegistryCatalogues.parameters` is the retired global legal-parameter provider,
not the live `ModeloRevision.parameters` family. No production consumer remains
for the former, while the latter remains the modelo-owned schema described as
out of scope by the ADR.

The retired boundary consists of `LegalParameter`, the top-level catalogue
field, shared legal-fragment parsing and reference validation, and their
dedicated loader tests. Removing all of them makes `[parameters.*]` invalid
rather than silently accepted. The active fact migration gate remains required,
but its terminology should be renamed from legal-parameter migration to fact
retirement as part of the same deletion step.

The published authority artifact is CLI-owned. It must be regenerated after
the schema change; a stale artifact must fail validation, never be adapted or
accepted through a compatibility reader.
