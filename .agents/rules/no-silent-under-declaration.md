---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Rule

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a draft
that under-declares: whenever a positive economic input is declared (resultado contable,
rendimiento de módulos, ingresos) but the dependent base or cuota resolves to zero and
no offsetting reduction is declared, the gate MUST surface at least an ADVISORY finding.
A human files outside the application, so an explicit operator-facing alert — never a
silent grant — is the minimum safeguard against filing a zero-tax return on positive
activity.

## Why

Round-30 CLI persona testimonials and a coordinator reproduction found the M200 verify
gate returned `granted_verificado_completo = true, finding_count = 0` for a sociedad
with resultado contable €140.000 but base imponible `DP200014:00552 = 0` and cuota
`DP200014:00562 = 0` — the root cause a partially-modelled chain (base imponible a bare
manual input with no derivation from resultado contable). The durable fix models the
determination so a zero base is computed; until then the gate must alert. The shape
recurs across partially-modelled engines (M131 objetiva rendimiento, multi-row
informativas), so the discipline is project-wide. ADR
`2026-06-02-modelo-200-base-determination-adr`; round-30 testimonial audit.

## How

- **Good:** the M200 revision declares an ADVISORY `verification_predicate`
  `implies_nonzero(["00501", "DP200014:00552"])`; the evaluator holds trivially when the
  antecedent is ≤ 0 (no false positive on losses) and fires only when the antecedent is
  strictly positive and the consequent zero, surfacing a non-blocking WARNING
  (legitimately zero base via BIN compensation or correcciones stays permissible),
  grounded with `legal_refs`. Once the engine computes the value, the advisory can be
  upgraded to a `BLOCKING_RULE` computed-vs-entered consistency check, or retired.
- **Bad:** shipping a manual base/result casilla with no derivation and no guard so the
  gate grants `verified_complete` with `finding_count = 0` on positive input; or a
  `BLOCKING_RULE` that refuses legitimate positive-result/zero-base filings (negative
  result, full BIN compensation, exemptions) — the guard must distinguish the suspicious
  case (positive antecedent, zero consequent) and stay advisory while legitimate
  zero-base cases exist.

## Source

ADR `2026-06-02-modelo-200-base-determination-adr` (Phase 1); audit
`2026-06-02-cli-persona-testimonials-round-30-audit`; worked example `414fd3529`.
