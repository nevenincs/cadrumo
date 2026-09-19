---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f43314431deae8cad8b761ce1c50643222b38e9592498585d2a23eb62af005ff'
step_id: 'S12'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Prove the canonical DEHu route and remote-operation guard permit only authenticated read-only notification fetches and refuse acknowledge, mark-read, comparecer, submit, present, and every other AEAT mutation before transport.

## Scope

- `src/cadrumo/application/live src/cadrumo/adapters/outbound/aeat/sede src/cadrumo/domain/calculations/registry src/cadrumo/entrypoints/cli`

## Description

- Locate the canonical CLI pull, bucket-scoped application capture, remote-operation policy, and notification adapter through RAG plus caller and duplication searches.
- Declare normalized exact summary, query, and detail read paths on the DEHu policy; require a bounded policy's permitted POST paths to be declared read paths too.
- Guard every DEHu wire crossing before navigation, including warm-up and notification-detail GET, and recheck every landing through the shared read-landing assertion.
- Retire the workflow's direct adapter notification acquisition; without an explicit active bucket, leave the inbox source not wired instead of bypassing authenticated capture and persistence.
- Replace the stale blanket POST source scan with a structural canary for the single already-read document retrieval and add path, zero-navigation, redirect, detail, and workflow canonicalization coverage.

## Outcome

The only notification acquisition route remains the authenticated, bucket-scoped `capture_notifications` flow behind CLI `pull`. Its DEHu policy now refuses every undeclared same-host route before transport for all HTTP methods; its sole detail POST stays behind AEAT-reported `leida=True`, an exact declared path, and a preceding detail GET guard. No notification acknowledgement, mark-read, comparecencia, submission, presentation, or other remote mutation can reach this route.

## Notes

- The prior blanket source scan incorrectly treated the constrained already-read document retrieval as a generic write; its replacement rejects every additional or unguarded POST call site.
- Scoped safety verification passed: 179 tests and path-scoped Ruff. A broader workflow/import follow-up exceeded the 120-second local command ceiling without a failure signature, so it is not used as acceptance evidence.
- No AEAT request, credentials, taxpayer identity, or notification content was accessed. The required authenticated evidence remains open in P05.S13 through P05.S18.
