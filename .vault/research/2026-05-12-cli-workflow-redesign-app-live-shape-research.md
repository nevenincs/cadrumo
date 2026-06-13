---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app live shape`

## Topic

Design the `aeat app live` surface for read-only AEAT remote observation.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §4.4 and §8, the bucket
and bucket-event ADRs, the portal catalogue, live-read AEAT/Sede adapters,
`app registry audit-oracles`, and current registry live-read verbs.

## Rewrite Scope

This research supports a child ADR that accepts `aeat app live` as the explicit
live-read app root, defines its grammar, keeps submission forbidden, defines
output and bucket-event rules, and cross-references the `app-registry-boundary`
ADR.

## Summary

`aeat app live` should be a real domain root under `app`, not distributed into
`modelo`, `overview`, `config doctor`, or `registry`.

The root represents the cross-cutting AEAT remote-observation boundary. It
makes live AEAT contact explicit to the operator and separates direct remote
reads from registry structure, local validation, oracle audits, model history,
overview summaries, and readiness diagnostics.

## Evidence

The apex leaves app live placement open and lists candidate verbs.

The current registry mixes pure registry inspection, audit-oracles, and live
reads, including `list-filed-data`, `capture-filed-data`,
`capture-source-filed-data`, and local `verify-filed-state`.

Current registry live access uses `AeatAccessGate(settings).require_live_read()`
plus authenticated session operation `registry-live-read`.

Existing live-read surfaces are read-only or guarded:

- Notifications adapter is read-only and never marks notifications read.
- Expedientes walker and declarations capture already exist.
- NIF-IVA adapter is a read-only public VIES proxy.
- GROI consult adapter refuses form-action drift before click.
- Renta WEB Open is read-only and guards against presentation, payment,
  signing, and persistence paths.
- `require_live_write()` always raises.

Bucket and event rules constrain persistence:

- Persisted operational records are bucket-linked.
- Material mutations emit events.
- Portal catalogue metadata already exists.

## Current Drift

`app registry` currently mixes registry validation, oracle audit, and direct
AEAT live reads.

Filed declaration capture persists under `var/aeat/filed-declarations` instead
of the active bucket event surface.

## Proposed Grammar

```text
aeat app live notifications list [--summary] [--format json|text]
aeat app live notifications show ID [--format json|text]

aeat app live expedientes list [--modelo MODELO] [--year YEAR] [--format json|text]
aeat app live expedientes show EXPEDIENTE_ID [--format json|text]

aeat app live filed list --modelo MODELO --from-year YYYY --to-year YYYY [--format json|text]
aeat app live filed capture --modelo MODELO --year YYYY [--period PERIOD] [--expediente ID] [--limit N] [--format json|text]
aeat app live filed capture-sources --modelo MODELO --year YYYY --period PERIOD [--format json|text]

aeat app live verify nif-iva NIF_IVA [--expected valid|invalid|unknown] [--format json|text]
aeat app live tgvi verify NIF [--expected valid|invalid|unknown] [--format json|text]

aeat app live borrador 100 fetch [--payload PATH] [--format json|text]
aeat app live borrador 100 show SNAPSHOT_ID [--format json|text]

aeat app live portals list [--category CATEGORY] [--modelo MODELO] [--format json|text]
aeat app live portals show PORTAL [--format json|text]
```

## Placement

Keep under `app registry`:

- `inspect`
- `verify`
- `audit-oracles`
- `workbooks verify`
- `parity run`
- `parity replay`

Move or place under `app live`:

- Notifications source commands.
- Expedientes traversal.
- Filed declaration listing and capture.
- NIF-IVA verification.
- TGVI and GROI verification.
- Borrador 100 fetch/show.
- Portal discovery.

`overview` summarizes after bucket snapshot.

`modelo` consumes captured history and snapshots but does not own live session
traversal. `modelo verify` may call live verification later only through an
explicit `--with-live` option.

`config doctor` diagnoses readiness only.

## Rejected Placements

Rejected:

- Put everything under `registry`.
- Distribute live reads into `modelo`.
- Put live reads under `config doctor`.
- Source notifications under `overview`.
- Add root-level `aeat live`.

## Access Rules

Every `app live` command that performs remote navigation or remote requests
calls `require_live_read()` before remote contact and authenticated session
creation.

No live command submits, presents, signs, or pays.

Names avoid `submit`, `present`, `sign`, and `pay`.

`require_live_write()` remains refusal-only and is used only by refusal tests.

## Output And Events

All command output goes through `_emit` typed reports.

Non-persisting reads emit no event.

Persisted captures and snapshots resolve an active bucket and emit events:

- `live.notifications.snapshot_captured`
- `live.expedientes.snapshot_captured`
- `live.filed.capture_created`
- `live.verify.nif_iva_checked`
- `live.verify.tgvi_checked`
- `live.borrador100.snapshot_captured`

Event payloads include `bucket_id`, command source and argv, timestamp, live
surface, remote operation kind, sanitized subject ids, object refs, and count
summary.

Event payloads must not leak raw NIF or name values beyond redaction.

## Boundary

`app-registry-boundary` resolves ownership as follows:

- `app registry` owns structure, validation, workbook parity, and oracle
  binding audits.
- `app live` owns direct AEAT live reads.
- `modelo` consumes observations.
- `overview` summarizes observations.
- `config doctor` diagnoses readiness only.
