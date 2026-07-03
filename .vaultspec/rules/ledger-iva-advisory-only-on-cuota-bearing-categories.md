---
name: ledger-iva-advisory-only-on-cuota-bearing-categories
---

# Ledger IVA advisory fires only on cuota-bearing categories

## Rule

The unconsumed-declarable-IVA advisory — the non-blocking `CalculationSourceDiagnostic`
raised by `unsupported_ledger_iva_observations` on the calculate path and surfaced to the
operator as the `source_advisories` / `ADVISORY:` line — MUST fire only on `IvaCategory`
values that are legally expected to produce a cuota a binding should route. Categories that
are cuota-less by law (exempt, zero-rated, not-subject, exempt intra-community supply,
intra-community triangulation, other-regime) MUST be excluded from the advisory's flagged
set via the named `CUOTA_LESS_M303_IVA_CATEGORIES` frozenset — never by an inline literal.

## Why

Finding #64 wired the advisory to surface declarable IVA that no binding consumes
(`no-silent-under-declaration`). A Modelo 303 grounding pass found it false-fired on
categories that bear no cuota by law (`DOMESTIC_EXEMPT` LIVA art. 20, `INTRA_COMMUNITY_SUPPLY`
art. 25, `OPERACION_NO_SUJETA` art. 7, exports, triangulation, simplificado): they
legitimately match no cuota binding, so flagging them is noise that trains operators to
ignore the alert. The advisory only earns trust if every fire is a genuine unrouted cuota.
After the M303 reverse-charge and import routing landed, the residual flagged set is empty
for every declarable category — the correct invariant: a fire means a real unrouted cuota.

## How

- **Good:** a declarable category that should route a cuota but has no binding yet
  (`DOMESTIC_REVERSE_CHARGE` before its binding; `IMPORT_THIRD_COUNTRY` before its deducible
  binding) fires the advisory until its binding lands.
- **Good:** an exempt/zero/not-subject/exempt-supply/triangulation/simplificado observation
  is a member of `CUOTA_LESS_M303_IVA_CATEGORIES` and never fires the advisory.
- **Bad:** flagging an exempt entrega intracomunitaria or an export as "unrouted declarable
  IVA" — it is base-only/informativa with no cuota, so the fire is a false positive.
- **Bad:** silencing a genuine unrouted reverse-charge or import cuota by adding it to the
  cuota-less set — it bears a real cuota; route it (add the binding) instead.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (accepted) codification candidate; grounding
research `2026-06-09-modelo-iva-routing-carry-research`; commits `068045d2b` (advisory
refinement + the named frozenset), `a9aca68fc` / `f3b0cc777` (routing that empties the
residual set). Companion to `no-silent-under-declaration` and `aeat-calculation-grounding`.
