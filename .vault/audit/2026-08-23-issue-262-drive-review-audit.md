---
tags:
  - '#audit'
  - '#issue-262-drive-review'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3bfb8d060dfb17594a2334b67a391fed0ece49ed89f980c887f4690d7712a9df'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace issue-262-drive-review with a kebab-case feature tag, e.g. #foo-bar.
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

# `issue-262-drive-review` audit: Drive attachment review journey

## Scope

Reviewed the issue #262 implementation from encrypted Drive attachment custody through
review discovery, safe provenance inspection, field extraction, explicit confirmation,
invoice linkage, and idempotent repeat ingestion. The review covered production code,
typed CLI envelopes, locale additions, real secure-repository tests, and command-policy
registration. Gmail and OAuth scope changes were excluded.

## Findings

### non-drive-locator-redaction | medium | Generic attachment view could expose a local path or credential-bearing URL

The first review projection copied `source_reference` into `provider_locator` for
non-Drive records. Since the command accepts any attachment id, that could expose a
local source path or a URL query token. Corrected before delivery: only a Drive file id
is projected; every other source reports `not-exposed`. The test continues to prove
manifest metadata and notes never reach the envelope.

### command-policy-oracle | low | New read callbacks were absent from the semantic policy oracle

The live commands were correctly decorated as encrypted-fact, local-I/O, read-only
operations, but the exhaustive callback oracle initially rejected the two additions.
The exact read-only tuples were added and the focused contract now passes.

## Recommendations

- Keep provider locators source-specific; never generalize the projection back to raw
  `source_reference`.
- Keep the queue derived from encrypted manifests and invoice back-links so repeat pulls
  cannot drift a second review-state store.
