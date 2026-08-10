---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:db1135e600f92f7346490d30ccea28670d10f53fe8a4aa01331e05859c8f7fea'
step_id: 'S300'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# The foreign-asset observations are populable, by a shipped operator surface

## Scope

- `src/cadrumo/application/modelo`

## Description

- Trace FORWARD from the producer rather than grepping the collection's name, because grepping the collection is the move that produced every wrong reading of this chain.
- Read each link's producer and consumer in turn, from the operator surface to the verify-time gate.
- Separate what was READ from what was ASSERTED, and record the boundary rather than rounding it up.

## Outcome

The collection is populable in production and the guard is reachable. There is a shipped operator surface that constructs these observations by name: the aggregate command accepts a typed foreign-asset observation option, with a help string, parses it into the typed model and carries it into the calculate mesh.

The traced chain, each link read directly:

- the CLI option, parsed into the typed observation model
- into the calculate mesh, which accepts the observations and feeds the enrolled foreign-asset resolver
- onto the persisted calculation revision's row-indexed binding values
- read by the evidence projection, which joins the two foreign-asset row bindings and sums per obligation bloque
- into the re-declaration findings on the live verify path

The empty-tuple default the row objects to is a default for callers that supply nothing, not a dead end.

**THE ROW WAS AUTHORED FROM A SYMBOL SWEEP AND INHERITED THAT METHOD'S BLIND SPOT.** Three successive readings of this one chain agreed with each other and all three were wrong: the row said the capacity was dormant, my first reading said the advisory had no production caller, and the row's remaining claim that nothing in production constructs these observations fails too. Agreement between readings that share a method is not corroboration — it is the same blind spot reported three times. That is the finding worth carrying out of this row, more than the answer.

**What was ASSERTED rather than read, and is now its own row.** One link was inferred: that the enrolled resolver writes those row-indexed values in the exact shape the evidence projection joins on. Every other link was read. That link is small and its failure is SILENT — a shape mismatch yields an empty join, the gate returns no finding, and the result is indistinguishable from a taxpayer who genuinely has nothing to declare. A guard against silent under-declaration would then be silent itself, while its presence reads as coverage. It is opened as a successor row requiring an executed verify run, explicitly not a structural reading.

**What this does NOT claim.** That the collection CAN be populated is shown. That it IS populated on any real run is not, and the difference between those two is the same one this campaign got wrong three times in a day. The guard's silence is conditional on operator input and on a carried prior-year baseline, and both conditions are legitimate: the gate's own docstring names first-year silence as the honest outcome rather than a miss, since a fabricated zero baseline would manufacture advisories on first filings.

## Verification

Read directly at HEAD:

    --foreign-asset-observation option       entrypoints/cli/_modelo_aggregate_cli.py:73
    parsed into the typed observation        entrypoints/cli/_modelo_aggregate_cli.py:109-112
    accepted by the calculate mesh           application/modelo/_calculation_actions.py
    evidence projection and its join         application/calculations/_foreign_asset_redeclaration.py
    verify-time gate                         application/modelo/_m720_redeclaration_gate.py
    called on the live verify path           application/modelo/_verification_actions.py

No gate run requested for this row: it changes no code, and the run that WOULD settle its residue belongs to the successor.

## Notes

One design detail survives independently of the ruling and is worth copying. The evidence projection discovers its two row bindings from the registry revision BY SELECTOR rather than hardcoding binding ids, with the stated reason that a registry rename must not silently empty the evidence side. A hardcoded id list would degrade exactly into the silent-guard failure the successor row exists to rule out.

The row is closed on the falsification of its own premise. A row cannot survive that, and closing it on anything else would have meant keeping a row alive to answer a question it did not ask.
