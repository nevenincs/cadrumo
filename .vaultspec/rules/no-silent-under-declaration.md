# No silent under-declaration

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a
draft that under-declares. Whenever a positive economic input is declared
(resultado contable, rendimiento de módulos, ingresos) but the dependent base or
cuota resolves to zero and no offsetting reduction is declared, the gate MUST
surface at least an ADVISORY finding.

A human files outside the application, so an explicit operator-facing alert —
never a silent grant — is the minimum safeguard against filing a zero-tax return
on positive activity.

A verify gate once returned `granted = true, finding_count = 0` for a sociedad
with substantial resultado contable but a zero base imponible and zero cuota, the
root cause being a partially-modelled chain where base imponible was a bare
manual input with no derivation. The shape recurs across partially-modelled
engines, so the discipline is project-wide.

## How

- **Good:** the revision declares an ADVISORY `verification_predicate` such as
  `implies_nonzero([...])`. It holds trivially when the antecedent is at or below
  zero (no false positive on losses) and fires only when the antecedent is
  strictly positive and the consequent zero, surfacing a non-blocking WARNING
  grounded with `legal_refs`. Once the engine computes the value, the advisory
  can be upgraded to a blocking computed-versus-entered consistency check.
- **Bad:** shipping a manual base or result casilla with no derivation and no
  guard, so the gate grants completeness on positive input.
- **Bad:** a blocking rule that refuses legitimate positive-result/zero-base
  filings (negative result, full loss compensation, exemptions). The guard must
  distinguish the suspicious case and stay advisory while legitimate zero-base
  cases exist.

**Watch the unwatched direction too.** This apparatus is built against
under-declaration; nothing in it watches a taxpayer over-paying, and that
direction produces valid output, no refusal, and no signal to the taxpayer. When
auditing a chain, deliberately probe the opposite direction — the structural tell
is a **restrictive provision used as a default**, which silently captures the
population the limiting article does not govern.

Source: ADR `2026-06-02-modelo-200-base-determination-adr`.
