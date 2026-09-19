---
tags:
  - '#adr'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c35ff269c185cabece8570b405f05e223123856667a9d3c3c60cbaa11e034160'
related:
  - "[[2026-09-10-sociedades-manual-coverage-temporal-coverage-research]]"
---

# `sociedades-manual-coverage` adr: `declarative annual manual coverage` | (**status:** `accepted`)

## Problem Statement

Documentary availability currently depends on whichever manual directories happen to be bundled. `2026-09-10-sociedades-manual-coverage-temporal-coverage-research` shows that this hides required years and lets an open revision cite annual evidence outside its own applicability. The product needs one auditable annual-manual boundary without converting manuals into Modelo 200 filing authority.

## Considerations

- The canonical supported-filing-year catalogue is the sole product-wide denominator.
- Annual manual guidance, revision/layout authority, legal grounding, review, and filing eligibility remain distinct axes under `2026-08-14-registry-temporal-coverage-adr`.
- AEAT publication is temporal; an unissued annual manual cannot be inferred from an earlier edition.
- The official source text remains Spanish; localization applies to Cadrumo-owned labels and statuses only.

## Considered options

- **Continue opportunistic directory discovery.** Rejected: omission remains silent.
- **Treat the latest manual as authority for later years.** Rejected: it extrapolates annual guidance.
- **Require a local manual for every year.** Rejected: a not-yet-issued manual becomes indistinguishable from an acquisition failure.
- **Declare annual manual coverage with exact source applicability and explicit unpublished dispositions.** Chosen: every supported year has an observable, source-backed outcome.
- **Promote manual availability into Modelo 200 support.** Rejected: documentary availability does not establish calculation, export, review, or filing authority.

## Constraints

- The existing supported-year catalogue, registry authority, source-reference schema, and snapshot selector are stable parent boundaries.
- Only official AEAT material can satisfy an annual-manual requirement.
- An unpublished disposition retains an official archive locator and observation date; it is not a permanent exemption.
- No 2026 manual source, checksum, corpus directory, or extracted text exists until AEAT publishes it.
- The contract must not widen Modelo 200 selectors or remove existing refusal paths.

## Implementation

Introduce a typed Sociedades annual-manual coverage catalogue beside the canonical filing-year declaration. Each supported year names either an enrolled annual manual source whose applicability interval contains that year and whose corpus manifest exists, or an explicit unpublished disposition with official locator, observation date, and acquisition condition.

Enroll the available 2022 and 2023 manuals through the existing acquisition and extraction pipeline; retain and validate 2024 and 2025; declare 2026 unpublished. Build validation derives its denominator from the canonical catalogue, rejects missing published material and off-interval annual source use, and requires evidence for every unpublished disposition. The operator manual surfaces project availability rather than silently omitting a year. Modelo 200 authority remains selected independently by its own annual revisions.

## Rationale

The chosen option is the only one that gives every declared product year an auditable outcome without laundering a missing source into either a fallback or a filing claim. It applies the year-scoped, fail-closed principle of `2026-08-14-registry-temporal-coverage-adr` to the narrower documentary corpus while preserving the established registry authority boundary.

## Consequences

- Published years become locally evidenced; expected publication absence becomes explicit and re-checkable.
- 2022 and 2023 need acquisition, extraction, provenance capture, enrolment, and focused coverage tests.
- 2026 remains non-substitutable until AEAT publication.
- Existing cross-year Modelo 200 manual references must be narrowed or explicitly disposed.
- This decision does not make Modelo 200 calculation or filing available for 2022, 2023, or 2026.
