---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0c27492f1e7ce54921ae724d341bc58d5fbad246951612df65690a41f879eb12'
step_id: 'S33'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Prove decomposition parity, that an ex-slim record and a natively rich record carrying identical economic facts decompose to identical components and land on the same partition side, and decide per unmigratable class whether it decomposes correctly, refuses loudly or is flagged defective

## Scope

- `src/cadrumo/domain/invoices/tests/test_decomposition.py`

## Description

- Built one economic record twice, differing only in whether it declares an IVA category.
- Proved the divergence, proved the informativas are unaffected, and proved where the loss actually lands.
- Deliberately did NOT assert divergence on the axes the contract reads through a zero default.

## Outcome

**Exactly one axis diverges across the fold, and its consequences are bounded and visible.**

The slim model cannot hold an IVA category at all, so a record carrying only the facts a slim record could hold decomposes ungrounded while its rich twin — same base, same cuota, same total, same line — decomposes grounded. That divergence is real.

What matters is that it is **named**. The uncategorised record reports `IVA_TREATMENT_UNDECLARED` rather than being silently excluded, and that defect is kept separate from the contradictory-category defect because the operator's fix differs: an absent category is a data-entry gap to fill, a category on its impossible side is a contradiction between two declarations that were both made.

**The informativas are unaffected, and proving that was the more important half.** M347 declares the uncategorised record identically — asserted as an equality on the declared figures rather than a bare non-zero, so a projection that silently degraded it would fail rather than pass. This is where the campaign record's warning was decisive: a test asserting an ex-slim record is DROPPED from M347 or M349 would have been red for a defect that does not exist, since M347 does not run the contract at all and M349 deliberately excludes absence. Aiming there would have manufactured a finding.

**The renta income lane is where it bites, and the behaviour there is correct rather than merely acceptable.** The record is withheld from the income calculation with a typed defect rather than contributing an unclassified figure to it — which is right, because an untagged operation cannot be told apart from an exempt one, and quietly treating one as the other is the silent mis-declaration this campaign exists to prevent.

**Three axes were deliberately left unasserted.** Recargo, suplido, retención and the line set are each read through a zero default by the contract, so a record lacking them decomposes cleanly. A test asserting divergence on any of them would be green for the wrong reason — passing while proving nothing about the fold.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -p no:randomly -q --no-header
    32 passed in 54.29s

    uv run --no-sync ruff check src/cadrumo/application/invoices/tests/test_source_resolver.py
    All checks passed!

One fixture correction is worth recording: the first draft used an invoice total below the M347 declaration floor, so the informativa half returned zero and read as "the record was dropped". It was not dropped — it was below the threshold. A proof that had been accepted at that value would have reported a capability loss that does not exist, which is the same over-severe shape this campaign has now caught several times.

## Notes

No class needed the fold staged or deferred. The divergence is confined to one axis, the canonical writer accepts that axis, and the refusal on the income lane is typed and visible rather than silent — so an operator re-entering a record either declares the treatment or is told, by name, that it is missing.

With this Step closed, `P01` is complete: the conservation law's inventory, its two blocking rows, the parity proof, the fold rules and the decomposition question are all settled.
