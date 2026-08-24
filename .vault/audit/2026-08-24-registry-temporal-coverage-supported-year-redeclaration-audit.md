---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:eaa288db52d2e2a0c22c91cf63da1aeea5c56aafe2ae99af64de5d4586d69aff'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-temporal-coverage with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-temporal-coverage` audit: `supported filing year canonical-home and redeclaration audit`

## Scope

Audit the production tree and governing decisions before S24 introduced a
supported-filing-year declaration. Discovery led with four Vaultspec RAG
queries covering the runtime horizon, catalogue compilation, M303 annual Orden
support, and the governing temporal-coverage decision. The returned epicentres
were read whole, then exact `rg` sweeps covered production constants, year-set
spellings, catalogue constructors, temporal selectors, cadence derivation, and
all M303 imports.

## Findings

### supported-year-python-authority | high | one production year tuple duplicated registry authority

`SUPPORTED_EJERCICIOS` in `_m303_orden_constants` declared 2022 through 2026
and was consumed by both manifest generation and projection validation. No
other production Python constant or collection declared a product-supported
filing-year set. Test-local ranges describe their own fixture matrices and are
not runtime authorities.

### canonical-catalogue-home | low | the shared catalogue compiler is the existing home

`RegistryCatalogues`, `load_catalogue_file`, and
`_load_shared_catalogue_files` already form the fingerprinted, typed,
duplicate-refusing shared registry catalogue boundary. S24 extends that owner;
it does not add another loader, horizon resolver, selector, cadence table, or
period parser.

### canonical-resolution-reuse | low | coverage can be derived entirely from existing authorities

The audit uses `ModeloRevision.period_selector` for the expected period
denominator, `select_revision` for law ownership,
`selector_period_matches_request` for source-period scope, and the existing
source applicability dates for evidence. The resulting advisory contains the
required modelo, filing year, period, and missing prerequisite coordinate.

### post-edit-redeclaration-sweep | low | no production redeclaration remains

The final exact sweep finds no `SUPPORTED_EJERCICIOS` definition or import and
no alternate supported-filing-year collection in production Python. The sole
declaration is the authoring-tree `supported_filing_years` table; production
M303 compilation receives its typed years from `RegistryCatalogues`.

## Recommendations

- Keep the authoring-tree catalogue as the only writable declaration.
- Keep the S24 projection advisory until the already named S20 enforcement
  flip; do not create an interim boolean, allowlist, or second horizon.
- Continue exact redeclaration sweeps whenever a new year is admitted.
