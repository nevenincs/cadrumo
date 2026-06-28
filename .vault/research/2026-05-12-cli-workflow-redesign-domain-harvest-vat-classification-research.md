---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `domain harvest VAT classification`

## Topic

Harvest the existing VAT classifier into the redesigned ledger classification
workflow.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §4.2 and §8,
modelo-303/classification ADRs, the VAT classifier domain, ledger classify
paths, and OSS/IOSS and IVA prorrata references.

## Rewrite Scope

This research supports a child ADR that decides the application wrapper API,
`app ledger classify` consumption, the distinction from OSS/IOSS and IVA
prorrata, output/event contract, rejected shapes, and no-shim rule.

## Findings

Apex §4.2 locks `app ledger classify` as a ledger verb that writes
classification through transaction services.

Apex §8 identifies `aeat.domain.vat._classification.classify_vat` as a
deterministic VAT-rule classifier with no application wrapper yet. Its target
consumer is `app ledger classify`.

Existing transaction classification persists `BusinessClassification`,
`business_pct`, `category_id`, notes, provenance, confidence, and history. The
retired financial transaction classify path wrapped `set_classification`, but
must not be revived.

The live `app ledger` surface currently has import, review, and edit only. It
has no classify command.

`classify_vat` is a pure closed-table resolver from
`VATClassificationCriteria` to `VATClassification(category, rate,
requires_reverse_charge, matched_rule_id, notes)`. It performs no persistence.

## Design Implications

Add an application wrapper named
`aeat.application.ledger.classify_ledger_transaction(...)`.

The wrapper loads the ledger transaction, applies business classification
through `set_classification`, optionally normalizes supplied VAT axes into
`VATClassificationCriteria`, calls `classify_vat` when VAT axes are supplied,
persists through the catalogue, and returns a structured result.

`classify_vat` remains a domain resolver. It must not become a persistence API.

`aeat app ledger classify TRANSACTION_ID ...` consumes the wrapper. The CLI
must not call `set_classification` or `classify_vat` directly.

## CLI Modes

Business classification mode accepts:

- `--as BUSINESS|PERSONAL|MIXED|PROCESSED_UNCLASSIFIED|SKIPPED_BY_RULE|FAILED_VALIDATION`
- `--pct`
- `--category`
- `--reason`
- `--confidence`

VAT classification mode accepts explicit VAT criteria flags that normalize into
`VATClassificationCriteria`. VAT output is derived, but persistence still flows
through the application wrapper.

## Boundaries

OSS/IOSS classification belongs to Modelo 369 under `app modelo`, not ledger
classification.

IVA prorrata is separate from ledger VAT classification. The ledger classify
workflow must not use prorrata language.

## Output And Event Contract

The JSON result shape is:

- `operation`: `ledger.classification.set`
- `transaction_id`
- `business_classification`
- `business_pct`
- `category_id`
- `classified_by`
- `confidence`
- `reason`
- `vat_classification`: nullable object with `category`, `rate`,
  `requires_reverse_charge`, `matched_rule_id`, `notes`
- `event_id`
- `bucket_id`
- `changed`

The emitted event is `ledger.classification.set`.

## Rejected Shapes

Reject financial transaction classify revival, `aeat vat classify`,
`app vat classify`, `app modelo classify`, `app ledger vat classify`, direct CLI
calls to `classify_vat`, wrappers that bypass persistence, conflation with
OSS/IOSS, prorrata language, and compatibility shims.
