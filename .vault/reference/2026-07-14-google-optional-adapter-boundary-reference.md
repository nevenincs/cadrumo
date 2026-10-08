---
tags:
  - '#reference'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-10-03'
body_hash: 'sha256:87fe207cb5c8ac2b2d7c1b80deffb48800fc214a64c849728f138c2b004bbed2'
related:
  - "[[2026-07-14-google-oauth-audit]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-06-30-bucket-custody-completeness-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
---

# `google-optional-adapter-boundary` reference: `implemented Google adapter boundaries`

This reference records the implementation that constrains the Google scope
reconciliation. The clean scoped files were confirmed against commit
`52352c8d61444b16f966aad6c4c3211996a5c005`. The concurrently modified custody
service was inspected as working-tree blob
`1f59a5ef26f8b561575344bad4a5f5428df1e5a5`; its diff changes prose only, not the
archive behavior cited below.

## Summary

### Authentication and provider composition already exist

Another authentication, session, or provider layer would duplicate shipped code.

### Drive is a ciphertext mirror with integrity reads, not restore authority

Those reads detect missing objects, stale revisions, divergent lineage, and ciphertext corruption. They do not install remote rows into the local secure repository. The correct boundary is therefore “no restore or key authority,” not “Google is push-only.”

### Provider-neutral custody already owns complete recovery

Google-specific KEK escrow, per-row restoration, or a second recovery format would duplicate this recovery mechanism.

### Drive evidence acquisition already reuses canonical byte custody

An exact source search at the audited revision found no
`KekEscrowEnvelope`, `inbound_ingested_files`, `sync inbound`, `google escrow`,
or `google restore` implementation. No watched `_inbound` scanner, filename
router, plaintext staging path, or rejection-sidecar pipeline exists. The ADR
must preserve the two explicit byte-bearing commands and retire only the
unimplemented watched-inbox design.

### Calculation Sheets is a non-authoritative round trip

Targeted confirmation found no `WorkUnit`, `ModeloWorkUnit`,
`CalculationRevision`, `CalculationRevisionCatalogueRepository`, or domain
writer import in the Google adapter or Google calc CLI. Sheet readback is real;
Sheet-to-local calculation persistence is not.

### Ledger correction already has one writer

`aeat app ledger update` builds a typed patch and calls `update_manual_transaction_fields` at `file:src/cadrumo/entrypoints/cli/_ledger.py:545-610`. Exact search found no Google transaction-edit command, generic CSV-corrections surface, or production reverse-merge writer. Adding those under Google would duplicate or bypass the canonical ledger lifecycle.

### Required wording corrections

- Remote integrity verification reads Drive; the mirror is non-authoritative,
  not write-only.
- Calculation Sheets has typed readback and non-persistent computation; it is
  not merely a one-way export.
- Explicit `doclink` and `pull-folder` flows intentionally persist encrypted
  evidence through canonical services; they are not parallel Google writers.
- No new Google escrow, watched inbound pipeline, calculation persistence, or
  ledger reverse merge is required by the current implementation.
