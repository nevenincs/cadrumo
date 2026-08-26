---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e11181950893fe387b9d70f1b43c9d5dbfca5059fc39805cd4a95d07aae82332'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `registry facade family census`

## Scope

Audit the private-to-public registry module relocation recorded by `c94133f29516b12e3529f3d154c31592562f6198`, rather than replaying that already-delivered mechanical change. Semantic Vaultspec-RAG discovery located the registry public-boundary and authority owners; the exact c941 rename delta then supplied the fixed denominator. `dev/quality/registry_facade_family_census.py` derives the 78 historic pairs, parent-facade exports, current symbol locators, and categorized current consumers under `src/`, `dev/`, and `docs/`.

The checked matrix records one independent future disposition per pair. It is an evidence and scheduling artifact only: no registry family disposition is implemented or represented as complete by this audit.

## Findings

### registry-facade-c941-denominator | medium | exact historical family requires individual disposition gates

The historic `git diff-tree -r -M` evidence names exactly 78 one-to-one renames beneath `src/cadrumo/domain/calculations/registry`. The checked matrix refuses a missing, additional, duplicate, unrelated, grouped, unresolved, or many-to-one pair. It also stores every parent-facade export, its current source locator array, and all current production, test, fixture, documentation, tooling, annotation, registration, dynamic-target, package-attribute, and transitive consumer arrays.

`R01` through `R78` follow deterministic bytewise old/new-pair order. The Sol disposition packet was normalized by named module rather than its presentation row number: `schema.py` is the hard-move special, while `schema_verification.py` remains keep-public.

The reviewed terminal inventory is 54 `keep_public`, 9 `hard_move_complete`, 13 `privatize_external_elimination`, and 2 `delete`. The hard-move cases explicitly reserve the remote-authority move to `src/cadrumo/core/remote_authority.py`, the `ENCODING_ALIAS_MAP` move to `src/cadrumo/domain/calculations/registry/schema_exports.py`, and the `schema.py` local-definition cut while routing its borrowed symbols to their existing owners. The final package gate is separately scheduled to prove zero project package bindings, zero re-exports, and zero unresolved family rows.

### registry-facade-independent-review | medium | S175 remains open pending architecture review

The matrix is deterministically complete and plan-bound, but this execution has not performed the independent Sol architecture review required by the source Step. `W03.P20.S175` therefore remains open. S173 and every affected registry-family implementation stay blocked by the S175 review gate and the individual disposition Steps; the current inert package marker at `src/cadrumo/domain/calculations/registry/__init__.py:1` is not a substitute for those future proofs.

## Recommendations

Execute exactly one canonical plan Step for each matrix row after the independent review clears S175. Preserve the row-specific terminal state and direct-import evidence; do not fold several registry families into one Step. Run the final inert-package fixed-point Step only after all 78 individual dispositions close. Do not start S173 or use the matrix as evidence of a completed hard move, privatization, or deletion before its corresponding follow-on Step has its own execution record and verification.
