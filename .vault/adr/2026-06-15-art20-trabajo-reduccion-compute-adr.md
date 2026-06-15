---
tags:
  - '#adr'
  - '#art20-trabajo-reduccion-compute'
date: '2026-06-15'
modified: '2026-06-15'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace art20-trabajo-reduccion-compute with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `art20-trabajo-reduccion-compute` adr: `Modelo 100 art. 20 work-income reduction: computed vs advisory` | (**status:** `accepted`)

## Problem Statement

Modelo 100 casilla `0023` ("Cuantía aplicable con carácter general") is the
reducción por obtención de rendimientos del trabajo of LIRPF art. 20. The legal-
grounding campaign corrected its `legal_refs` (art-17 → art-20, audit V8) but the
casilla remains a MANUAL input: the operator transcribes the figure the AEAT program
computes. This is the residual frontier item the centralization audit repeatedly
flagged. The reduction is a piecewise-linear function of the rendimiento neto del
trabajo (casilla `0022`) GATED by an eligibility condition on the rest of the return,
and `no-silent-under-declaration` warns that a partially-modelled calc chain that
leaves a determinable value as a bare manual input can file an under-declared return
with zero operator signal. This ADR decides how `0023` should be modelled.

## Considerations

The art. 20 schedule (verified this campaign against the bundled `ley-35-2006.html#a20`
and the AEAT 2024 manual §7.1.6, RDL 4/2024 art. 3.1 / BOE-A-2024-12944):

- rendimiento neto del trabajo (RNT, `0022`) ≤ 14.852 €: reduction = 7.302 €;
- 14.852 < RNT ≤ 17.673,52: 7.302 − 1,75 × (RNT − 14.852);
- 17.673,52 < RNT < 19.747,5: 2.364,34 − 1,14 × (RNT − 17.673,52);
- RNT ≥ 19.747,5: 0;
- AND the reduction applies ONLY if "otras rentas, excluidas las exentas, distintas de
  las del trabajo" ≤ 6.500 €.

The piecewise function of `0022` is fully determinable in-engine. The eligibility GATE
is not: "otras rentas" is a derived aggregate of the WHOLE rest of the return (capital
mobiliario/inmobiliario, actividades, ganancias) — a forward/cross-section dependency on
casillas not necessarily resolved at the point `0023` evaluates in the rendimiento-neto
chain. The schedule changes per ejercicio (RDL 4/2024 raised it for 2024-2025), so any
codified figure rides the registry per-revision, not a Python literal
(`aeat-schema-central-config`).

## Constraints

Parent-feature stability: the registry calculation engine is currently in flux — a peer
`bindings-interface-hardening` refactor (`BindingAggregationOp`) has the registry in a
non-loading state at authoring time, so implementation and gate-verification of any new
formula/binding are BLOCKED until that lands. The "otras rentas ≤ 6.500" aggregate would
need a cross-section aggregation resolver enrolled in the live calculate mesh
(`no-dormant-source-resolvers`), which is exactly the surface the peer refactor touches.
No external numeric oracle beyond the AEAT manual exists for a synthetic case, so any
calc test must be schedule-derived from the manual, never hand-computed from the same
formula (`no-tautological-calculation-tests`).

## Implementation

Two-phase, advisory-first:

- **Phase 1 (advisory — unblocked once the registry loads, no cross-section resolver).**
  Add an ADVISORY `verification_predicate` to the M100 revision: when RNT (`0022`) is in
  the reduction-eligible range (≤ 19.747,5 € and > 0) AND the manual `0023` is zero,
  surface a non-blocking advisory ("posible reducción del art. 20 no aplicada; verifique
  si sus otras rentas no superan 6.500 €"), grounded with `legal_refs = ["ley-35-2006:art-20"]`.
  The predicate stays ADVISORY (not blocking) precisely because the engine cannot see
  "otras rentas" — a legitimately-zero reduction (otras rentas > 6.500) must remain
  permissible. This is the same shape the M200 base-determination advisory uses.

- **Phase 2 (computed — gated on the cross-section aggregation surface).** Once an
  "otras rentas distintas del trabajo" aggregate is computed in the engine (it is needed
  by other determinations too), flip `0023` to a COMPUTED casilla whose formula applies
  the piecewise schedule to `0022` conditioned on that aggregate ≤ 6.500, with the
  schedule parameters authored in the registry per revision. At that point the advisory
  predicate is upgraded to a `BLOCKING_RULE` consistency check between the computed and
  any entered value, or retired.

## Rationale

Advisory-first respects `no-silent-under-declaration` (a determinable reduction left at
zero on eligible income gets an operator signal) WITHOUT the false-positive risk a
blocking rule would carry (it cannot prove ineligibility, so it must not refuse a
legitimate zero). It is implementable as soon as the registry loads, independent of the
cross-section aggregation work, so it delivers the safety value now and defers the
heavier compute behind the aggregate it genuinely needs — matching the campaign's
incremental, verify-before-ship discipline. Full compute is the correct end state but is
gated on a resolver that the in-flight engine refactor must stabilise first.

## Consequences

Gains: closes the silent-under-declaration gap on the highest-volume IRPF reduction with
a low-risk, registry-grounded advisory; documents the verified schedule for the eventual
compute. Difficulties: Phase 2 depends on a cross-section "otras rentas" aggregate that
does not yet exist and on the engine refactor stabilising; the eligibility gate's
forward dependency is a genuine ordering problem the aggregate resolver must solve.
Pitfalls: shipping a BLOCKING rule in Phase 1 would refuse legitimate otras-rentas>6.500
filings — the advisory severity is load-bearing and must not be tightened until the
aggregate is real.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
