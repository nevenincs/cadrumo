---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c390dde67a430f33054d74cba7dbdf01d0957dcba362c993f25737e04ffb2f63'
step_id: 'S28'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S28

## Outcome

Done and verified at HEAD. One canonical rate-tier to domestic-category table survives, and both former copies now consume it.

## The collapse

`_RATE_TIER_TO_CATEGORY` (`domain/iva/_classification.py:559`) is the single declaration, with `_CATEGORY_TO_RATE_TIER` derived from it by inversion rather than hand-listed a second time.

The two sites that previously held their own copies now read the accessor:

- `domain/iva/_invoice_classification.py:198` reads `domestic_categories_by_rate_kind()[rate_kind]`
- `application/aggregation/_iva_ledger.py:1250` reads the same accessor

A sweep for a surviving hand-listed rate-kind to `DOMESTIC_*` table finds exactly one site: the canonical declaration itself.

## Why this one was hard to find, recorded in the accessor's own docstring

> three independent copies of this mapping existed before it was promoted, none sharing an identifier with another, so no symbol search would have found them.

That is the general shape this campaign's sweep phase exists for, and the reason the accessor says it in its own docstring rather than leaving it to a commit message: the next reader is the one who would otherwise add a fourth.

## A trap the docstring closes

It also warns against using the mapping's KEY set as "which rate kinds exist" and directs the reader to iterate the enum for that. Conflating the two is what let one of the three copies drift a member short, so the fix names the conflation rather than only removing its symptom.
