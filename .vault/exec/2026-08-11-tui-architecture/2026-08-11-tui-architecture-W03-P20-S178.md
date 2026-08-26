---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f9a41520c765e418f894562bdaf5d2952c1744c36bb5b36813d26c4f72742708'
step_id: 'S178'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retain applicability as public only for locally defined contract symbols and direct-import every borrowed owner

## Scope

- `src/cadrumo/domain/calculations/registry/applicability.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_applicability.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_applicability.py src/cadrumo/domain/calculations/registry/tests/test_registry_recovery_facts.py src/cadrumo/domain/calculations/registry/tests/test_applicability_fragment_family.py -n0` -> `pass`

## Notes

The module advertised six symbols it does not define. Four of them - the
modelo-202 modality family - were imported for no reason but the re-export and
are now gone entirely; PayerFact and TaxRoute are genuinely used inside the
module, so their imports stay while their advertisement does not. The sweep by
symbol confirmed every consumer already reached the owning modules directly,
so no consumer moved.

The wider suites carry unrelated red from the in-flight transport-verb
alignment (peer commit 6ffef9dd23): two overview reason-string assertions and
six cross-period cases refused by an M303 filing-evidence rule. Neither can be
reached by deleting a re-export, so verification is scoped to the registry
applicability surface.
