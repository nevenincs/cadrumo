---
tags:
  - '#adr'
  - '#m303-prorrata-grounding'
date: '2026-07-28'
modified: '2026-08-26'
body_hash: 'sha256:387c6775d98b7c8660b93f84cdd722d5dde9532883ade23694ff64dbfe32ba6e'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - "[[2026-07-27-conformance-cli-adr]]"
  - '[[2026-07-06-cross-period-prorrata-reference]]'
  - '[[2026-07-07-prorrata-especial-adr]]'
  - '[[2026-07-08-iva-prorrata-complexity-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
---

# `m303-prorrata-grounding` adr: `a standalone record for the M303 prorrata corrections` | (**status:** `rejected`)

## Problem Statement

The campaign-close honesty review found that eleven Steps changed the Modelo 303
prorrata computation under a campaign ADR authorising only a governance surface,
and asked for a decision record governing them. This record was scaffolded to be
that record. It is rejected: the territory is already governed by four accepted
records, and a parallel record would have produced sibling accepted markers over
one decision, which is the failure the amend-versus-supersede discipline exists
to prevent.

## Considerations

- The prorrata substrate placement is decided by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.
- The art. 103.Dos.2 mandatory-especial gate and its multiple are owned by
  `2026-07-07-prorrata-especial-adr`, and its emit audience and boundary reading
  by `2026-07-08-iva-prorrata-complexity-adr`.
- The prorrata percentage's ceiling rounding and its full-deduction default on a
  no-volume declaration are both recorded as the model's premises in
  `2026-07-05-cross-period-prorrata-adr`.
- Rounding as explicit registry and runtime policy is an invariant of
  `2026-04-17-modelo-formulas-adr`.

## Considered options

- **A standalone record for the whole cluster (rejected).** It would have carried
  decisions three other accepted records already carry, and would have had to
  restate their content to be readable.
- **Amend each cluster into its owning accepted record (chosen instead).** The
  art. 103.Dos.2 two-redaction and year-aware ruling amends the prorrata-especial
  record and corrects the now-false boundary constraint in the complexity record;
  the rounding and no-volume corrections amend the cross-period record whose
  premises they make true on both revisions.
- **Supersede one of the existing records (rejected).** Nothing reversed. Every
  correction is supported by the existing rationales, so none of them is a pivot.

## Constraints

None. No document depends on this record, and no work was executed under it.

## Implementation

None. The record is retired at birth. Its `related:` edges are left in place so a
reader arriving here reaches the Step records and the owning decisions.

## Rationale

Filing this cluster in a fresh record would have repeated, one level up, the
error the honesty review named: a decision recorded away from the record that
already governs it. The corrective discipline is the same in both directions —
one decision, one record, kept current in place.

## Consequences

- The IVA prorrata decisions stay in the four records that already own them, and
  each gained the content the corrections decided.
- A reader who searches for a dedicated M303 prorrata correction record finds
  this tombstone and the routing table above rather than nothing, which is why it
  is retired rather than deleted.
- The feature tag exists with a single rejected record and no other documents.
  That is accepted: the cost of the tombstone is lower than the cost of the next
  agent re-making the same parallel record.
