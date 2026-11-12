---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:9eec38a70bd6428ba866e3e83e12bdb1fd7d4b1b353e150b48ffc1dcd36e6f38'
related:
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-11-12-renta-prevision-social-contribution-source-adr]]"
  - '[[2026-11-12-renta-prevision-social-contribution-source-research]]'
---

# `prior-carry-attestation` adr: `Attest or state the pension-reduction excesses pending from earlier ejercicios` | (**status:** `proposed`)

Proposed 2026-11-12 by CALCULATORS for slice S40 (c), on CADRUMO-PRIME's split of 15:03 ("(c) follows the accepted carry ADRs: never inferred, attestation enough"). It is a proposed amendment to `2026-11-08-prior-carry-attestation-adr`, held apart until accepted, in the form the savings carries took. Grounding: lane note `.tmp/2026-11-12-calculators-s40/pension-limits-grounding.md`.

## Problem Statement

LIRPF art. 52.2 lets a contribution that could not reduce the base, because the general base was insufficient or the 30% limit applied, reduce it in the five following ejercicios. Modelo 100 holds those excesses in Anexo C, per contributing member: general social-welfare systems in rows 1284 to 1299 and collective dependency insurance in rows 1300 to 1315 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:8636-8726`), with opening, applied and closing rows per origin year and a generated row for the year's own excess (1299, 1315). None of these rows has a binding or a formula, so a filer with an excess pending from an earlier year cannot apply it, and a filer without one cannot say so. Without an earlier return the pending amounts are unknown, never zero.

## Considerations

- Accepted carry rules: `2026-11-08-prior-carry-attestation-adr` and its 2026-11-12 amendments. A pending carry is read from the earlier return, or stated by the filer as nothing pending (`attest_no_amount`) or with its amounts (`attest_prior_value`). It is never inferred, and a later captured return that contradicts the statement raises `precedence_tier_divergence`.
- The two kinds have separate limits and separate rows, and a filer can hold one without the other (grounding note, art. 52.1 and 51.5).
- Only amounts blocked by the base or by the 30% limit carry. Amounts above the absolute limits never carry (art. 51.6, DA 16).
- Order of application: from 2022 (RD 1039/2022), oldest origin year first, general systems before collective dependency, and earlier excesses before the year's own contributions. In 2020 and 2021 the manual states a proportional split between the kinds (grounding note, per-year locators).
- The rows are kept per contributing member (rows 1284 and 1300 carry the member code), so a joint return keeps each member's excesses apart.

## Considered options

- (a) Two new carry families, one per kind, at row grain keyed by the contributing member, read from the previous return's rows one origin year newer, with the existing `attest_no_amount` and `attest_prior_value` intents. Chosen.
- (b) One family for both kinds. Rejected: the kinds carry and apply separately, and a single statement would let a filer state absence for a kind never looked at.
- (c) A profile fact holding the pending excesses. Rejected by the accepted record: carries are per-ejercicio facts of a declaration.

## Constraints

- The closed absence-attestation family set gains `renta_prevision_social_excess_pending` (general systems) and `renta_dependency_insurance_excess_pending` (collective dependency insurance). Neither joins a default; each is stated on its own, under the "one statement covers every open family" amendment.
- Opening rows read the previous return's rows one origin year newer (`filing_year_offset` -1), declared once in the earliest edition whose design holds these rows, inherited after; the oldest origin year lapses after its application year.
- Applied amounts are fixed by the law's order for the year, never chosen. Where no official text states an order and the order changes a figure, the result stays at calculation grade, as the savings amendment rules.
- The generated rows (1299, 1315) come from the S40 (a) limit formula as the part of the year's admissible contributions it could not reduce; the absolute-limit excess is not generated.
- A pension-reduction remainder never reaches the savings base (art. 50; grounding note, point 8).
- Joint returns keep each member's rows apart; a statement names the member.
- No `schema.toml` change; the words for refusal, statement, effect and origin are served per family.

## Implementation

We will declare the two families on the Anexo C opening rows, compute the applied, closing and generated rows by registry formulas in the order each edition's text states, and let the existing statement intents and door cover them.

- Registry: bindings on the opening rows of each family and member; formulas for the applied rows (in the order of the year), closing rows (opening minus applied) and generated rows; edition deltas only where the official design changed (2021 adds employer-contribution splits, `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/revision.toml:4618` onward).
- Families: the two tokens join the closed set with their served words and the `attest-prior-carries --family` choices.
- Evidence: real resolvers and stores for every Modelo 100 year the envelope admits; the manual's worked example for each rule period as oracle; a two-year cascade; a joint return with excesses on one member; a captured earlier return contradicting an attested zero.
- Hypotheses that may change: whether the 2021 employer-contribution split rows (1742 to 1763) need a third family or fold into the first.

## Rationale

The pension excesses are earlier-ejercicio carries of the same nature as the negative bases the accepted record governs, so they take the same statement, contradiction and door rather than a new mechanism. Two families keep the kinds as separate facts, as the savings carries do.

## Consequences

- A filer with or without an earlier return can complete the pension reduction, and nothing pending is never read from an unprinted box.
- The calculation of the year's own excess feeds the next year's return.
- The `PRIOR_CARRY_FAMILIES` set and the form's carry door grow by two families; the operation contract manifest is regenerated.
- Depends on S40 (a) for the limit and on S40 (b) for the kinds of contribution.
