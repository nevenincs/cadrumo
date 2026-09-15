---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:c2a65b12bee87b5376947729fcbfbe82afd327a0449589006f718f137f818fd3'
related:
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

# `registry-edition-authoring` audit: `Lane 1 generalized collapse review`

## Scope

Audit the canonical registry delta-collapse implementation against Lane 1 source-equivalence,
minimality, idempotence, modelo-independence, revision-shape, and architecture-boundary requirements.

## Findings

### representative-minimality | high | Required real candidates do not reach independent minimality

Non-applying conversions for modelos 200, 714, 303, and 322 do not satisfy the required
zero-redundancy result. Existing and fresh casilla chains still retain changed rows as full
declarations. A recursive field-patch attempt failed exact simulation on distinct provenance,
source-default, and nested-constraint shapes and was reverted rather than weakening the proof.

### canonical-completion | high | The single orchestration path cannot complete every partial tree

The canonical path now invokes the generic keyed-family converter after casilla planning and no
longer dispatches through a Modelo 100 entry point. It still treats an existing casilla chain as
lift-only, so remaining casilla payload cannot be completed by the same API.

### compiler-boundary | medium | The generic family module imports private compiler internals

The relocated family converter imports three symbols from a private compiler module. These were
inherited from the displaced implementation, but the new canonical owner must consume public
defining symbols or relocate the definitions atomically.

### revision-shape-coverage | medium | Tests do not prove every required revision topology

Real range and within-year names were exercised by candidate runs, but focused converter tests do
not yet cover annual, named-range, within-year, and parallel-branch planning together.

## Recommendations

- Complete casilla recursive overrides using the loader's exact patch, default, and provenance
  semantics while retaining the independent minimality criteria.
- Expose required compiler operations from semantically named public owners.
- Add topology fixtures and rerun fresh isolated candidates for 200, 714, 303, and 322 through
  equivalence, minimality, and a second no-op pass before closing the step.

