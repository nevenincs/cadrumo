---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:87591ffef5f8e34c25a7c624c2324156cc5c841d4d771e28100143a0c41f1b88'
step_id: 'S22'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Adjudicate Modelo 390 revision 2021 casilla surface and exact annual filing authority

## Scope

- `.vault/reference/`

## Description

- Use Vaultspec-RAG to locate the existing snapshot, filing-export, and
  emitted-byte proof authorities; read the discovered authority module in full
  and confirm exact symbols with `rg`.
- Recheck AEAT's historic catalogue, its Modelo 390 exercise-2021 filing page,
  and BOE-A-2009-18472 against the locally enrolled source and extracted record
  design.
- Compare the exact annual source with the loaded 2021 revision, its ten
  parser-only casillas, and the filing-grade sibling surfaces.
- Record the exact non-fileable boundary and route follow-up to the existing
  source-casilla and export-generator plans without adding a duplicate writer.

## Outcome

Modelo 390 revision `2021` remains applicability-only and non-fileable. Its
exact 2021 AEAT record design is already bundled, reviewed, hash-pinned, and
selected only for 2021; AEAT's historic exercise route also exposes
`PresentaciÃ³n (con fichero)`. The gap is therefore not source acquisition or
temporal selection. The revision has ten informational extractor casillas and
no bindings, formulas, filing application link, producer vocabulary, semantic
map, render profile, export layouts, canonical generation, or emitted-byte
proof. Filing-grade siblings have at least 325 casillas, so a 2021 export over
the parser surface would omit most required record values.

`W02.P04.S27` owns the complete source-grounded 2021 casilla and value-arrival
surface. `W02.P04.S28` owns the canonical producer, source-bound map and render
profile, generated fragments, and production emitted-byte proof. No temporal
owner is needed because the selected revision and record-design source have
matching exact closed 2021 scopes. The result preserves the existing parser
capability while refusing any invented filing capability.

## Notes

- Vaultspec-RAG plus targeted `rg` found the existing
  `ValidatedRegistryAuthority` and canonical proof path as the single filing
  authority. No production code, registry source, exporter, or remote AEAT
  behavior was changed.
- `test_m390_selects_the_exact_annual_epoch_and_own_record_design` passed for
  all five enrolled annual epochs, and
  `test_m390_2021_parser_epoch_does_not_advertise_filing_capability` passed.
- The aggregate filing-capability worklist remains intentionally red. Its
  Modelo 390 casilla-surface refusal is expected evidence; no test was
  weakened, skipped, or altered. The broader focused worklist run was not
  retained because concurrent shared test workers exceeded the command capture
  window; the final independent review must re-run it after that contention
  settles.
