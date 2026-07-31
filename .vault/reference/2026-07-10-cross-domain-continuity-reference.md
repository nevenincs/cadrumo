---
tags:
  - '#reference'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:a63900af5226c396ab7148e0e3682bc078c4ec5d1195992b18aab0691006e300'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-06-03-iva-exemption-article-adr]]"
---

# `cross-domain-continuity` reference: `Modelo 303 Article 20 exemption prorrata correction`

## Summary

The current Modelo 303 registry correctly has no casilla 61. The correction is limited to withdrawing an invalid Article 20.Uno.26 exception from the IVA prorrata route; it must not create a new official-box binding.

The reference source is the current consolidated Ley 37/1992 at https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740. Article 20.Uno.26 defines the domestic exemption, Article 94 omits it from the right-to-deduct list, and Article 104 consequently places it in the prorrata denominator but outside its numerator. The AEAT record of the Modelo 303 July 2021 change at https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2021/capitulo-1-novedades-destacar-2021/modelo-303.html confirms casilla 61 was removed.

## Blueprint

- `src/aeat/domain/iva/_schema.py:180-211` contains the stale Article 20.Uno.26 full-deduction and casilla-61 statements. The member may remain only if it has a real, separately grounded future consumer; it has none today.
- `src/aeat/application/calculations/_prorrata_regularizacion.py:150,500-509` is the sole active false route. Removing its special exemption set restores the ordinary `DOMESTIC_EXEMPT` path, which contributes only to the non-deductible prorrata volume.
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml:211-253` and `bindings/0000-bindings.toml:213-224` already carry the annual prorrata fields and casilla-44 regularisation surface. Do not change this registry for the correction.
- `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py` needs a real rollup proving Article 20 domestic-exempt volume increases total and non-deductible volume, never the deductible numerator. Retain category validation and propagation coverage in the IVA domain and aggregation suites.

The accepted 2026-06-03 IVA exemption-article ADR is materially false on this route and must be superseded, not edited in place.

## Article 27 recargo assessment boundary

The bundled `ley-58-2003-art-27.html.extracted.md` distinguishes a deadline-only late posture from a statutory recargo: the latter requires a late actual presentation, no prior administrative requirement, and an amount payable. It also leaves the exact twelve-month anniversary in the ordinary 1-percent-plus-1-percent-per-completed-month rule; the 15-percent-plus-interest consequence begins on the following day.

### Current implementation and defect

- `src/aeat/domain/deadlines/_recargo.py` counts completed months only. For a 2026-04-20 deadline, both 2027-04-20 and 2027-04-21 return twelve months; the existing registry therefore selects the 15-percent interest band for both dates. A numeric completed-month input alone cannot express the statutory boundary.
- `src/aeat/application/modelo/_work_plazo.py` receives a `WorkUnit` and the current date only. It converts every late work unit into a recargo band even though neither fact establishes the actual presentation date, positive amount payable, or no-prior-requirement condition.
- `src/aeat/entrypoints/cli/_modelo_rendering.py` then serialises that band and emits an imperative recargo notice on every overdue calculation. The existing JSON payload models a band, percentage, and interest boolean, not an assessment provenance or a monetary result.

### Blueprint

- Retain a typed deadline-only late posture for calendar and draft-calculation surfaces. Its operator notice must state that the voluntary deadline elapsed and that Article 27 consequences depend on the actual presentation, a positive amount payable, and no prior requirement. It must not emit a statutory rate, amount, or eligibility assertion.
- Introduce a separate statutory assessment only when a real presentation event carries an actual date, a positive official or auditable payable amount, and explicit evidence of no prior administrative requirement. The existing justificante schema already models presentation time and optional amount; it does not prove the negative requirement condition, so that fact needs a distinct typed, provenance-carrying boundary.
- Make recargo-band selection calendar-threshold-aware. Preserve rate data in the canonical TOML, add the ordinary twelve-complete-month 13-percent/no-interest result, and select the 15-percent tail only after the calendar anniversary rather than by a completed-month integer alone. Define and test leap-day anniversary semantics before implementation.

### Required evidence

- A non-tautological domain case must distinguish 2027-04-20 (13 percent, no interest) from 2027-04-21 (15 percent, interest) for the same 2026-04-20 deadline.
- A real overdue zero/refund CLI calculation must expose only the deadline posture and conditional advisory, with no statutory recargo payload.
- Assessment tests must prove that absent presentation, amount, or no-prior-requirement evidence never yields an assessment, and that all three evidenced facts do. The existing unconditional-notice regression must be revised rather than retained as the oracle.

## Calculation filing-date convergence

The codebase has two intentionally different date concepts. `period_end_date(year, token)` is a strict range helper: it delegates contiguous tokens to `Period`, preserves only Modelo 202 `1P` through `3P` payment-month mapping, and must continue to refuse `EXT-*`, `4P`, `AD-HOC`, and `EVENT-*` where a ledger-style span is unavailable. Calculation contexts instead require a deterministic date for every accepted typed `Period`.

### Current drift

- `application/verification/_verify.py` reimplements date selection and returns the first day for monthly periods.
- `application/filing/__init__.py` preserves `EXT-nT` as the underlying quarter end but falls back to 31 December for other non-spans.
- Formula-runtime defaults and both Google Sheets calculation paths use 31 December for every non-span, so they disagree with the filing path for `EXT-nT` and Modelo 202 instalments.

### Blueprint

Introduce `calculation_filing_date(period: Period) -> date` in `domain.period`, separate from the strict bare-token helper. It must return `Period.end_date` for contiguous codes; map `EXT-1T` through `EXT-4T` to the equivalent ordinary quarter end, preserving the registry's quarterly Modelo 369 exterior scheme and existing filing behavior; map `1P`, `2P`, and `3P` to their sanctioned Modelo 202 payment-month ends; and explicitly use 31 December for residual accepted non-spans (`4P`, `AD-HOC`, and `EVENT-N`). Route verification, filing replay, formula-runtime defaults when `snapshot.filing_period` is present, Sheets pull and parity calculations, and normal calculation preparation through that one function. A registry scope that has no constructible `Period` may retain its documented 31 December default.

The calculation-sheet export engine must be assessed separately: its layout selects date-effective tariff rows using the same implicit 31 December default. An `EXT-nT` correction can change row counts or addresses. Pull metadata does not currently bind the workbook to an engine version, so the compatibility path must version or explicitly invalidate/re-export affected layouts before a stale workbook is read under the new policy.

### Required evidence

- Every contiguous code produces the same date through core `Period`, the strict helper, and the calculation resolver.
- `1P`, `2P`, and `3P` match calculation, verification, and filing replay; `EXT-1T` through `EXT-4T` use their ordinary quarter ends across normal calculation, Sheets pull, and Sheets parity.
- `4P`, `AD-HOC`, and `EVENT-N` retain an explicit, tested calculation-context fallback without changing strict range-helper refusal.
