---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:368ce18779e78648f565e1deeb17eae2696b4ecc12140866d2be3e5544ac4265'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

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
