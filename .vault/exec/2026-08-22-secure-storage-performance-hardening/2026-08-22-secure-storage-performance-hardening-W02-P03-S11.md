---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2132e112da35702021aed21a77aedd12da32fe0ecf928721fbd6e2cb3beed6e5'
step_id: 'S11'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Make schema and operator-help discovery consume registration metadata without materializing handler subtrees

## Scope

- `src/cadrumo/entrypoints/cli/_command_schema.py`

## Description

- Generate one deterministic registration projection from the materialized
  result-schema decorators and complete live Click tree in Spanish and English.
- Project canonical paths, arguments, options, defaults, choices, localized
  help, hidden and deprecated flags, callback execution policy, owners, and
  normalized source fingerprints into cached immutable runtime records.
- Route result-schema discovery, input-schema discovery, operator-surface
  reconciliation, and MCP/HITL policy reads through metadata without loading
  command handlers.
- Preserve all result declarations for drift accounting while exposing only
  callable identities through `command_schema_refs()`; exact-gate the four
  declared-but-unimplemented identities rather than advertising or deleting
  them.
- Retain longest-prefix evidence for unknown command identities from the
  generated complete-node projection.
- Add exact-set, localized parity, deterministic generation, source binding,
  packaging, fresh-process import, and planted-drift gates.

## Outcome

Runtime discovery now consumes a single packaged metadata resource and imports
none of its handler or payload owners after the projection is loaded. A
fresh-process probe loaded no registry, persistence storage, user-profile,
cryptography, or keyring family. Five metadata-only samples produced a median
of 648.8 ms versus 5,216.0 ms for three materialized samples, an approximately
eightfold reduction on the same host.

The projection retains 300 result-schema declarations and exactly reconciles
the four stated absent verbs, while the callable input/operator/MCP surface
contains 296 identities. These are evidence counts, not fixed pass thresholds:
the gates derive both sets from the current generated and materialized sources.
The complete root/group/leaf census is also generated and exact-gated, so a new
node automatically requires metadata regeneration and parity.

Verification passed:

- scoped Ruff formatting and lint;
- scoped `ty` analysis;
- 15 focused unit tests;
- 36 focused CLI/operator integration tests;
- 8 focused MCP/HITL unit tests and 41 focused MCP/HITL integration tests;
- 12 metadata-specific integration tests, including eight planted drift axes;
- deterministic two-locale generator `--check`;
- a real wheel build containing exactly one 1,932,220-byte metadata resource;
- independent code review with both findings fixed and no open findings.

Implementation landed through `2ced6e71f0`; the independent review record
landed through `5fb055004d`; review fixes landed through `e3a40d1980`.

## Notes

The reviewer found a HIGH callable-surface mismatch and a MEDIUM loss of
unknown-path prefix evidence. Both are closed in the S11 audit and were rerun
against the real operator and MCP/HITL consumers. Cross-platform source hashes
normalize CRLF and LF before hashing; a semantic source change still changes
the fingerprint. No S12 work was started. Unrelated shared-worktree locale
changes were preserved and excluded from all commits.
