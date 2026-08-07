---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration; evidence and oracles must be real

## The gate must not grant completeness over an under-declaration

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a
draft that under-declares. Whenever a positive economic input is declared
(resultado contable, rendimiento de módulos, ingresos) but the dependent base or
cuota resolves to zero and no offsetting reduction is declared, the gate MUST
surface at least an ADVISORY finding.

A human files outside the application, so an explicit operator-facing alert —
never a silent grant — is the minimum safeguard against filing a zero-tax return
on positive activity. A verify gate once granted completeness for a sociedad with
substantial resultado contable but zero base and zero cuota, because base
imponible was a bare manual input with no derivation.

**Watch the unwatched direction too.** This apparatus is built against
under-declaration; nothing in it watches a taxpayer over-paying, and that
direction produces valid output, no refusal and no signal to the taxpayer. When
auditing a chain, deliberately probe the opposite direction — the structural tell
is a **restrictive provision used as a default**, which silently captures the
population the limiting article does not govern.

## Grounding claims need a bundled oracle AND engine reproduction

A casilla listed in a verification expectation's
`externally_grounded_casilla_ids` MUST be backed by a bundled AEAT-authoritative
oracle payload carrying the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or a manual worked-example oracle under
`corpus/manual_oracles/`, keyed by `expected_by_casilla_id`), AND the registry
engine MUST independently reproduce that figure in a parity test.

Never fabricate a grounding figure, never hand-compute it from the registry
formula under test, and never declare the ids without both.

**Enrollment in a verification expectation is NOT grounding.** Enrollment only
reconciles filed-versus-engine; grounding is the stronger claim that the engine
value is checked against an independent AEAT authority. A value reconciled only
against the app's own engine cannot catch a systematic engine error the filing
matches.

**The oracle must follow the fix, never precede it.** Building an oracle that
asserts a currently-wrong figure converts a live defect into verified behaviour
behind an AEAT-branded test name, which is harder to find later than the open
gap. Never force a figure with an override reaching beneath a guard every real
filing passes through — a fixture proving a chain works in a configuration no
filing can reach reads as coverage.

## Suppression is grounded in registry classification, never the schedule

A cross-period dependency may be scoped out of the clean-state gate as
not-applicable ONLY on a registry signal on that dependency's own
`DependencyClassificationDefinition`: `taxpayer_files_source = false` (suffered
retenciones), or `conditional_on_economic_activity = true` combined with a
**fail-closed** `taxpayer_files_economic_activity is False` (pagos fraccionados).

The suppression set MUST derive from `snapshot.revision.dependency_classifications`,
never from the deadline-engine obligation schedule — the schedule is an
INCOMPLETE signal that over-suppresses other targets' enforced sources. A taxpayer
who DOES file the source, and the undeclared case, stay enforced.

## Local-filed observations are non-official evidence

Observations persisted by the local `file` flow MUST carry a non-official
`source_kind` (`app_filing`) and MUST NEVER be added to
`_OFFICIAL_SOURCE_KINDS` — the set satisfying the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`).

Automatic cross-period carry may feed calculate and draft from these
observations, but they must never substitute for external AEAT filing evidence. A
same-filing-year local chain may reach local verify and export ONLY when the
chain is present, value-consistent, revision-confirmed, and its only blockers are
the official-evidence delta — and that path MUST surface a non-blocking
non-official-local-chain advisory and MUST NOT assert AEAT acceptance. Cross-year
priors, operator-manual sources, missing data and value or revision divergence
remain blocking.

## How

- **Good:** the revision declares an ADVISORY `verification_predicate` such as
  `implies_nonzero([...])`. It holds trivially when the antecedent is at or below
  zero (no false positive on losses) and fires only when the antecedent is
  strictly positive and the consequent zero, surfacing a non-blocking WARNING
  grounded with `legal_refs`.
- **Good:** an id is declared grounded only after the bundled oracle carries the
  AEAT literal figure with a raw-evidence locator AND a test proves the engine
  independently computes it. Where a manual states contradictory figures, ground
  on the one it states repeatedly and the engine re-derives bottom-up, and
  document the discrepancy.
- **Good:** a suffered-retencion source marked `taxpayer_files_source = false`
  scopes out as a **visible** not-applicable advisory, never silently.
- **Good:** the local filing path stamps `source_kind="app_filing"`, and a
  regression asserts `app_filing not in _OFFICIAL_SOURCE_KINDS`.
- **Bad:** shipping a manual base or result casilla with no derivation and no
  guard, so the gate grants completeness on positive input.
- **Bad:** a blocking rule refusing legitimate positive-result/zero-base filings
  (negative result, full loss compensation, exemptions) — the guard must
  distinguish the suspicious case and stay advisory while legitimate zero-base
  cases exist.
- **Bad:** adding a grounded id because the engine emits a plausible value, with
  no bundled oracle; or authoring an expected figure by copying the registry
  formula's own output.
- **Bad:** scoping out because the source modelo is missing from the
  deadline-engine schedule; or suppressing on an undeclared profile signal, which
  fails open.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS`.

Gate: `test_external_oracle_grounding_enrolled.py`. Source: ADRs
`2026-06-02-modelo-200-base-determination-adr`,
`2026-07-01-verification-power-adr`,
`2026-06-19-m100-dependent-modelo-applicability-adr`,
`2026-06-09-modelo-iva-routing-carry-adr`.
