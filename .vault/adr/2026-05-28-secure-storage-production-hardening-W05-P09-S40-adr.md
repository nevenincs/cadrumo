---
tags:
  - '#adr'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s40-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
---



# `secure-storage-production-hardening` adr: `W05.P09.S40 operator-directed export exceptions` | (**status:** `accepted`)

## Problem Statement

The side-store hardening wave migrated sensitive bucket-local JSON and JSONL
repositories behind runtime-created secure-object repositories. Two retained
surfaces still intentionally write plaintext material outside the secure-object
backend when an operator asks for an export: evidence bundle ZIP export and
ledger transaction export.

These writes are not repository persistence, but without an explicit exception
record they can be confused with the plaintext side stores the hardening plan is
removing. S40 decides the allowed boundary for these export writes and confirms
that they do not authorize new bucket-local plaintext stores.

## Considerations

The accepted secure-storage direction requires normal sensitive application
state to live behind runtime-created secure-object repositories. The S36
inventory and S40 research distinguish explicit operator exports from default
bucket-local repositories because exports cross to a caller-selected path for
inspection, transfer, filing preparation, or audit handoff.

Evidence bundle export verifies the bundle before writing and refuses failed
verification. Incomplete bundles require an explicit force option, and
`manifest.json` is written last so partial archives do not look complete.

Ledger transaction export writes only when the command includes an output path.
The export path records a ledger event containing the export format, row count,
byte size, digest, and bounded transaction identifiers.

The remaining purchase-invoice-evidence and business-operation invoice JSONL
stores are not accepted exceptions here. They remain pending secure-object
migration under their later ledger side-store rows unless implementation
research rejects migration.

## Constraints

Operator-directed export writes may contain financial, identity, or audit
material. The application cannot protect caller-selected destinations with the
same custody and idle-lock guarantees as bucket-local secure-object storage.

The export boundary must therefore remain explicit, narrow, and observable:
the operator supplies the destination, the service writes only for that command,
and the write must not become a reusable application repository.

This ADR does not cover remote mirrors, storage-provider sidecars, temporary
secret materialisation, profile export, declaration export, or future global
plaintext-exception consolidation. Those surfaces remain governed by their own
tracking and must not be inferred from this W05.P09 closeout.

## Implementation

Retain the evidence bundle ZIP export and ledger transaction export as
accepted operator-directed plaintext export exceptions.

The implementation rule is:

- Normal reads and writes of evidence, inventory, live snapshots, verify
  observations, and future migrated ledger side stores must use runtime-created
  secure-object repositories.
- Export commands may write plaintext bytes only to a caller-provided output
  path and only as the direct result of an explicit export operation.
- Export implementations must keep refusal checks, verification requirements,
  digest or event metadata, and bounded audit breadcrumbs that allow the export
  event to be reconciled without treating the export file as canonical state.
- Tests and static persistence policy may allow these export writes only under
  their exact production function boundaries.

If a later migration row proposes retaining a bucket-local plaintext repository,
that decision requires a separate research-backed ADR with sensitivity,
threat-model, retention, and retirement analysis.

## Rationale

Operator-directed exports are necessary boundary crossings. They let the
operator hand an evidence archive, tabular ledger, or filing-support artefact to
external tools, accountants, or filing workflows. Treating those outputs as
forbidden repository persistence would remove useful workflows without reducing
the risk that motivated W05.P09.

The accepted boundary preserves the secure-storage invariant where it matters:
default application state remains encrypted and bucket-scoped, while explicit
exports are intentional artefacts outside application custody. The explicit
exception also prevents the export pattern from becoming a loophole for local
JSON or JSONL side stores.

## Consequences

Operators are responsible for protecting exported files after choosing the
destination path. The application should continue to make export operations
visibly explicit and should avoid writing exported sensitive material to hidden
default directories.

Future code review must reject any use of this ADR to justify normal
bucket-local plaintext repositories. The currently pending ledger JSONL side
stores remain migration work, not accepted exceptions, unless later research
and ADR coverage explicitly change that disposition.
