---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a1aa1dd9693fc45f94a47a32eb9766dcd0f41357949c1a6b21c80f33328d82cf'
step_id: 'S244'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add a helper that reaches the declared-relief guard through the RECORD status axis, the one production uses, rather than the printed-value axis every existing case used.
- Supply the filer's own territory in that helper, so the counterparty is the only unplaced party.
- Gate the three reserved alpha-3 forms against both relieving categories.
- Add the catalogue-gap and catalogued-country controls that make those refusals attributable.

## Outcome

The classifier was already correct: reserved alpha-3 tokens read as ISO-unassigned rather than as a catalogue gap, so the guard refuses them. Nothing exercised it. Every boundary case used an alpha-2, and the printed-value status axis declines three-letter tokens outright, so an alpha-3 could not reach the guard through the existing helper at all.

The exposure is real rather than theoretical: Facturae states the alpha-3 spelling and is the Spanish national format, so a reserved three-letter token is a shape the majority of this corpus can present. The failure direction is the one this campaign's rules care most about — a reserved code mistaken for a catalogue gap would be SPARED, honouring a relief claimed on a token with no referent.

The reserved codes are NAMED rather than derived, which inverts the treatment the catalogue-gap specimen gets, and correctly. ISO reserves those ranges for private use, so no vocabulary will ever admit them and there is no boundary to track; the catalogue-gap specimen stays derived because that boundary moves every time a country is enrolled.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py -n0 -q -m unit
    33 passed in 5.98s

The mutation was applied from outside the repository through a pytest plugin, leaving every tracked file untouched. Collapsing the reserved bucket into the catalogue-gap bucket: banner printed, holder rebound, 8 invocations, and exactly the six reserved cases red while every control stayed green.

## Notes

The first version of this gate was VACUOUS and its own positive control caught it. The helper omitted the filer's territory, so both residency slots were gaps; the catalogue-gap exemption forgives only the counterparty's, which meant nothing could ever be spared and the reserved assertions would have held for any status whatsoever. The control asserting that an uncatalogued code IS spared failed, which is the only reason the vacuity surfaced. Without that control the Step would have shipped six green assertions proving nothing.

A second divergence was found on the way: the existing helper reaches the guard through the printed-value status axis while the confirm path uses the record axis. A helper that reaches a guard by a route production does not use can be green while the production wiring is dead, which is how the sibling sparing rule shipped unreachable. The new helper uses the production axis.

The test module's marker was worth checking rather than assuming: a by-name run of an existing case reported NOTHING RAN under the unit lane, which read as the test having been deleted. It had in fact been renamed by a peer sweep in the same window.
