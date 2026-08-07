---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:920b00b523c6cfec69e92a2f0d5f8088917984006fb27b5f00f28fb1f278bfbc'
step_id: 'S41'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S41

## Outcome

Addressed, with a sharper mechanism than blanket refusal: the resolver DISCLOSES the inferred clave, and only when the ambiguity is actually reachable for that taxpayer.

## The hazard

An intra-community supply with no declared operation type falls back to clave **E**. The official table expressly carves post-importation supplies (**M** / **H**) out of E, and the category alone cannot distinguish them, so a silent E is a guess about which of three claves applies.

## Why disclosure beats refusal here

Clave M or H requires a PRIOR exempt importation by the same taxpayer: LIVA art. 27.12 exempts the importation only because the onward supply is art. 25 exempt. A bucket holding no importation at all therefore cannot contain a post-importation supply, and the inferred E is not merely likely correct there, it is the only clave available.

Refusing unconditionally would raise an alarm about nothing on every Modelo 349 an ordinary EU-trading taxpayer ever files, which is the profile that trains an operator to ignore the channel. The resolver instead emits its inferred-clave diagnostic only when the bucket genuinely holds an `IMPORT_THIRD_COUNTRY` invoice.

## The subtlety worth preserving

The importation scan reads the whole bucket, not the declared set. An importation is a RECEIVED record producing no Modelo 349 row of its own, so it is absent from the declared set by construction and invisible to a scan of it. A future refactor narrowing that scan to the declared rows would silence the disclosure permanently while looking like a tightening.
