---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:53e72b61d5a5244f9f6e72e8d989f31098749bae9a744eee344f97cf644a8f33'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `DDMMYYYY partial implementation review`

## Scope

Review the partial `DDMMYYYY` export-value-policy contribution discovered while executing open step S79. The audited surface comprises the canonical policy, schema validation, fixed-width codec round trip, render-profile declaration and generated-schema derivation, loader-semantic provenance, and the source-pinned Modelo 390 2022 profile. It also includes the reconciled extraction of the registry's existing export-schema declarations into `_schema_exports.py`: `_schema.py` remains the public re-export surface and `_schema_surfaces.py` retains only the non-export declarations. S79 itself remains open: this audit makes no semantic-map or complete-revision claim.

## Findings

### policy-owner-census | low | Corrected before commit

The initial literal census interpreted unrelated parser-format labels as export-policy redeclarations and was narrowed too far. The final guard restores an all-production AST census while reporting only enum members and explicit `value_policy` declarations. It therefore continues to scan application and adapter modules without treating `parse_date` format labels as export policy.

### export-schema extraction | information | Accepted prerequisite

The complete current export-schema block was compared with its tracked origin. The six public declaration models retain the same fields and validation entry points; the registry facade continues to re-export them from `_schema.py`; and no production consumer calls the former private validation helpers. The extraction changes ownership only. The sole semantic addition is the generic `DDMMYYYY` policy shape.

No unresolved critical, high, medium, or low findings remain. The independent reviewer verified that the exact 2022 source cells E65, E69 and E73 state `DDMMAAAA`, the generic policy path has no Modelo 390 default or inference, and the policy, schema, codec, profile, derivation and provenance contracts agree.

## Evidence

- The focused DDMMYYYY policy, codec, provenance, profile, parser, header, and authority lane passed 378 tests sequentially.
- Direct public schema, export, parse, semantic-vocabulary, record-extent, record-spec, and registry-boundary contracts passed 198 tests sequentially.
- A broader schema/public gate produced 303 passes and 8 shared-tree failures: concurrent M303 application-link/export-layout expectations, S73 section-token migration, validator-size reviewability limits, and a missing workbook-parity module. None import or exercise the extracted module or the DDMMYYYY policy; they remain outside this partial's ownership.

## Recommendations

- Retain the source-bound profile as an S79 partial; do not mark S79 complete until its full 537-anchor semantic map and canonical-owner/value-arrival prerequisites are reviewed.
- Keep any future policy-token census extensions AST-aware so unrelated parser vocabulary cannot silently narrow production coverage.
- Treat the export-schema module as the sole wire-facing declaration home; preserve `_schema.py` as its public registry façade.
