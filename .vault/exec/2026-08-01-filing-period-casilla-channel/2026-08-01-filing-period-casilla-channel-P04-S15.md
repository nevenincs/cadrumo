---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:ac4cf4a83bc8cea3a4d46f97ab78c7bf78d4b427c5585dafe4273131ada1164a'
step_id: 'S15'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Open a tracked issue for the observation channel's type-expressiveness gap: strictly-Decimal CasillaObservation.value cannot express text-family values and emits a plausible-looking structural Decimal zero for them instead

## Scope

- `.vault/audit/2026-08-01-filing-period-casilla-channel-audit.md`

## Description

- Read the amended decision and the audit's persistence-cost section before drafting, so the issue tracks the corrected scope rather than the original claim.
- Confirm the strictly-Decimal declaration on the observation model and enumerate the string family the gap covers.
- Quote a real persisted observation record rather than describing one.
- File the issue against the repository, labelled for defect and local-state domain.

## Outcome

Tracked as repository issue 624.

The issue states the gap as a type-expressiveness limit, which is the corrected framing: the observation does not disappear for a text-family casilla, it persists carrying a structural zero with its legal and source references intact. The record quoted is a real persisted one for a first-quarter Modelo 303, asserting value zero for a period that is `1T`, with two real legal references attached. That combination is the point of the issue, because a wrong value with correct provenance reads as more authoritative than either a wrong value without it or an honest absence.

Scope is stated as the whole registry string family rather than the period casilla alone, and the gap is noted as predating this campaign.

Evidence is the measurement taken during the golden refresh: thirty observation sites moved to zero across seven pages, alongside thirty equivalent moves in the flat value mapping.

The remedy is deliberately left undecided. Three shapes are named without a recommendation, together with the reason the choice belongs to the operator: the value lives inside the encrypted revision envelope, so any change to it is a persistence-boundary change needing roundtrip and anti-tautology attention rather than assertion updates alone.

## Notes

The decision this issue tracks was corrected before this Step ran. The governing ruling originally said moving the casilla off the decimal channel removes its observation; the amendment established that the observation persists carrying the structural zero, and re-scoped this Step accordingly.

The same fact was independently re-derived during the golden refresh, from the persisted records rather than from the amended ruling, by an executor who at the time believed it new and reported it as a correction to the ruling. It was not new. The issue cites it as corroboration of the amendment, which is what it actually is, rather than repeating it as a discovery.

Recorded because the sequence matters: two independent routes reached the same conclusion, and only one of them was first.
