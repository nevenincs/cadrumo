---
tags:
  - '#adr'
  - '#modelo-100-anualidades-separate-escala'
date: '2026-07-01'
modified: '2026-07-03'
body_hash: 'sha256:5f181ecf52c0eccb1571a6393f6035ad52917642b7558f8fe4abdd58f030bfbe'
related:
  - "[[2026-07-01-modelo-100-anualidades-separate-escala-research]]"
---

# `modelo-100-anualidades-separate-escala` adr: `Modelo 100 anualidades por alimentos separate-escala determination` | (**status:** `accepted`)

## Problem Statement

The Modelo 100 cuota-integra chain models the anualidades por alimentos a favor
de los hijos satisfechas por decision judicial (casilla 0527) benefit partially
and incorrectly across revisions 2020-2025, producing a confirmed silent
under-declaration (issue #532). LIRPF art. 64 (estatal) and art. 75 (autonomica)
grant these amounts a SEPARATE-escala treatment: the progressive escala is applied
separately to the anualidades and to the rest of the base liquidable general, the
minimo personal y familiar is increased by 1.980 EUR before its escala is
subtracted, and the result is floored at 0. The registry instead subtracts the
anualidades from the base (0505 = max(0, 0500 - 0527) in 2024/2025) and applies a
single escala -- it never re-applies the escala to the anualidades, omits the
+1.980 increment, and applies no floor. In 2020-2023 the regime is not modelled at
all (0505 is a manual input). An interim non-blocking ADVISORY
(advisory_when_positive on 0527, commit 3aaf44f15) was landed on 2024/2025 as the
no-silent-under-declaration safeguard; it does not correct any cuota. This ADR
decides the full determination and the retirement of that interim advisory.

## Considerations

- aeat-safety-legal-gates and registry-calculation-legal-grounding: the value and
  its conditions must be grounded in the binding provisions (art. 64/75, escala of
  art. 63/74, +1.980) which are present verbatim in the bundled consolidated LIRPF
  (ley-35-2006.html); the casilla-level wiring is grounded in the AEAT Renta manual.
- no-silent-under-declaration: the current chain grants a numerically wrong (too
  low) cuota with no operator signal beyond the interim advisory; the fix must make
  the correct figure computed, not merely advised.
- The formula runtime already provides if_then_else, the comparison ops, multiply
  (as boolean AND of 1/0 factors), lookup_bracket, and lookup_bracket_by_ccaa -- no
  new runtime op is required (see research).
- The separate-escala regime is CONDITIONAL. When it does not apply (no
  anualidades, anualidades >= base, or the payer retains the minimo por
  descendientes for those hijos) the chain must reduce to the ordinary
  escala(base) - escala(minimo).
- The gating condition "sin derecho al minimo por descendientes por esos hijos" is
  a per-filing fact not derivable from other casillas; it needs a new modelled
  input.
- Cross-revision integrity: casilla legal_refs, the cuota construct, and the
  previous_filing / per-source bindings must be swept coherently per revision (the
  registry validator enforces construct-covers-member-and-binding refs).

## Considered options

- Option A -- Conditional wiring on the existing cuota casillas (CHOSEN). Keep 0505
  as the full base liquidable general; make 0528/0529/0530/0531 if_then_else on a
  regime predicate; floor 0532/0533 at max(0, ...). Pros: preserves the official
  casilla semantics (0528 = escala s/ base, 0530 = escala s/ minimo), reuses the
  existing escala parameters, and the else-branch is byte-identical to today. Cons:
  each of the four escala formulas grows a conditional; 0505 must be reverted /
  built per revision.
- Option B -- New intermediate casillas for escala(anualidades) and the +1.980
  minimo. Introduce dedicated casillas outside the official form to hold the
  separate terms. Rejected: invents non-official casillas (modelo-export mirrors
  official structure), fragments the chain, and still needs the same predicate.
- Option C -- Keep the 0505 = base - anualidades shortcut and only add the missing
  escala(anualidades) and +1.980 as correction terms. Rejected: preserves a base
  casilla whose value contradicts its official definition, and the correction
  algebra is less faithful and harder to verify against the manual than the
  separate-escala form the law states.
- Option D -- Leave the interim advisory as the permanent safeguard, do not
  compute. Rejected: no-silent-under-declaration is a floor, not a ceiling; a
  computed regulated figure is mandated (aeat-calculation-grounding), and the
  advisory cannot produce the correct cuota.

## Constraints

- Depends on the state-scale wiring already landed (renta-cuota-integra-state-scale
  research, escala-estatal parameters) and the lookup_bracket_by_ccaa autonomic
  dispatch; both are stable and in production. No frontier or immature dependency.
- The 2020-2023 revisions have no computed 0505 sub-chain; building it (0505 from
  0500, then the escala targets) is a precondition for the conditional wiring in
  those years and widens the per-revision change surface.
- The new gating input must be a typed input with a real capture path (profile
  field or manual-input casilla); shipping a binding with no operator-reachable
  source would be a design-only shell (aeat-source-hygiene).
- External numeric authority for the test is the AEAT Renta manual worked example /
  live oracle; the ordering property (shortcut < correct < no-benefit) is the
  non-tautological structural anchor. No hand-computed expected values.
- 2020 is in the same defective family though issue #532 names 2021-2025; the plan
  must fold it in or explicitly defer it (plan-closure honesty).

## Implementation

Model the art. 64/75 separate-escala regime as a conditional applied at the
existing cuota-escala casillas, per revision 2020-2025.

Regime predicate (a 1/0 value), reused by the state and autonomic branches:
multiply( greater_than(0527, 0), less_than(0527, 0505), no_minimo_descendientes_flag ).
The product is non-zero iff all three hold; if_then_else treats non-zero as true.

State branch:
- 0528 = if_then_else(regime, add(escala63(0527), escala63(0505 - 0527)), escala63(0505)).
- 0530 = if_then_else(regime, escala63(0521 + 1.980), escala63(0521)).
- 0532 = max(0, 0528 - 0530) -- the "sin que pueda resultar negativa" floor,
  harmless in the ordinary case where 0528 >= 0530 always.

Autonomic branch mirrors with lookup_bracket_by_ccaa and the art. 74 escala, the
autonomic minimo 0523 (which already carries the art. 56.3 adjustments), and the
same +1.980 and floor at 0533.

0505 reverts to (2024/2025) or is built as (2020-2023) the full base liquidable
general with NO anualidades subtraction (max(0, 0500)); the anualidades enter only
through the separate-escala term inside the regime branch. All seven 0505 consumers
continue to want the full base.

The gating fact is a new input binding renta-{year}-...-anualidades-sin-derecho-
minimo-descendientes (recommended shape: a source = "profile" boolean binding
alongside the existing renta-{year}-profile-descendientes-* family, or a
data_type = "boolean" manual-input indicator casilla), yielding the 1/0 flag.
Grounded in art-58 (the minimo it negates) plus art-64. It must be enrolled in the
cuota construct and its legal_refs swept with the casillas and bindings it joins.

Grounding: the escala parameters, +1.980, the two conditions, and the floor are
grounded in the bundled ley-35-2006.html (arts 64, 75, 63, 74, 58); the
casilla-level assignment (which casilla holds the summed escala, which holds the
+1.980 minimo escala) is grounded in aeat-renta-2024-manual-parte1. Existing
formula source_citations (required_text "anualidades por alimentos a favor de los
hijos", "resto de la base liquidable general") already assert the corpus text.

Test strategy (no-tautological-calculation-tests): assert the ordering
current-shortcut < correct-separate-escala < single-escala-no-benefit for the
worked profile, pin the exact correct cuota to an AEAT manual / live-oracle value,
and update the existing test_anti_tautology_anualidades_changes_cuota (which
currently encodes the 602,87 shortcut value and would otherwise lock in the
defect). Add regime-off cases proving reduction to the ordinary chain: no
anualidades, anualidades >= base, and flag off (payer keeps minimo descendientes).

Advisory retirement: remove advisory_when_positive on 0527 from a revision only
when that revision computes the full determination; the compute supersedes the
mechanical follow-up that would have added the advisory to 2020-2023.

## Rationale

Option A is chosen because it is the most faithful mapping of the law text onto
the official form the registry mirrors: art. 64 states the escala is applied
separately and the total is minorada by the escala of the minimo + 1.980, floored
at 0 -- exactly 0528 (the summed escala), 0530 (the +1.980 minimo escala), and the
0532 floor. The else-branch is byte-identical to the current ordinary chain, so the
change is scoped to anualidades filers who meet the statutory conditions, and
regime-off filers are provably unaffected. The runtime already expresses every
operator needed (research: if_then_else, comparison ops, multiply-as-AND,
lookup_bracket[_by_ccaa]), so no engine change is required. The direction of the
correction (raising the cuota over the shortcut while staying below the no-benefit
single escala) is grounded in the worked example and confirms both the
under-declaration and the reality of the benefit.

## Consequences

- Good: the regulated cuota becomes correct and computed for anualidades filers who
  qualify; the silent under-declaration is closed at the value, not merely advised.
- Good: the interim advisory can be retired per revision as the compute lands,
  removing a standing "review the cuota manually" prompt.
- Good: a reusable gating-input pattern (profile/manual boolean flag feeding a
  multiply-AND predicate) is established for future conditional regimes.
- Neutral/cost: filers who declared anualidades but retain the minimo por
  descendientes for those hijos (regime off) will now be taxed on the full base
  with no anualidades reduction -- correct per art. 64, but a behaviour change from
  the current shortcut that always reduced the base. This must be communicated as
  the intended correction, not a regression.
- Cost: the 2020-2023 revisions require building the 0505->0532 computed sub-chain
  before the conditional can be wired, widening the change surface; the new gating
  input requires a real capture path in the profile/CLI surface.
- Pitfall: the +1.980 minimo escala input (0521 + 1.980) may exceed 0505 in edge
  cases; the manual-grounded cap behaviour must be confirmed during implementation.
- Pitfall: a coherent per-revision sweep of casilla/construct/binding legal_refs is
  required or the registry fails to load; each revision lands as one atomic change.
