---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:fcecfb300b00e5ff78931e8b019cec2e9e6dd99265d67c3aae5793c4c1f86fb6'
related: []
---

# `tui-architecture` audit: `every annual-versus-quarterly pair reconciles its base and its retenciones`

## Scope

## Findings

## Recommendations

## What was swept

`aeat-calculation-grounding` requires that when a tier or category is added to
any total, "every downstream total and every return that reconciles against it
enumerates it too". An annual summary that omits a block desynchronises from
the quarters it summarises, and nothing in the quarterly return would show it.

Every `annual_summary` relation in the registry was derived and read, grouped
by the pair it reconciles.

## Verdict: all five pairs are complete

| annual | quarterly | reconciled |
|---|---|---|
| M190 | M111 | nine importe blocks (02, 05, 08, 11, 14, 17, 20, 23, 26) plus the retenciones TOTAL (28) |
| M180 | M115 | base (02), retenciones (03) |
| M193 | M123 | base (06), retenciones (09) |
| M296 | M216 | base retenciones (10), retenciones total (13) |
| M390 | M303 | cuota devengada total, cuota deducible total, resultado régimen general |

Both halves are covered everywhere: what was paid, and what was withheld from
it. The relations are routed -- `RelationPrefillSourceResolver` is enrolled on
the live calculate mesh -- so these are not dormant declarations.

## A near-miss worth recording

M190 first appeared to reconcile no retenciones at all: intersecting its M111
source casillas against the nine per-block retención boxes (03, 06, 09 ...)
gave the empty set. That was the probe being wrong, not the registry. M190
reconciles the retenciones AGGREGATE, casilla 28, which is the box the taxpayer
actually paid against each quarter -- one relation instead of nine, and the
right one.

The pattern generalises: an aggregate can be reconciled at the total or at its
parts, and a set difference against the parts reports a false gap when the
design chose the total. List the actual sources before believing a coverage
hole.

## Status

Closed for these five pairs. Re-run when a new annual/quarterly pair is
modelled, or when a block is added to an existing quarterly return.
