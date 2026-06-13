---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `domain-harvest-normatives`

## Findings

The redesigned CLI should harvest the existing read-only legal and manual
corpus APIs, not create new root commands. Current normatives APIs include
`load_catalogue`, `find_reference`, `find_articulo`, `cite`, and
`verify_catalogue` in `src/aeat/domain/normatives/`. Current manual APIs
include `load_manual`, `load_catalogue`, `iter_sections`, `find_rules`, and
`verify_manual_dir` in `src/aeat/domain/manuals/`.

The target placement is `aeat app registry citations ...` for normatives and
`aeat app registry manuals ...` for manuals. These are local reference
catalogue inspection commands, aligned with the `app registry` authority
boundary. They do not read AEAT live systems and do not mutate operator data.

Suggested command shape:

```text
aeat app registry citations list [--tag TAG] [--format json|text]
aeat app registry citations show NORMATIVE_ID [--articulo NUM] [--format json|text]
aeat app registry citations verify [--format json|text]

aeat app registry manuals list [--manual renta|iva] [--year YYYY] [--format json|text]
aeat app registry manuals show --manual renta|iva --year YYYY --part PART [--section SECTION] [--format json|text]
aeat app registry manuals rules --manual renta|iva --year YYYY --part PART [--kind KIND] [--format json|text]
aeat app registry manuals verify --manual renta|iva --year YYYY --part PART [--format json|text]
```

Reject `aeat normatives ...`, `aeat manual ...`, and top-level
`aeat registry ...` because they violate the two-root contract. Reject
operator-facing `manual fetch`: `fetch_manual_part` writes PDFs and manifests,
which is a persisted mutation that is not currently bucket-scoped or evented.
Keep fetch as developer/internal unless a future bucketed/evented design accepts
it.

Read-only commands emit typed payloads via `_emit` and emit no bucket event.
Any future command that persists catalogue snapshots or fetch results must
resolve the active bucket, emit a bucket event, and carry bucket id, command
source and argv, object refs, counts, and sanitized source URLs.
