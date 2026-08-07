---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:129a1b81efa7a6a5a955daba2aa1aa2c369a50b5936b8d6c422fac45ce90d7a9'
step_id: 'S20'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Emit arithmetic-closure findings over the identities total equals base plus cuota plus recargo plus suplido, cash equals total minus retencion, and per-rate sums, gated by both COM-2026-0005 fixture entries producing a blocking 890.00 versus 927.22 finding

## Scope

- `src/cadrumo/application/ledger`

## Description

Landed as `application/ledger/_closure_findings.py`. Three families of identity,
all computed from figures the document itself states:

**The total closes** -- `total = base + cuota + recargo + suplido`. Omitting
recargo understates a recargo-de-equivalencia invoice by exactly the surcharge;
omitting suplidos reports a false discrepancy on every invoice advancing sums on
the customer's behalf. Both are terms, not refinements.

**Cash closes** -- `cash = total - retencion`. A draft dropping the retención
reconciles the ledger against the wrong figure, and reconciles SUCCESSFULLY,
against a bank movement short by exactly the withholding.

**The per-rate breakdown closes** -- subtotals sum to the flat base and cuota,
and each tier satisfies `base * rate == cuota` on its own. Modelo 303 declares
cuota devengada per tier, so a breakdown summing correctly in aggregate while
misattributing base between tiers still declares into the wrong tier.

### Tolerance

One cent per STATED term (`ROUNDING_ALLOWANCE_PER_TERM`), scaled by how many
terms the document actually supplies. Real invoices round per line, so a few
cents of drift is arithmetic rather than error. Deliberately not a percentage: a
percentage grows with the invoice, so the largest invoices -- where a misread
component costs most -- would get the widest licence to be wrong.

An absent component contributes nothing to the sum and is NOT counted as a term,
so it neither widens the allowance nor invents a figure.

### Silence means not-checked, never verified

An identity missing a term is not evaluated at all. A draft with no printed total
has no total identity to check, and reporting that it closed would be a claim
about a figure the document never stated.

This module is distinct from `printed_total_discrepancy`, which compares the
document against the invoice that was WRITTEN and can therefore only run at
confirm. These identities are internal to the document and run the moment it is
read, which is where the operator is still deciding.

## Outcome

- `_closure_findings.py` -- `closure_findings`, `within_rounding_allowance`,
  `ROUNDING_ALLOWANCE_PER_TERM`. Promoted to the package facade in the same
  change.
- Findings are emitted in a stable order (total, cash, per-tier rate, breakdown
  sums) so an operator surface and a test read them the same way.
- The printed total is never normalised toward the computed one. The
  disagreement IS the finding, and `printed_total` and `grand_total` stay
  distinct throughout the corpus.

## Verification

`test_closure_findings.py` (15 tests) and `test_com_2026_0005_control.py` (13
tests), all passing, counts read from a log on disk.

Both control renderings are asserted INDIVIDUALLY and by name, parametrised over
their corpus `doc_id` rather than a filename, so a corpus rename fails loudly
instead of silently shrinking the set under test. A reader failing on only one
rendering is failing on the rendering rather than on the content, which is why
both are bundled and both are named.

Mutation-proved from OUTSIDE the repository. Rounding allowance widened to 50.00
per term -- wide enough to swallow the control's 37.22 gap:

- `test_closure_findings.py` -- **6 failed, 9 passed**.
- `test_com_2026_0005_control.py` -- **9 failed, 16 passed** across the pair,
  including both parametrised entries by name
  (`[OP-PUR-COM-2026-0005_layout-minimal]` and `[OP-PUR-COM-2026-0005_camera-photo]`)
  and `test_the_control_document_scoring_clean_would_be_a_gap`.

The tolerance boundary is also asserted directly rather than inferred from a
passing case: 37.22 must sit outside the allowance for every term count from 1 to
20, so a future widening fails there first and says why.

Positive control: a closing invoice raises nothing, and per-line rounding drift
of one cent is absorbed -- so the checker is not a blanket accusation.

## Notes

The identities checked here are ACCOUNTING identities, not registry formulas.
`total = base + cuota + recargo + suplido` holds because of what those words
mean, not because a registry file says so, which is why constructed cases are
legitimate here and not tautological under `no-tautological-calculation-tests`.
A test asserting a registry-derived rate or threshold would need bundled AEAT
authority; these do not.

Both fixtures are stamped `synthetic_generated` -- they are generated control
documents and the provenance gate binds that claim to the file's own bytes rather
than to an in-tree generator signature. Not re-stamped.
