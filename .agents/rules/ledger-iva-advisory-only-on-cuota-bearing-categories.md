---
name: ledger-iva-advisory-only-on-cuota-bearing-categories
trigger: always_on
---

# The ledger IVA advisory fires only on cuota-bearing categories

The unconsumed-declarable-IVA advisory — the non-blocking diagnostic raised on
the calculate path and surfaced to the operator as an advisory line — MUST fire
only on `IvaCategory` values legally expected to produce a cuota that a binding
should route.

Categories that are **cuota-less by law** (exempt, zero-rated, not-subject,
exempt intra-community supply, triangulation, other-regime) MUST be excluded via
the named `CUOTA_LESS_M303_IVA_CATEGORIES` frozenset — never by an inline literal.

The advisory exists to surface declarable IVA that no binding consumes. It once
false-fired on categories bearing no cuota by law, which legitimately match no
cuota binding — noise that trains operators to ignore the alert. The advisory
only earns trust if every fire is a genuine unrouted cuota.

## How

- **Good:** a declarable category that should route a cuota but has no binding
  yet fires the advisory until its binding lands.
- **Good:** an exempt, zero-rated, not-subject, exempt-supply, triangulation or
  simplificado observation is a member of the cuota-less set and never fires.
- **Bad:** flagging an exempt entrega intracomunitaria or an export as "unrouted
  declarable IVA" — it is base-only with no cuota.
- **Bad:** silencing a genuine unrouted reverse-charge or import cuota by adding
  it to the cuota-less set. It bears a real cuota; route it instead.

Source: ADR `2026-06-09-modelo-iva-routing-carry-adr`. Companions:
`no-silent-under-declaration`, `aeat-calculation-grounding`.
