---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Rule

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a
draft that under-declares: whenever a positive economic input is declared (e.g.
resultado contable, rendimiento de módulos, ingresos) but the dependent base or
cuota resolves to zero and no offsetting reduction is declared, the gate MUST
surface at least an ADVISORY finding. A human files outside the application, so an
explicit operator-facing alert — never a silent grant — is the minimum safeguard
against filing a zero-tax return on positive activity.

## Why

Round-30 CLI persona testimonials and a coordinator reproduction found that the
Modelo 200 verify gate returned `granted_verificado_completo = true,
finding_count = 0` for a sociedad with resultado contable €140.000 but base
imponible `DP200014:00552 = 0` and cuota `DP200014:00562 = 0` — a silent
under-declaration the gate could not surface. The root cause was a calculation
chain modelled only partway (the base imponible casilla is a bare manual input
with no derivation from the resultado contable), so a positive-result filer who
does not also enter the base files zero. The durable fix is to model the
determination so a zero base is computed, not silently omitted; until that lands,
the gate must at least alert. See ADR `2026-06-02-modelo-200-base-determination`
and the round-30 testimonial audit. The same shape recurs across modelos whose
engines are partially modelled (M131 estimación objetiva rendimiento, multi-row
informativas), so the discipline is project-wide, not M200-specific.

## How

- **Good (worked example):** the Modelo 200 revision declares an ADVISORY
  `verification_predicate` `implies_nonzero(["00501", "DP200014:00552"])`. The
  `implies_nonzero` evaluator holds trivially when the antecedent is ≤ 0 (no false
  positive on losses) and fires only when the antecedent is strictly positive and
  the consequent is zero. As ADVISORY it surfaces a non-blocking WARNING (a
  legitimately zero base via BIN compensation or correcciones remains permissible)
  while making the under-declaration non-silent. Grounded with `legal_refs`.
- **Good:** when a calculation engine is later completed so the dependent value is
  computed (not manual), the silent-zero becomes impossible and the advisory can be
  upgraded to a `BLOCKING_RULE` consistency check between computed and entered
  values, or retired.
- **Bad:** shipping a partially-modelled calc chain (a manual base/result casilla
  with no derivation and no guard) so the verify gate grants `verified_complete`
  with `finding_count = 0` on positive economic input — the operator gets no signal
  that the return under-declares.
- **Bad:** using a `BLOCKING_RULE` guard that refuses legitimate
  positive-result/zero-base filings (negative result, full BIN compensation,
  exemptions). The guard must distinguish the suspicious case (positive antecedent,
  zero consequent) and stay advisory while legitimate zero-base cases exist.

## Source

ADR `2026-06-02-modelo-200-base-determination-adr` (Phase 1); round-30 CLI
testimonial audit `2026-06-02-cli-persona-testimonials-round-30-audit`; worked
example commit `414fd3529`. Promoted per the `vaultspec-codify` discipline.
