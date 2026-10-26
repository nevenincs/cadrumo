---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:5780e3af420ff07fabc22786d84475229072fba5004cf31b635ed9eaa6d7dcd2'
related: []
---
# `source-casilla-integration` audit: `S89 row source identity review`

## Scope

Independent review of the S89-owned hunks in mixed commit `f769e9ff9f` and scoped follow-on `f8aa24046d`. The review read the governing plan, ADR, research, reference, S87/S88 records and audits, then used Vaultspec-RAG code discovery, whole-file reads of the canonical row carrier, source-resolution carrier, calculation revision, persistence writer, encrypted repository, and repository port, plus exact-symbol confirmation for redeclarations.

It checked that the stored value is the exact registry row-set selector grouping rather than the coarser row-assembly source-kind axis; that its optionality is truthful; that canonical hashing, secure projection, and secure rehydration retain it; that a grouping mutation changes the revision id; and that S89 did not add a parallel carrier, resolver, store, provenance route, or S90/S91 behavior.

## Findings

### row-source-resolution-list-rehydration | high | Canonical list-form input discarded the exact grouping

`CalculationSourceResolution` accepts a canonical list form for row-source identities, but its rehydration projection omitted `row_set_grouping`. A live, no-mock construction carrying the registry token `per_perceptor_clave` produced an identity with `None`, losing the required distinguishing selector before the existing calculation-revision persistence handoff. The correction now carries the same optional field through this canonical input projection, and a focused no-mock regression proves the retained value.

### row-source-identity-persistence | low | Original secure proof used a source shape inconsistent with its optionality explanation

The real encrypted repository proof supplied `per_inventory_activity` on an inventory identity while the carrier comment stated inventory activities could not have row-set selectors. The persistence behavior itself was correct, but the explanation was too narrow. The comment now accurately states that the field is absent only for row identities that do not originate from a registry row-set selector.

## Recommendations

No open S89 finding remains after the narrow carrier correction. Preserve `row_set_grouping` as the raw exact `BindingRowSetSelector.grouping` token: `RowSetGroupingKind` is a coarser dispatcher category and would conflate distinct selector groupings. Keep its optionality until S90 supplies ingress ownership and hostile-row validation. S90 and S91 remain open and must not be inferred from this carrier and encrypted-repository proof.
