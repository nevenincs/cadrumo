---
tags:
  - '#adr'
  - '#modelo-100-trabajo-casilla-compute'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - '[[2026-07-01-modelo-100-trabajo-casilla-compute-research]]'
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
---

# `modelo-100-trabajo-casilla-compute` adr: `Modelo 100 trabajo-casilla auto-apply and cap: computed vs advisory` | (**status:** `accepted`)

## Problem Statement

Three Modelo 100 rendimientos-del-trabajo determinations that AEAT applies or caps
automatically are modelled as bare MANUAL inputs or unclamped formulas, so a filer who
leaves a box blank or over-enters a value is mis-taxed with zero operator signal
(no-silent-under-declaration):

- Casilla 0019, the art. 19.2.f LIRPF automatic EUR 2.000 "otros gastos" deduction, is a
  bare MANUAL input in every revision 2021-2025. A blank 0019 OVER-taxes by omitting a
  determinable EUR 2.000 deduction (issue #568).
- The net-trabajo formula 0022 = sum(0018, -0019, -0020, -0021) has no max(0,...) clamp,
  and the art. 19.2.f letter-f cap (the sum of 0019/0020/0021 limited to the rendimiento
  0018) is unenforced. An over-entry drives 0022 negative (issue #568).
- Casilla 0468, the previsión-social reducción, applies the EUR 10.000 combined cap
  (min(0467, 10000, 30% of 0432)) but not the art. 52 EUR 1.500 individual sub-limit that
  binds purely-individual contributions with no plan-de-empleo/employer backing - a
  potential OVER-reduction / under-tax (issue #574 followup).

The accepted `2026-06-15-art20-trabajo-reduccion-compute-adr` already decided this exact
shape for casilla 0023 (art. 20 reducción): advisory-first, compute-flip deferred. This
ADR decides how these three trabajo-net / previsión-social-cap gaps are modelled.

## Considerations

Figures verified verbatim against the bundled consolidated LIRPF
`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html`:

- art. 19.2.f (anchor a19): "En concepto de otros gastos distintos de los anteriores,
  2.000 euros anuales", the +2.000 mobility increment (desempleado que acepta traslado,
  casilla 0020), the +3.500 / +7.750 disability increments (casilla 0021), and the
  letter-f cap "tendran como limite el rendimiento integro del trabajo una vez minorado
  por el resto de gastos deducibles" (= casilla 0018).
- art. 52.1 (anchor a52): joint limit = "la menor de: a) El 30 por 100 ...; b) 1.500
  euros anuales", incremented by "En 8.500 euros anuales, siempre que tal incremento
  provenga de contribuciones empresariales, o de aportaciones del trabajador al mismo
  instrumento de previsión social". The legal-catalogue entries ley-35-2006:art-19 and
  ley-35-2006:art-52 already exist, corpus-grounded and reviewed.

Determinability differs across the three gaps. The EUR 2.000 (0019) is unconditionally
determinable from "has rendimientos del trabajo" - no cross-section dependency. The letter-f
cap / max(0) on 0022 is a pure in-formula clamp over already-resolved casillas - fully
determinable now. The art. 52 EUR 1.500 sub-limit is NOT cleanly determinable: casilla 0463
mixes individual and empresarial aportaciones in one box, so the individual-only amount is
not a single readable casilla; only the ABSENCE of the plan-de-empleo/employer boxes
(0426 = 0 AND 0427 = 0) is a reliable discriminator, and the exact 8.500 increment carries
its own sub-table (the cuadro of worker-contribution proportions).

The two sibling increment boxes 0020 (mobility) and 0021 (disability) are genuinely
conditional on taxpayer facts the engine cannot assert and MUST stay MANUAL. The schedule
figures ride the registry per revision, not Python literals (aeat-schema-central-config).

## Considered options

- **Advisory-first, two-phase, per gap (CHOSEN).** Phase 1 emits non-blocking ADVISORY
  findings for each gap; Phase 2 flips the determinable pieces to COMPUTED. Mirrors the
  accepted art-20 precedent exactly, delivers the safety signal immediately, and defers the
  hard individual/employer split behind the data it needs. Kept.
- **Flip everything to COMPUTED immediately.** Correct end state for 0019 and the 0022
  clamp, but for the art. 52 sub-limit it is not safely computable today (the 0463
  individual/empresarial box mix + the 8.500 cuadro), and flipping 0019 to COMPUTED trips
  the Diseño-de-Registros parity gate (AEAT lists 0019 as INPUT) which needs the same
  parity treatment art-20 used - heavier, and blocked while the parity/engine surface is in
  flux. Rejected as a single step; folded into Phase 2.
- **BLOCKING rule instead of advisory.** A blocking predicate on 0019 = 0 or on the art. 52
  over-reduction would refuse legitimate filings (a taxpayer who genuinely enters 0019
  elsewhere, or a legitimate employer-backed 10.000 reducción). Rejected: severity must stay
  advisory until the value is actually computed, per no-silent-under-declaration's
  false-positive caution.
- **Split the two concerns into two ADRs (trabajo-net vs previsión-social).** They share the
  trabajo surface, the advisory mechanism, the manual/worked-example test strategy, and the
  art-20 precedent; one ADR keeps the decision coherent. The Considerations already flag that
  Gap C's Phase 2 is independently gated. Rejected as needless fragmentation.
- **Do only the 0022 max(0) clamp (the safe, no-cross-section piece) and nothing else.**
  Under-scopes: leaves the #568 EUR 2.000 auto-apply and the #574 over-reduction unaddressed.
  Rejected; the clamp is Phase 2a within this ADR.

## Constraints

- **Locale corruption blocks Phase 1 prose.** New advisory findings need locale keys, and
  the locale catalogues are under a peer duplicate-key corruption. Phase 1 lands only once
  that clears; keys are authored solely through `python -m cadrumo.locales set`
  (aeat-locales-cli), never by hand.
- **Parity gate on the 0019 COMPUTED flip (Phase 2).** AEAT lists 0019 as an INPUT box, so
  flipping it to COMPUTED requires the parity-gate treatment the art-20 ADR applied to 0023.
  Phase 1 touches no input_kind and does not perturb the gate.
- **Gap C Phase 2 is data-gated.** The exact art. 52 individual sub-limit needs the
  individual/employer contribution split that casilla 0463 does not cleanly expose plus the
  8.500-increment cuadro; it stays advisory until that split is modelled. Gaps A and B Phase 2
  have no such dependency.
- **Registry authority + no tautology.** Every figure rides the registry per revision
  (aeat-registry-authority-flow, aeat-schema-central-config); calc tests derive expected
  values from the bundled AEAT Renta manuals, never from the same formula under test
  (no-tautological-calculation-tests).
- **Parent-surface stability.** The registry engine has been intermittently non-loading under
  peer refactors; the registry-predicate mechanism is unavailable while it is, which is why
  Phase 1 uses the Python-helper mechanism the art-20 advisory already proved.

## Implementation

Two-phase, advisory-first, following the art-20 precedent mechanism.

**Phase 1 (advisory - gated on the locale-corruption clearing).** Add Python advisory
helpers beside `_art20_advisory.py`, wired into
`_verification_actions._collect_revision_verification_findings`, resolving casillas by
semantic_role (never hard-coded numbers) and grounding each finding with legal_refs:

- A19 advisory: when the rendimiento del trabajo is positive (0018 > 0, role
  irpf_rendimiento_trabajo_suma_rendimientos_netos_previos) but the otros-gastos casilla
  (role irpf_rendimiento_trabajo_gasto_otros) is zero, warn that the EUR 2.000 art. 19.2.f
  deduction is likely unapplied. legal_refs ley-35-2006:art-19.
- Letter-f / clamp advisory: when 0019 + 0020 + 0021 exceeds 0018 (net would go negative),
  warn that the letter-f cap limits otros gastos to the rendimiento. legal_refs
  ley-35-2006:art-19.
- A52 advisory: when the reducción (0468) was granted above EUR 1.500 while both
  plan-de-empleo/employer boxes are zero (0426 = 0 AND 0427 = 0), warn of a possible art. 52
  over-reduction (individual-only contributions are capped at EUR 1.500). legal_refs
  ley-35-2006:art-52.

All three are ADVISORY / WARNING severity; a legitimately-zero or legitimately-employer-backed
case must remain permissible. The EUR 2.000 and EUR 1.500 figures ride external_constants
(e.g. MODELO_100_ART_19_2F_OTROS_GASTOS_EUR, MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR),
grounded on arts. 19.2.f / 52, never inline literals.

**Phase 2a (compute - the no-cross-section pieces, Gaps A and B).**

- Flip 0019 to COMPUTED with formula 0019 = min(EUR 2.000, max(0, 0018)) per revision,
  grounded ley-35-2006:art-19, applying the same Diseño-de-Registros parity-gate treatment
  art-20 used for a computed casilla AEAT lists as input. (The exact interaction with 0020 /
  0021 under the joint letter-f cap is confirmed against a manual worked example at plan time;
  the base case is min(2.000, rendimiento).)
- Wrap the 0022 formula in max(0, ...): 0022 = max(0, 0018 - 0019 - 0020 - 0021), which
  enforces both the missing clamp and the art. 19.2.f letter-f joint cap in one expression,
  grounded ley-35-2006:art-19. Applied across revisions 2021-2025.

**Phase 2b (compute - the data-gated piece, Gap C).** Once the individual/employer
contribution split is modelled (distinguishing individual aportaciones from the
0426/0427-backed 8.500 increment slot, with the art. 52 cuadro), re-express 0468 as the art.
52 lesser-of with the 1.500 general slot plus the employer-backed 8.500 increment, replacing
the flat 10000 literal (which also moves to external_constants), grounded ley-35-2006:art-52.
At that point the A52 advisory upgrades to a BLOCKING consistency check or retires.

**Tests.** Extend `test_renta_chain_behaviour.py` with manual-grounded oracles: an
otros-gastos auto-apply case (rendimiento minus EUR 2.000), a letter-f over-entry clamp case
(net floored at 0), and an individual-only over-reduction case (reducción capped at EUR 1.500)
- each expected value derived from a bundled AEAT Renta manual worked example, never from the
formula under test. Phase 1 advisories get synthetic-revision contract tests (matching the
art-20 advisory test), independent of the registry loading.

## Rationale

Advisory-first respects no-silent-under-declaration (a determinable EUR 2.000 deduction
left blank, or an over-reduction, gets an operator signal) WITHOUT the false-positive risk
a blocking rule carries (it cannot always prove eligibility, so it must not refuse a
legitimate figure). It reuses the exact mechanism the accepted art-20 ADR proved - a Python
verify-path helper resolving by semantic_role, grounded in legal_refs - so it is a mechanism
selection, not a new pattern, and delivers safety value the moment the locale corruption
clears, independent of the engine refactor. The research established that the letter-f cap
and the max(0) clamp are the same expression, so Gap B's Phase 2 is a one-line, fully-grounded
change with no cross-section dependency; the EUR 2.000 auto-apply (Gap A) is likewise
determinable. Only Gap C's exact compute genuinely needs data the schema does not cleanly
carry, which is why it alone stays behind Phase 2b. Every figure is grounded verbatim in the
bundled consolidated LIRPF (arts. 19.2.f, 52) with catalogue entries that already exist,
satisfying registry-calculation-legal-grounding and aeat-safety-legal-gates.

## Consequences

Gains: closes a silent over-tax on the highest-volume IRPF work-income deduction (the EUR
2.000 art. 19.2.f) and a silent over-reduction on previsión-social, with a low-risk grounded
advisory now and a fully-grounded compute for the two determinable gaps next; documents the
verified schedule for the deferred art. 52 compute. Difficulties: Phase 1 is blocked until the
peer locale corruption clears; the 0019 COMPUTED flip must carry the parity-gate treatment for
a casilla AEAT lists as input; Gap C Phase 2b depends on an individual/employer contribution
split the current casilla taxonomy (0463 mixing both) does not expose, plus the art. 52 8.500
cuadro. Pitfalls: shipping any of these as a BLOCKING rule in Phase 1 would refuse legitimate
filings (a genuine employer-backed 10.000 reducción; a taxpayer whose otros gastos are entered
under a different path) - the advisory severity is load-bearing and must not be tightened
until the value is actually computed. Pathways: the same advisory-to-compute ladder now covers
0019, 0022, 0023 (art-20), and 0468, converging the M100 trabajo-net and previsión-social
surfaces onto one grounded, non-tautological pattern; a future codification candidate is the
"determinable auto-apply casilla modelled as bare MANUAL" smell this and the art-20 ADR both
correct.

Closes / unblocks: #568 (0019 auto-apply + letter-f cap + 0022 clamp), the #574 followup (art.
52 EUR 1.500 individual sub-limit over-reduction). Extends the art-20 advisory-first pattern
(`2026-06-15-art20-trabajo-reduccion-compute-adr`).

## Phase 2b reconciliation (post-implementation, #574 code review)

Phase 2b shipped at `d7b7e314c` and was code-reviewed. The review confirmed the Considerations
section's premise needed correction on one point and surfaced one additional gap in the shipped
formula; both are resolved in the same follow-up commit as this reconciliation.

**Casilla 0463 is NOT a mixed individual/employer catch-all.** The Considerations section above
states "casilla 0463 mixes individual and empresarial aportaciones in one box" as the reason Gap
C could not be cleanly computed. The AEAT Diseño de Registros field dictionary
(`01-100-diccionario-declaracion-individual-ejercicio-2025-*.properties`) disproves this: 0463
(`RGEA`, "Aportaciones individuales y contribuciones empresariales") is its OWN disjoint
data-entry field, distinct from 0427 (`RGCONT`, "Contribuciones empresariales... **excepto**...
las aportaciones de empresarios individuales") — 0427's own label explicitly EXCLUDES what 0463
covers. Casilla 0467 (`RSUMAD`) is a pure additive SUM of 0463+0464+0465+0438+0426+0427+0499+0466,
confirming every summand is its own independently-declared box, not an overlapping catch-all. An
employer contribution cannot legitimately land in 0463; it has its own dedicated box (0427/0426/
0438). This removed the blocker the Considerations section identified, and the tiered compute
(pooling 0463+0465 as "individual" and 0426+0427+0438+0499 as "employer-linked backing") is sound
on this axis.

**A genuinely separate defect was found and fixed: art. 52.1's 1.º and 2.º increments are not
interchangeable.** The shipped formula pooled casilla 0499 (aportaciones de trabajadores por
cuenta propia o autónomos, empresarios individuales) together with 0426/0427/0438 as uniformly
unlocking the full EUR 8.500 art. 52.1.1.º increment. The bundled `ley-35-2006` art. 52.1 corpus
text is explicit that 1.º ("En 8.500 euros anuales") is conditioned on "contribuciones
empresariales, o... aportaciones del trabajador al mismo instrumento de previsión social"
(0426/0427/0438 only), while 2.º ("En 4.250 euros anuales") is the SEPARATE increment for
"aportaciones... realizadas por trabajadores por cuenta propia o autónomos" (0499) — and the two
increments are additive but jointly re-capped at EUR 8.500 total ("en todo caso, la cuantía
máxima de reducción por aplicación de los incrementos previstos en los números 1.º y 2.º
anteriores será de 8.500 euros anuales"). A purely-0499-backed filer was therefore silently
granted up to EUR 8.500 of increment capacity when only EUR 4.250 is legally available — an
over-reduction / under-tax. The formula was corrected to split the two sub-tiers
(`min(0426+0427+0438, 8500)` plus `min(0499, 4250)`, jointly re-capped at `8500`) in both the
2024 and 2025 revisions, and the `_art52_reduccion_advisory_finding` defense-in-depth advisory
(2021-2023, where 0468 stays MANUAL) was extended to resolve casilla 0499 so it no longer
false-positives on a legitimate 0499-only reducción above EUR 1.500.

Both fixes are grounded in the bundled `ley-35-2006` art. 52 corpus text (arts. 52.1.b, 52.1.1.º,
52.1.2.º) and the AEAT DR field dictionary; new manual-derived chain tests
(`test_art52_tiered_autonomo_only_aportacion_capped_at_1500_plus_4250`,
`test_art52_tiered_employer_and_autonomo_increments_jointly_recapped_at_8500`) lock the corrected
boundary, alongside a new advisory contract test
(`test_art52_reduccion_advisory_silent_when_autonomo_backed`).
