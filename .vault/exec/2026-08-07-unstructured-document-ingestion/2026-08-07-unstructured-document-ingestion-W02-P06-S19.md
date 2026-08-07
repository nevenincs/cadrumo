---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c1223bee148febd098f9d018ba5a760dca2e78cb4f32bf9573fe9296507a9857'
step_id: 'S19'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Resolve identity roles deterministically, excluding the taxpayer own NIF from counterparty candidacy and surfacing AMBIGUOUS with all candidates when role evidence does not pick exactly one, gated by the OP-PUR-COM-2026-0005_layout-minimal fixture never yielding a first-match id

## Scope

- `src/cadrumo/application/ledger`

## Description

Landed as `application/ledger/_identity_roles.py`. Three mechanisms, all
deterministic:

**The filer's own identifier is never a counterparty candidate.** It appears on
every invoice in both directions, so leaving it in the pool means the most
frequently occurring identifier on the page competes for a role it can never
hold. Comparison is on the canonical form, so a printed `12.345.678-Z` does not
evade exclusion against a stored `12345678Z`.

**A checksum failure is recorded, not dropped.** An identifier failing its
control character is a real fact about the document -- it is precisely what makes
the true supplier invisible to a validating scan -- so it surfaces as an
`IDENTITY_UNVERIFIED` finding. That is the difference between "we could not
verify the supplier" and "we found a supplier", and the operator needs the first
when the first is true.

**EU identifiers count.** Validation routes through `core/identity/_nif_iva.py`
(`nif_iva_format_for_country`, `normalise_nif_iva`, the spec's anchored pattern)
rather than a Spain-shaped test. A Spanish-only check silently discards every
intra-EU counterparty, which is exactly the Modelo 349 population -- the filing
that exists to report them.

### The correction: sole survivorship is still first-match

The first implementation resolved when exactly one candidate survived
elimination. Running the measured defect through it returned the wrong entity
with full `ANCHORED` confidence, because eliminating the bad-checksum identifier
and the filer's own leaves exactly one candidate standing.

Sole survivorship is first-match with the competitors removed beforehand -- the
same guess, harder to see. D4's "no identity resolves without unique role
evidence" is the correct and stronger reading. Resolution now requires POSITIVE
role evidence; a lone verified candidate carrying none resolves `UNANCHORED`
with a `ROLE_UNRESOLVED` finding rather than being promoted.

Order is preserved for display only and never breaks a tie: breaking a tie by
position is first-match under another name.

## Outcome

- `_identity_roles.py` -- `IdentityCandidate`, `IdentityRoleResolution`,
  `canonical_identity_token`, `resolve_counterparty_identity`. Promoted to the
  package facade in the same change.
- Two or more competitors resolve `AMBIGUOUS` carrying EVERY candidate, never a
  winner plus alternates -- there is no winner, and a shape that had one would
  invite a caller to promote the first.

### What the control document actually shows

`OP-PUR-COM-2026-0005_layout-minimal`, read through the production transcriber,
prints supplier `Reformas Delta SL` with CIF `B1234567X` (control character
fails) and recipient `Nordeste Estudio Creativo, S.L.` with `B17283946` (valid).

This sharpens the measured defect beyond its original description. `B17283946`
is not merely "a different entity on the same page" -- on a PURCHASE invoice the
recipient is the FILER, so the defect wrote the taxpayer's own identifier into
the counterparty field. Both guards bite on this document: the checksum removes
the true supplier, and the own-identifier exclusion removes the survivor.

## Verification

`test_identity_roles.py` (15 tests) and `test_com_2026_0005_control.py` (13
tests), all passing, counts read from a log on disk.

The control document is gated against its real bundled bytes: the sidecar's
declared sha256 is checked against the file, so a fixture silently edited to
"fix" a deliberate defect fails before any behavioural assertion can pass
vacuously. A fixture-anchor test asserts `B1234567X` still fails its control
character and the others still pass, so a validator change cannot leave these
cases testing nothing.

Mutation-proved from OUTSIDE the repository. Identity resolution reverted to
first-match:

- `test_identity_roles.py` -- **9 failed, 6 passed**, including
  `test_the_measured_defect_shape_never_yields_a_first_match_identifier`.
- `test_com_2026_0005_control.py` -- **11 failed, 14 passed** across the pair,
  including `test_layout_minimal_never_yields_a_first_match_identifier` and
  `test_layout_minimal_still_refuses_when_the_filer_is_not_the_recipient`.

That second case is deliberate: with an unrelated filer, `B17283946` survives
verification and must STILL not resolve. Without it, the first case would pass on
the own-NIF exclusion while the lone-survivor path stayed broken.

Positive control: role evidence picking exactly one candidate DOES resolve it, so
none of the above is satisfiable by a function that always refuses.

## Notes

Order-independence is asserted directly (`test_reversing_document_order_does_not_change_the_outcome`)
as the structural proof that no first-match remains -- a resolver ranking by
position returns a different identifier under reversal.
