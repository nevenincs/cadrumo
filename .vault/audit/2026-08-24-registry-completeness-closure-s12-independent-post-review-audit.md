---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3bcd8ab3e6e5128de4f7b58f33f19a5cbcb864c5f7c25b7f405ccca16b60aa38'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-completeness-closure` audit: `Modelo 036 authority adjudication independent post-review`

## Scope

Independently reviewed the W02.P03.S12 Modelo 036 authority reference and
execution record from commits `a287297827` and `01195e189a`, including the
official BOE and AEAT sources, the selected registry revision, CENSO portal
boundary, local lifecycle, producer vocabulary, and the current owning-plan
routes. No production code was changed.

## Findings

### human-filing-wording | medium | The reference and execution record narrow recording to Sede when the shipped contract permits office filings.

The S12 reference says `record_m036_declaration` records an operator's Sede
filing only, and its execution record repeats that Cadrumo records a human Sede
filing. `M036DeclarationCommand` documents a declaration filed through Sede or
in person at an AEAT office, while `sede_justificante` is optional. The product
still must not create, render, submit, or dispatch an M036 filing; the defect is
the evidence wording, which under-declares the supported human-filing record
surface.

### owner-route | medium | The reference omits the current Modelo 036 source-participation owner.

The S12 reference gives W02.P04.S28 as the future export remedy, but it leaves
the censo source route conditional and unnamed. The current roll-up already
assigns below-filing source-connectivity participation beginning with Modelo 036
to W02.P04.S73. A reader can therefore mistake the export route for the sole
reconsideration path, even though source participation and filing-artifact scope
are separate decisions.

## Recommendations

Add one narrow W02.P04.S74 tracking row. It must correct the S12 reference and
execution record to say Sede-or-office human filing with an optional
justificante; retain the terminal no-local-filing boundary; route source
participation evidence through S73; and route a future filing artifact through
S28 after the existing ADR threshold. Re-run the focused M036 registry, portal,
and lifecycle tests after the documentation correction.
