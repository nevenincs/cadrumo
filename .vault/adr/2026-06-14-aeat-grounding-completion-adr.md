---
tags:
  - '#adr'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-29'
related:
  - '[[2026-06-14-aeat-grounding-completion-research]]'
  - "[[2026-06-14-legal-grounding-centralization-audit]]"
---

# `aeat-grounding-completion` adr: `Build Legitimately-Missing Spanish-Tax Grounding Features` | (**status:** `accepted`)

## Problem Statement

The legal-grounding verification swarms confirmed the codebase's regulatory figures are
overwhelmingly correct and centralized, but surfaced a class of findings that are not
wrong values or mis-placed literals — they are LEGITIMATELY MISSING FEATURES: real
Spanish-tax law the application should model but currently does not. Operator directive
(2026-06-14): the grounding campaign is a multi-day effort, and where a feature is
legitimately missing it is IN SCOPE to BUILD it (not merely track it as a gap). This
ADR records the decision to build the identified missing grounding features and the
per-gap approach, grounded against BOE/AEAT sources.

## Considerations

The missing features differ in kind and risk: (a) missing registry DATA/law that a
gate would consume (the estimación-objetiva módulos magnitude-exclusion limits; the IS
Entidad de Reducida Dimensión INCN<10M transitional schedule) — low-risk registry
authoring with clear legal basis; (b) a display-echo limitation where the underlying
tax is already correct (the M200 casilla 00558 two-tranche micro-empresa rate echo) —
must not regress the correct cuota; (c) dormant/duplicate aggregation routing already
tracked in the centralization plan's phase P03 (M303 casilla 59/60 base bindings, the
compensación casilla routing, prorrata-subsystem enrollment) — those stay in that plan.
Every authored value MUST carry its binding provision per `registry-calculation-legal-
grounding`, and every gate must be advisory-first per `no-silent-under-declaration`
where a hard block could refuse a legitimate filing.

## Constraints

These are regulated tax surfaces: a wrong authored value or an over-strict gate is the
exact harm the campaign prevents, so each build lands only with BOE-grounded values,
corpus cross-checks where a corpus text exists, and real-behaviour tests (no
tautologies). The módulos limits depend on the existing estimación-objetiva regime
selection (`IrpfEstimationRegime`); the IS schedule depends on the existing M200
registry parameter/bracket structure. Both parent surfaces are stable. The work is
incremental and independently landable per gap — no single large irreversible change.

## Implementation

Wave-structured, one gap-cluster per wave. **W01 módulos exclusion limits:** author the
DT 32ª in-force magnitudes — 250.000 € general rendimientos íntegros, 125.000 €
operaciones con obligación de factura (destinatario empresario), 250.000 € agrícolas/
ganaderas/forestales, 250.000 € volumen de compras — as grounded registry parameters
(legal_refs `ley-35-2006:art-31`, `ley-35-2006:dt-32`, the annual Orden de módulos),
plus an advisory gate that surfaces a `Notice` when a declared volume exceeds a limit
(módulos exclusion is operator-consequential but self-declared, so advisory-first).
**W02 IS rate-surface gaps:** add the true ERD (INCN<10M, LIS art. 101) DT 44ª schedule
24%(2025)/23%(2026)/22%(2027)/21%(2028) as a registry parameter distinct from the
mis-named micro-empresa "erd" scalar, and land the deferred bracket-based casilla-00558
rate echo so the displayed micro-empresa rate reflects the two-tranche scale for
2025/2026 instead of the stale flat 23%. Each wave is its own grounded, tested landing.

Current-state note 2026-06-29: W01 and W02 have landed in the current tree. The
objective-estimation advisory consumes structured profile volume fields and the
objective-estimation selector is enum-only through `irpf.estimation_regime`; the legacy
`uses_objective_estimation_irpf` boolean input is not a supported path. Modelo 131
deadline-window predicates also use `irpf.estimation_regime == "objetiva"`. The Modelo
200 Art.101 ERD schedule is encoded separately from the micro-empresa lane, and the
casilla 00558 display echo is closed without weakening the bracket-derived cuota path.

## Rationale

Per the operator directive, a verified missing feature is in scope to build, not defer.
The registry is the authority (`aeat-schema-central-config`, `aeat-registry-authority-
flow`), so the missing law is authored there with grounding the existing gates enforce.
Advisory-first gating follows `no-silent-under-declaration` (surface the risk) without
the over-block risk a hard refusal carries on a self-declared regime. Sequencing the
low-risk registry-data builds (módulos, ERD schedule) before the display-echo change
keeps the correct cuota untouched while the safe wins land.

## Consequences

Gains: the application gains real filing-obligation gates it lacked (a taxpayer who
exceeds the módulos volume is now alerted rather than silently mis-gated), the IS ERD
INCN<10M lane gains its transitional rates, and the M200 rate echo stops displaying a
stale figure. Honest difficulty: the módulos magnitudes are self-declared inputs the
app may not yet collect, so the gate's antecedent (declared volume) may need a new
profile/ledger input to be fully live — the advisory fires only when the input exists,
and W01 must say so rather than imply full coverage. The M200 echo change touches a
regulated display casilla and must prove the cuota is unchanged. The broader campaign
(all Spanish-tax concepts) continues beyond these waves; this ADR covers the gaps the
two verification swarms surfaced, and later swarms will surface more.

2026-06-29 outcome: the gains above are present as current code/registry behavior, with
the módulos limit implemented as advisory verification findings rather than a hard filing
block. The remaining discipline is ongoing campaign hygiene: future legal surfaces must
still be introduced through grounded registry parameters or explicit non-authoritative
anchors, not by carrying secondary-source text as corpus.

## Codification candidates

- **Rule slug:** `missing-regulatory-law-is-built-in-the-registry`. **Rule:** when a
  verification pass finds a real Spanish-tax provision the application should model but
  does not, author it as a grounded registry parameter (legal_refs→corpus_ref) with an
  advisory-first gate — do not leave it as a corpus-only reference or an un-enforced
  comment. (Promote only after this ADR's waves land and the pattern holds.)
