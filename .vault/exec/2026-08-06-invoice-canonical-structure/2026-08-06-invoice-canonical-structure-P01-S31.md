---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2dca915cd53e75666ebfa85dd388cc22ca8e9cfcf7b087958c73b3de2431a0e2'
step_id: 'S31'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Write the capability-parity proof, a bucket exercising every capability of both stores run through the canonical path asserting identical M347, M349, M303 and M390 outputs and an identical export-import roundtrip, and if that proof cannot be written record that the fold is not ready and what is missing

## Scope

- `src/cadrumo/application/invoices/tests/test_source_resolver.py`

## Description

- Measured which modelos the invoice stores actually feed before writing the proof, which changed what two of its four assertions could honestly say.
- Built one bucket exercising the capabilities that reach a declaration and asserted both modelos over that same bucket.
- Rewrote the M303/M390 half from an equality assertion into a scope guard.
- Left the export/import and decomposition halves to the Steps that own them, rather than restating them weakly here.

## Outcome

**The capability-parity proof is written and passes.** With `S28`'s two blocking rows closed, this is the proof the fold rests on.

Two structural choices carry most of its value:

- **One bucket, not several single-invoice cases.** The declarante summaries aggregate across records, so an error that appears only when a supply and an acquisition are counted together — a mis-signed fold, a direction collapsed onto one clave — is invisible to per-invoice tests. That class of error is the reason a parity proof exists at all.
- **Both modelos asserted over the SAME bucket.** They share one resolver, so a filter error moves a record between them rather than losing it. A single-modelo proof reads that as correct, because the record is still declared — just in the wrong return.

The bucket deliberately includes an intra-community acquisition of **services**, the class the resolver docstring once claimed no IVA category could express. It is declared under its clave here, which is the executable form of that correction.

**Two of the Step's four named modelos could not be asserted as written, and the reason is the defect class this plan exists to remove.** The criterion asks for identical M303 and M390 outputs. Measured at `HEAD`, neither modelo declares a single invoice-sourced binding — only M347, in one fragment, and M349, in three. An equality assertion on those two would compare zero against zero and pass by construction: a green that proves nothing, which is precisely the vacuous-green shape the plan was rewritten to eliminate.

So that half is written as the assertion that does have content: **the invoice stores contribute nothing to either modelo.** That is true today, it is what makes this proof's scope correct rather than arbitrary, and it fails loudly the moment an invoice-sourced binding is added to either — the change that would otherwise widen the fold's blast radius past what was ever verified, silently.

That inversion is the more useful artefact. An equality assertion would have been deleted as noise by the next reader; a scope guard states why the proof stops where it does and defends that boundary.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -p no:randomly -q --no-header
    27 passed in 27.20s

    uv run --no-sync ruff check src/cadrumo/application/invoices/tests/test_source_resolver.py
    All checks passed!

The measurement behind the scope guard:

    rg -l "collectible_invoice|payable_invoice" _data/registry/aeat/modelos/{303,390,347,349}/
    303: 0 files   390: 0 files   347: 1 file   349: 3 files

The M349 proof asserts the record count as well as the two rows, so the bucket is pinned against OVER-declaration as well as under-declaration — the domestic invoice must not appear on a recapitulative return.

## Notes

**Two halves of the Step's criterion are deliberately not restated here.** The export/import roundtrip is owned by `S29`, which proves it at strict-equality standard with its own anti-tautology guard; the decomposition parity is owned by `S33`, which has not run. Restating either weakly inside this proof would have produced a second, shallower assertion of the same property — and a parity proof that passes on a shallow restatement while the owning Step is still open is worse than one that defers.

So this Step certifies the modelo-output half. The fold's full certification is this proof plus `S29` plus `S33`, and `S33` remains open.
