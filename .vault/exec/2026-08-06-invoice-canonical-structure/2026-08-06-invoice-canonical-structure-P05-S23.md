---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:01f09a7c11eb5c5893abfdbdfcc81d64d5f8ce932740f517df952f10726aeb35'
step_id: 'S23'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Extend the invoice-versus-ledger screen past its ES-only counterparty filter so intracomunitaria, import and export invoices are screened, proving a non-ES invoice diverging from the ledger is now caught where it passes silently today

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Located the screen and its selection predicate by meaning, then confirmed the exact filter line.
- Replaced the counterparty-country proxy with the property it was standing in for.
- Carried an earlier Step's bucket-attribution correction into this guard, having found the same defect shape here.
- Added the refusal proof and a positive control aimed at the commonest non-ES case.

## Outcome

**The screen no longer exempts an invoice because its counterparty is foreign.**

The filter tested the counterparty's COUNTRY, which was serving as a proxy for "carries Spanish IVA". It is a poor proxy in the direction that matters: an invoice to a foreign customer can carry ordinary domestic cuota — goods that never leave the país, a service localised here, a non-established consumer — and every one of those walked straight past the guard. Changing one field on an otherwise identical invoice was enough to escape it, which is what the refusal proof demonstrates by reusing the domestic case's figures and varying only the country.

**The fix replaces the proxy with the property, rather than simply deleting the filter.** The screen already compares only lines carrying a positive cuota. So removing the country test widens WHICH invoices are considered without widening what is actually compared — a zero-cuota invoice contributes no observation whatever its counterparty's country.

That distinction is what makes the widening safe, and the positive control asserts it on the case that would have hurt most: an entrega intracomunitaria exenta is the commonest non-ES invoice there is, and it passes for a **structural** reason rather than by luck. Had the widening been a blanket removal, that case would now refuse and the screen would block correct filings far more often than it caught wrong ones.

**A second defect was found and fixed here rather than left for a later sweep.** The screen compared the invoice's bucket against the context bucket, so an unattributed invoice was silently dropped from the comparison — the same shape as the projection filter corrected earlier in this campaign, appearing this time in the guard rather than in the declaration. Only a populated, mismatching bucket excludes now.

That recurrence is worth noting on its own: the same comparison was written twice, in two files, by the same reasoning, and fixing one did not fix the other. Nothing linked them.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py -q --no-header
    18 passed in 20.24s

    uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/application/modelo -q --no-header
    2221 passed in 88.65s (0:01:28)

    uv run --no-sync ruff check src/cadrumo/application/aggregation/
    All checks passed!

The refusal proof reuses the existing domestic refusal case's figures verbatim and varies only the counterparty country, so the assertion is attributable to the filter rather than to any difference in amounts.

## Notes

**A scripted edit landed on the wrong function and the tests caught it.** The counterparty payload literal appears in two fixture builders in that module, and a first-match replacement edited the wrong one — producing a `NameError` for a parameter that existed only on the other builder. It was corrected by restoring the mis-edited site and targeting the intended builder explicitly.

This is the second scripted edit in this campaign to land somewhere unintended. The first reported success and changed nothing; this one changed the wrong place. Neither was caught by reading the script — both were caught by running the tests, which is the argument for making a targeted edit rather than a pattern replacement whenever the pattern is not provably unique.

**An index caveat, surfaced by the tool itself.** The code index reported `shrunken` during this Step — 79507 of 79595 published sections — and warned that an absent result is therefore not evidence. Every negative claim here rests on a targeted confirmation rather than on a semantic search returning nothing.
