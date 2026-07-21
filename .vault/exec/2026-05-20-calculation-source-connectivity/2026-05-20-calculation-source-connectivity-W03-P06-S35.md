---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S35'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# [RETIRED] Represent region scoped category profiles in registry resources

## Reconciliation outcome

Retired on 2026-07-17. This step deliberately created no registry enrollment;
keeping code for that empty layer violated the no-dormant-resolver rule. RIC
and Ceuta/Melilla continue through their dedicated legal mechanisms. The
material below is historical execution evidence, not current architecture.

## Scope

- `src/aeat/_data/registry/aeat/categories/profiles`

## Description

Provision the per-comunidad category-profile override-layer shape via `resolve_region_category_profiles(year)` and leave it deliberately EMPTY. No registry TOML override entries are authored.

## Outcome

Closed DONE-EMPTY per ADR `2026-07-04-renta-region-deductibility` decision D2-C. The override mechanism exists; a future territorial-regime enrolment populates it grounded to its regime law with no further architectural change. Landed in commit `1ca532e93a`.

## Notes

Honest empty layer, not an omission. No `SpendingCategory` warrants a per-comunidad expense-deductibility override today, because the two genuinely region-varying expense-side regimes are OUT of this table by construction: the Reserva para Inversiones en Canarias (Ley 19/1994 art. 27) reaches the base through its OWN dedicated binding, and the Ceuta/Melilla benefit is an art. 68.4 CUOTA deduction (not base-imponible; Ceuta and Melilla are excluded from the `CCAA` enum as ciudades autonomas). Both regime legal bases are already bundled in corpus (`ley-19-1994-art-27.html`, `ley-35-2006-art-68-4.html`), so nothing needed fetching and no regulated value was fabricated.
