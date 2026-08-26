---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6da848f7fcdb30b6383023796bd816402748f25e9b8fcd6d735c4eb404ef8de8'
step_id: 'S154'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll canonical modelo.export through the existing export_modelo_revision authority with capability and identity preconditions, transient output custody, safe effect/result evidence, and no remote AEAT submission or duplicate export writer

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_export.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass` (26)

## Notes

Transient output custody is expressed by what the result does NOT hold. It
names the artefact and fingerprints it - path, byte size, sha256 - and carries
none of its bytes: custody is the operator's from the moment the file lands,
and a later reader needs to prove which bytes were produced rather than keep
them. A gate asserts no result field carries material.

Presenter, taxpayer and product-software identities come from an injected
command builder rather than the request, so an operation replayed later cannot
stamp an artefact with an identity that has since changed. A gate asserts the
request pins none of them.

The export authority is local by construction and this enrolment adds no
transport, so an artefact reaches AEAT only when a human carries it. The
no-remote-reach gate walks the AST rather than the source text, for the reason
recorded under S153.
