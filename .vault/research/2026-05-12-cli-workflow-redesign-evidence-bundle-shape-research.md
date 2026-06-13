---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `evidence bundle shape`

## Topic

Design the EvidenceBundle model and `aeat app modelo audit` surface.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §6 and §8,
app-modelo-shape, modelo-file, filing-record, modelo-verify, the
bucket-event-history ADR, evidence/export references, and run-trace references.

## Rewrite Scope

This research supports a child ADR that decides the EvidenceBundle model,
`app modelo audit show/verify/export/replay`, storage placement, export format,
replay relation, no-live-submission rule, and no-shim rule.

## Findings

Adopt `aeat app modelo audit show|verify|export|replay` as the evidence
packaging surface.

Do not introduce root-level `audit` or `run` commands, and do not add
compatibility shims.

EvidenceBundle is a bucket-scoped, work-unit-bound aggregate. It is not a
bucket-global truth record. Domain records remain authoritative; the bundle
records provenance, verification, reproducibility inputs, and export material.

Durable manifests and verification reports are stored inside the active bucket
under the Modelo work unit or filing case. Bucket event history remains the
chronological index.

Audit events:

- `modelo.audit.verified`
- `modelo.audit.exported`
- `modelo.audit.replayed`

## Proposed Grammar

```text
aeat app modelo audit show WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
aeat app modelo audit verify WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
aeat app modelo audit export WORK_UNIT_ID --output PATH [--revision REV | --filing-record ID] [--force-incomplete] [--format json|text]
aeat app modelo audit replay WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
```

Default target selection uses the current filed filing record when one exists.
Otherwise, it uses the selected calculation revision. `--filing-record` is the
strongest selector.

## EvidenceBundle Model

`EvidenceBundle` is a typed manifest plus referenced records:

- `bundle_id`, `schema_version`, `created_at`
- `bucket_id`, `work_unit_id`, `modelo`, `year`, `period`
- `calculation_revision_id`, optional `filing_record_id`
- `verification_report_id`
- `profile_snapshot_id`, `profile_snapshot_hash`
- `ledger_snapshot_hash` or transaction catalogue fingerprint
- source-kind refs: `ledger_transaction`, `purchase_invoice_evidence`,
  `payable_invoice`, `collectible_invoice`
- export artefact refs and SHA-256 digests
- filed revision and filing record refs
- run trace refs: `run_id`, `trace_sha256`, `events_sha256`
- registry, corpus, profile, and source digests needed for replay
- per-item status: `present`, `missing`, `stale`, `mismatch`, `not_required`
- verdict: `pass`, `fail`, `partial`, `replay_degraded`, `replay_corrupt`

The bundle is not the source of relational truth. Domain records own current
state; the bundle records provenance and reproducibility.

## Export Format

Export as a ZIP archive with `manifest.json` written last.

Required contents:

- `manifest.json`
- verification report JSON
- filing record JSON when present
- calculation revision JSON
- profile snapshot JSON or canonical redacted projection
- ledger snapshot/fingerprint report plus source-object refs
- export receipt/file digest records
- redacted run `trace.json` and `events.jsonl` where referenced

`audit export` runs `audit verify` first. `fail` refuses by default. `partial`
requires `--force-incomplete`.

## Replay Contract

`audit replay` is evidence-case replay, not root observability argv replay. It
uses stored source traces, registry/corpus hashes, profile snapshot hash, ledger
snapshot hash, and calculation inputs to reproduce the calculation/evidence
path.

Output states:

- `replay_match`
- `replay_degraded`
- `replay_corrupt`

Replay never contacts AEAT and never performs live submission.
