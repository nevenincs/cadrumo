---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app-review-queue-execution`

## Findings

The 2026-04-18 unified-review-queue ADR is pre-redesign. It accepted a
top-level `aeat review queue`, command-local `--format table|json`, old drill
commands under `financial`, `filing`, and `sync`, and a generic `invoice` kind.
The current apex supersedes that shape: roots are exactly `aeat config` and
`aeat app`, output uses root `--format json|text` via `_emit`, and bare
`invoice` is forbidden in CLI copy and source-kind semantics.

Current code is partial. There is no registered `aeat app review` CLI app.
`aeat.application.review` contains queue models, adapters, filters, edits, and
actions, but the implemented aggregator only emits legacy `transaction`,
`invoice`, and `finding` kinds. Existing review copy and drill commands still
point at retired roots such as `financial`, `filing`, and top-level `review`.
Existing review mutations write workflow-state history but do not emit
bucket-scoped bucket events.

Close the child slot as a read-only unification surface:

```text
aeat app review queue
    [--kind ledger_transaction|purchase_invoice_evidence|payable_invoice|collectible_invoice|modelo_finding|live_notification|sync_divergence]
    [--state pending|all]
    [--modelo MODELO]
    [--source-kind KIND]
    [--format json|text]

aeat app review show REVIEW_ITEM_ID
    [--format json|text]
```

`queue` and `show` are read-only and emit no bucket events. Generic
cross-source `edit`, `approve`, and `defer` are retired for this child ADR.
Source-specific mutations remain under their owning app surfaces unless a
later ADR defines bucket-scoped, evented generic review actions.

Backend harvest scope and execution debt:

- Current `transaction` pending items migrate to `ledger_transaction`.
- Current `invoice` pending items must split into
  `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.
- Current `finding` draft items migrate to `modelo_finding`.
- `live_notification` and `sync_divergence` are reserved review kinds until
  concrete source repositories are wired. Notification parsing exists elsewhere
  in the codebase, but there is no notification review repository; there is no
  `application/sync` package.
- `kind` is the review item kind. `source_kind` is separate: one of
  `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, or
  `collectible_invoice`, or null for modelo/live/sync items.
- `_filter.py` and `_edit.py` are legacy substrate only if their copy and
  source-kind language are renamed away from bare invoice/declaration surfaces.
- Existing tests lock old `transaction` / `invoice` / `finding` behavior and
  old `aeat review show` drill commands. Execution must replace those tests;
  they are not compatibility constraints.

Reject top-level `aeat review`, command-local `--format table|json`, Rich-only
output, generic `invoice` kind/copy, old drill commands under retired roots,
generic mutation verbs in this child ADR, and compatibility aliases.

## Comparable Workflow Grounding

Bookkeeping and tax workflow tools consistently separate passive status from
operator judgment queues.

QuickBooks Online uses a Banking Centre "For Review" area for downloaded bank
transactions before they are accepted into the books. Source:
`https://www.intuit.com/content/dam/intuit/intuitcom/partners/documents/icom-education-program-ca-qbo-ch6-banking-in-quickbooks-online.pdf`.

FreeAgent exposes unexplained and for-approval bank transactions, and explains
that categorizing/explaining transactions helps populate tax returns and VAT
returns. Sources:
`https://support.freeagent.com/hc/en-gb/articles/115001222524-Explain-a-bank-transaction`
and `https://support.freeagent.com/hc/en-gb/p/explain-a-transaction`.

Xero's bank-account workflow surfaces unreconciled items through bank account
reconciliation and recommends keeping bank records accurate by reconciling bank
feed data against business records. Sources:
`https://central.xero.com/0/guide/a5B3m00000F5CItEAN/keep-your-bank-records-accurate-and-up-to-date`
and `https://www.xero.com/us/guides/how-to-do-bank-reconciliation/`.

TaxDome uses workflow task states such as pending, in review, in progress,
waiting for client, waiting for signatures, and waiting for agency in tax
practice workflows. Source:
`https://help.taxdome.com/article/1378-tasks-basic-working-on-a-task`.

This supports the `review` name if and only if the surface is a human-judgment
queue. It does not support using `review` as a passive dashboard, generic
status page, or miscellaneous workflow root.

## Hardened Boundary

`overview status` answers "where is the bucket right now?".

`overview backlog` answers "what unresolved work exists?".

`review queue` answers "what needs human judgment before this bucket is
trustworthy enough for modelo calculation, verification, or internal file
approval?".

The queue row must therefore contain:

- stable review item id;
- source kind;
- object id and optional modelo/period;
- severity;
- reason the item needs judgment;
- blocking versus nonblocking flag;
- current owner surface;
- canonical next command;
- since timestamp.

If a row cannot point to a real source object and a real next command, it does
not belong in `app review queue`.
