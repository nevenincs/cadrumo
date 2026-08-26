---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:39244a864eb3163b168edada78b18f4a44b656a49d9fe536dda8182adaa23609'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `registry facade family census`

## Scope

Audit the private-to-public registry module relocation recorded by `c94133f29516b12e3529f3d154c31592562f6198`, rather than replaying that already-delivered mechanical change. The fixed c941 rename delta supplies the 78-pair denominator. The reviewed source and consumer evidence is read exclusively from the immutable clean Git object `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`; it is not derived from the current worktree. The archive includes authored source, tests, fixtures, manifests, receipts, tooling, and documentation while excluding generated registry data.

The checked matrix records one independent future disposition per pair. It is evidence and scheduling only: this audit implements no registry family disposition.

## Findings

### registry-facade-c941-denominator | medium | exact historical family requires individual disposition gates

The historic `git diff-tree -r -M` evidence names exactly 78 one-to-one renames beneath `src/cadrumo/domain/calculations/registry`. The checked matrix refuses a missing, extra, duplicate, unrelated, grouped, unresolved, or many-to-one pair. Every row records parent-facade exports, immutable source locators, categorized consumers, literal dynamic imports, unresolved nonliteral dynamic-import sites, a structured per-row owner locator census, competing in-family sites, substitutability rationale, RAG query/result, terminal destinations, and a distinct canonical follow-on Step.

Relative `ImportFrom` targets are resolved to absolute modules; legacy annotations and `ast.TypeAlias` nodes are included. Package member attributes are attributed to one owning facade member rather than every row. The immutable measurement record is regenerated with the evidence commit, not a hard-coded test number, so source evolution cannot silently retain stale edge evidence.

`R01` through `R78` follow deterministic bytewise old/new-pair order. The Sol disposition packet is normalized by named module: `schema.py` is the hard-move special while `schema_verification.py` remains keep-public. The inventory is 54 `keep_public`, 9 `hard_move_complete`, 13 `privatize_external_elimination`, and 2 `delete`. The hard-move cases reserve the remote-authority move to `src/cadrumo/core/remote_authority.py`, `ENCODING_ALIAS_MAP` to `src/cadrumo/domain/calculations/registry/schema_exports.py`, and the `schema.py` local-definition cut with borrowed bindings routed to their existing owners.

A separate current-terminal report observes future S176--S254 work against the working tree. It accepts a removed public candidate or private relocation as a valid pending terminal state and never demands a shim, alias, forwarding module, or re-export. It is intentionally separate from the immutable S175 evidence check.

### registry-facade-independent-review | medium | Sol review failed frozen evidence and S175 remains open

Independent Sol review of frozen `976d47eb75` failed because its census was worktree-derived, did not fully resolve relative imports or `ast.TypeAlias`, dropped nonliteral dynamic imports, used imprecise package attribution, and had boilerplate semantic evidence that could not survive later H/P/D terminal changes.

This remediation binds the regenerated schema-v2 matrix to `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`, adds structured machine-anchored evidence and a terminal-state observer, and adds regressions for source measurements, TypeAlias, fixture ordering, dynamic imports, package attributes, dirty-worktree immunity, and future terminal disappearance. S175 remains open pending a new independent Sol review; S173 and affected registry work remain blocked by S175 and the individual disposition Steps.

## Recommendations

Execute exactly one canonical plan Step for each matrix row after the independent review clears S175. Preserve the row-specific terminal state and direct-import evidence; do not fold several registry families into one Step. Run the final inert-package fixed-point Step only after all 78 individual dispositions close. Do not use this audit or its matrix as evidence that a hard move, privatization, or deletion has already completed.
