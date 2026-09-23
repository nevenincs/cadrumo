---
tags:
  - '#adr'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:89bb307bccd9729b348afc8691a147f56bb4fa867d0c0d3950fd089b0a6c44a9'
related:
  - "[[2026-09-21-calendar-obligations-plan]]"
  - '[[2026-09-23-calendar-obligations-holiday-jurisdiction-research]]'
---

# `calendar-obligations` adr: `Deadline holiday jurisdiction` | (**status:** `accepted`)

## Problem Statement

The overview calendar shifts every registry deadline with no regional territory (`src/cadrumo/application/overview/calendar.py:858` passed `ccaa_code=None`). A deadline that ends on a holiday of the taxpayer's autonomous community is therefore shown as expiring a day or more early. The shift result also does not say which holiday layers were checked, so a national-only answer looks as certain as a complete one. The `HolidayJurisdiction` docstring in `src/cadrumo/domain/deadlines/festivos.py` asserts that AEAT ignores municipal holidays; the official calendar says the opposite. Accepted June decisions settle calendar ownership and evidence meaning but none decides holiday jurisdiction, so this record does.

## Considerations

- Grounding: `2026-09-23-calendar-obligations-holiday-jurisdiction-research`. Autonomic and local holidays extend AEAT deadlines except Modelo 369, keyed on the taxpayer's residence or the body's seat. A natural person's fiscal domicile is the habitual residence by default. The two registry territory vocabularies have no relation, and municipal holidays have no registry source.
- The profile's typed `tax_residence_ccaa` answer defaults a missing value; a defaulted value is not a declared residence.

## Considered options

- Keep national-only shifting: rejected; it reproduces the early-deadline defect and hides the uncertainty.
- Derive the territory from the fiscal-address postcode through a province catalogue: correct for every entity kind, but needs a new 52-entry province fact and a still-optional postcode. Recorded as the follow-on for legal entities and non-residents.
- Match fact 0129 and 0143 by member name: rejected; it is not a registry relation and silently fails for two communities.
- Declare an explicit relation from each fact 0129 token to its fact 0143 territory, and use only a declared common-regime residence of a resident natural person: chosen.

## Constraints

- Filing-affecting holiday behaviour must come from registry data through the canonical authority flow; the relation is authored in fact 0143 and published with the authority.
- Uncertainty stays visible (`no-silent-under-declaration`): national-only, not-shifted and unavailable outcomes are distinct typed states, never a certain date.

## Implementation

Fact 0143 gains one relation entry per fact 0129 token naming its ISO territory, plus the art. 30.6 legal reference; the typed catalogue projection validates completeness against the declared common-regime count and that every target is a declared autonomous community. The deadline `TaxpayerProfile` gains an optional holiday territory, resolved in the profile projection only from an explicitly declared residence of a resident natural person under the common regime. The overview calendar passes that territory to the existing shift rule and records a typed holiday-coverage state on each entry: national and territory, territory unverified, national only (territory unresolved), not shifted (modelo exception) or calendar unavailable. A territory's regional holidays extend a deadline only when the year's holiday publication fact names that territory as verified against the official non-working-day resolution; any other regional entry is ignored and the entry reports the territory as unverified, because a later deadline is the harmful error. Municipal holidays are never evaluated and the coverage states say so. The CLI and TUI project the coverage state without their own date arithmetic; the domain docstring is corrected.

## Rationale

The explicit relation is the smallest grounded change that fixes resident natural persons, the supported autonomo profile, without inventing a residence or a mapping. Every case it cannot decide stays national-only and visibly labelled, which is safer than a wrong regional answer.

## Consequences

- Autonomic holidays extend deadlines for declared common-regime residents only once the year's list for that territory is verified; until the holiday data is re-authored from the official resolutions, residents see their territory reported as unverified and the national-only date.
- Legal entities, non-residents and foral taxpayers remain national-only until the fiscal-address route lands; their dates say so.
- Municipal holidays remain unevaluated; an effective date can still be a day early where a local holiday applies, and the coverage label states this limit.
- Publishing the relation changes the authority generation consumed by every lane.
