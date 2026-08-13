---
tags:
  - '#audit'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3a8a729ba0dc769a28d8bc3ee3aa5bd0fc6191db96116345fd329eca5cbb443c'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace canonical-identifiers with a kebab-case feature tag, e.g. #foo-bar.
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

# `canonical-identifiers` audit: `s11 contract`

## Scope

Audit the S11 CLI declaration-row contract migration from bare `str` to the
canonical `AeatExpedienteId` alias.

## Findings

No S11 findings. The payload imports `AeatExpedienteId` through the canonical
public `core.identity` facade and reuses its existing 12-32 uppercase
alphanumeric AEAT constraint. The diff changes no other declaration field,
wire key, producer, or registration.

### unrelated-focused-lane-failures | low | Existing integration inventory assertions are red

The focused live-read integration module has 33 passing tests and one failure
because the asserted subgroup inventory omits `deudas`. The wider
schema-conformance lane has 332 passing tests and one profile-precondition
refusal for `--tax-residence-jurisdiction-scope`. Neither signature references
the S11 payload or its identifier constraint.

## Recommendations

Repair the live-read subgroup inventory and profile-precondition expectation in
their owning campaigns; do not widen S11 beyond its one declared payload field.
