---
tags:
  - '#adr'
  - '#modelo-100-minimo-descendientes-engine'
date: '2026-07-01'
modified: '2026-07-02'
related:
  - '[[2026-07-01-modelo-100-trabajo-casilla-compute-adr]]'
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
  - '[[2026-05-27-descendant-profile-axis-adr]]'
---

# `modelo-100-minimo-descendientes-engine` adr: `Modelo 100 minimo por descendientes engine: compute 0513/0514 vs manual` | (**status:** `accepted`)

## Problem Statement

Modelo 100 casillas `0513` (minimo por descendientes, parte estatal) and `0514`
(parte autonomica) carry no `input_kind` and no `binding` in every revision 2020
through 2025, so the loader defaults them to a bare MANUAL input: the operator
types the euro figure by hand. The minimo personal y familiar total `0519` is a
computed `sum(0511, 0513, 0515, 0517)`, but only `0511` (minimo del
contribuyente) is engine-derived; `0513`, `0515`, and `0517` are hand-entered.
The application therefore does NOT compute the minimo por descendientes at all;
it accepts whatever the operator supplies and folds it into the cuota chain
(`0519` feeds the escala-sobre-minimo formulas that reduce the tax). A blank or
mis-entered `0513`/`0514` mis-taxes the filer with zero operator signal, which is
the silent-under-declaration failure mode.

The apparatus to compute the minimo is already scaffolded but stranded, dormant,
or dangling, never wired to `0513`/`0514`:

- The per-birth-order and menor-3-anos amounts exist as registry `money`
  parameters in every revision (`renta-YYYY-minimo-descendientes-primer-hijo-YYYY`
  through `-cuarto-y-siguientes-` plus `-menor-tres-anos-`), grounded to Art. 58
  and the AEAT Renta manual. NO formula references any of them.
- The custodia-compartida prorrateo axis (added under the descendant-profile-axis
  work): `DescendantInfo.custodia_compartida: bool`, the constant
  `CUSTODIA_COMPARTIDA_PRORRATA_FACTOR = 0.5` (grounded at Art. 61.4a), and the
  `RentaFamilyProfile.custodia_compartida_advisory` / `custodia_compartida_count`
  / `custodia_compartida_prorrata_factor` helpers. The advisory and the minimo
  prorrata factor have zero non-test consumers. The bare `custodia_compartida`
  FIELD is consumed indirectly by the separate anualidades-sin-minimo derived
  binding for the Art. 64/75 separate-escala eligibility, but nothing applies the
  0.5 factor to a minimo por descendientes contribution, because there is no
  minimo por descendientes computation to apply it to.
- Two profile bindings, `renta-YYYY-profile-descendientes-count` and
  `renta-YYYY-profile-descendientes-minimos-aggregate`, exist. The count binding
  resolves to `RentaFamilyProfile.descendientes_count` (a real property). The
  aggregate binding maps to model selector
  `family.descendientes_minimos_aggregate_YYYY`, which does NOT exist as a
  property anywhere: a dangling selector scaffolded ahead of the engine that was
  meant to populate it. Neither binding is consumed by any formula.

Issue #515 opened as a bounded "apply custodia-compartida 50% prorrateo" request
citing Art. 59 LIRPF. That premise is doubly wrong: (1) the engine gives each
parent nothing computed, not the full allowance, so there is no full amount to
halve; and (2) Art. 59 LIRPF is the minimo por ASCENDIENTES; the custodia
prorrateo authority is Art. 61.4a, already corrected in the repository. Closing
#515 requires building the minimo-descendientes engine and rebinding `0513`/`0514`
from manual to computed, a behaviour change for every M100 filer with
descendientes, so it warrants a decision record rather than a bounded patch.

## Considerations

Amounts verified verbatim against the bundled consolidated LIRPF
`src/aeat/_data/corpus/normatives/html/ley-35-2006.html` (Art. 58), and matching
the registry `money` parameters that cite the same law plus the AEAT manual:

- Art. 58.1 ordinary minimo por descendientes: "2.400 euros anuales por el
  primero", "2.700 euros anuales por el segundo", "4.000 euros anuales por el
  tercero", "4.500 euros anuales por el cuarto y siguientes".
- Art. 58.2 menor-de-tres-anos supplement: "el minimo a que se refiere el apartado
  1 anterior se aumentara en 2.800 euros anuales".
- Art. 61.4a prorrateo between entitled parents: "su importe se prorrateara entre
  ellos por partes iguales", the shared-custody / two-entitled-parents case,
  encoded as the 0.5 factor.

Eligibility and prorrateo primitives already exist on `DescendantInfo` /
`RentaFamilyProfile` (`is_eligible_ordinary`, age < 25 or discapacidad, cohabiting;
`is_eligible_menor_tres`, age < 3; `descendientes_full_year_minimum`;
`joined_before_or_on_1_july`; `custodia_compartida_prorrata_factor`). These are the
building blocks a formula/resolver would consume; they are tested in isolation but
feed no casilla.

One grounding gap is deliberately flagged, not asserted: the Art. 58.4 TEMPORAL
prorrateo. The code interprets it as a 1-July cutoff (born/adopted before 1 July =
full annual amount; on/after = half), but the bundled Art. 58 corpus text found in
this pass does not state a "half-year 50%" rule verbatim; it phrases the temporal
prorrata as "por numero de dias del periodo impositivo" (a daily prorrata). The
exact per-day-versus-half-year mechanism, and whether it attaches to nacimiento,
adopcion, and defuncion alike, MUST be grounded against the AEAT Renta manual and
Art. 61.3a/58.4 during planning before it is encoded as computed (per the
bundled-corpus-cross-check discipline; a numeric mechanism is not shipped on an
unverified interpretation).

The rebind is a genuine behaviour change: today a filer whose profile carries no
descendientes but who hand-enters `0513` gets that value; after the rebind, a
computed `0513` derived from an incomplete descendientes profile would OVER-write
the operator figure with a wrong (likely lower or zero) computed one, the exact
inversion of the under-declaration this fixes. So the fail-direction when
descendientes profile data is absent or partial is the load-bearing design
question, not an afterthought.

The precedent for a manual-to-computed M100 casilla rebind is established: the
art. 20 trabajo-reduccion and trabajo-casilla-compute ADRs both chose an
advisory-first, compute-flip-deferred shape for exactly this class of gap, and
both are per-year multi-revision. This ADR follows that shape rather than
inventing a new one.

## Considered options

- **Option A, full computed minimo-descendientes engine + rebind (closes #515).**
  Author a formula (or profile-aggregate resolver) that sums, per eligible
  descendant, the Art. 58.1 birth-order amount + Art. 58.2 menor-3 supplement,
  applies the Art. 58.4 temporal prorrateo and the Art. 61.4a divide-by
  entitled-parents (custodia compartida = 0.5) factor, and binds the result into
  `0513`/`0514`, flipping them from manual to computed. Consumes the dormant
  params, the dangling aggregate binding, and the stranded custodia axis. Pro:
  actually computes the minimo, closes #515, removes the hand-entry mis-tax. Con:
  changes tax for every filer with descendientes; depends on complete
  descendientes profile data; multi-revision (2020-2025); needs the Art. 58.4
  grounding resolved first.

- **Option B, bounded advisory interim (does NOT close #515).** Surface the
  already-grounded `custodia_compartida_advisory` (Art. 61.4a) as a non-blocking
  `Notice` on the M100 calculate path when the profile carries at least one
  eligible shared-custody descendant, instructing the operator to halve the
  manually-entered minimo. Also emit an advisory when descendientes exist in the
  profile but `0513` is left blank. Keeps `0513`/`0514` manual. Pro: a real
  safeguard shippable in one bounded change with no behaviour-change blast radius;
  consumes the stranded advisory; aligns with the notice channel and
  no-silent-under-declaration. Con: an advisory, not a computation; the operator
  still types the figure, so #515 stays open.

- **Option C, status quo (rejected).** Leave `0513`/`0514` manual and the
  apparatus dormant. Rejected: it is the silent-under-declaration state the issue
  and the no-silent-under-declaration rule refuse; it also leaves dormant
  resolvers/params and a dangling selector on the tree, which the
  no-dormant-source-resolvers discipline treats as either wire-or-delete.

## Decision

We will pursue **Option A** as the closing design, phased per revision, and land
**Option B as the interim first phase** because Option A is multi-phase and gated
on the Art. 58.4 temporal-prorrateo grounding. The advisory ships first as an
immediate safeguard while the computed engine is built and rebound revision by
revision; each revision rebind lands only once its descendientes-driven
computation is grounded and its fallback verified.

## Constraints

- **Art. 58.4 grounding is blocking for the compute flip.** The temporal prorrateo
  mechanism must be confirmed against the AEAT Renta manual / consolidated LIRPF
  before `0513`/`0514` are rebound to computed. Option B (advisory) is NOT blocked
  by this and can land first.
- **Descendientes profile completeness is a parent dependency.** The computed path
  reads the `renta_family.descendiente.*` fact tree (birth_date, adoption_date,
  discapacidad, convivencia, custodia_compartida). The descendant profile axis is
  landed and stable, but a filer data set may be absent or partial; the engine
  cannot assume completeness.
- **The dangling aggregate selector must be built or the binding deleted.** The
  `descendientes-minimos-aggregate` binding maps to a non-existent
  `family.descendientes_minimos_aggregate_YYYY`. Option A implements that property
  (or replaces the binding with a formula over the params); it is not left
  dangling.
- **Multi-revision surface.** 2020 through 2025 each carry their own param set and
  their own `0513`/`0514`/`0519` casilla files (registry index differs from
  official number per year); the rebind is per-revision, not a single edit.
- **No-legacy / no-shim.** The rebind deletes the manual-input assumption for
  `0513`/`0514`; it does not add a manual-vs-computed toggle or a compatibility
  branch.

## Implementation

Layering, high level:

- **Interim (Option B), one bounded phase.** On the M100 calculate path, when the
  active profile descendientes list contains at least one eligible shared-custody
  descendant, project `custodia_compartida_advisory` (already grounded, already
  translated) into an advisory `Notice` on the calculate envelope telling the
  operator to apply the 50% prorrateo to the hand-entered minimo. Add a companion
  advisory when descendientes are present but `0513` is blank. This consumes the
  stranded advisory and gives the operator a signal without touching the value
  channel. It does not resolve #515.

- **Computed engine (Option A), phased per revision.** Introduce a
  minimo-por-descendientes computation that, per eligible descendant, selects the
  birth-order amount (first/second/third/fourth-and-following from the registry
  params), adds the menor-3 supplement where age < 3, applies the Art. 58.4
  temporal prorrateo (once grounded), then multiplies by the Art. 61.4a factor
  (divide by number of entitled parents; 0.5 for custodia compartida). The
  aggregate feeds `0513` (estatal); the autonomico half `0514` follows the same
  base unless a comunidad publishes its own minimo (a per-CCAA grounding item).
  Bind the aggregate into `0513`/`0514` and flip their `input_kind` to computed.
  Prefer a profile-aggregate resolver populating the existing
  `descendientes-minimos-aggregate` binding (building the missing
  `family.descendientes_minimos_aggregate_YYYY` property), or an explicit formula
  over the params; the plan chooses one canonical mechanism, not both
  (one-aggregation-path discipline).

- **Fail-direction on absent/partial descendientes data.** Ground the fallback in
  no-silent-under-declaration. When the profile carries NO descendientes facts, the
  computed `0513` would be zero; overwriting a non-zero operator entry with a
  computed zero is a silent under-application of a determinable allowance in the
  OTHER direction. The plan must decide, per phase, between (a) computing only when
  descendientes facts are present and otherwise leaving the manual value with a
  "descendientes profile empty, minimo not computed" advisory, versus (b)
  computing always and emitting a blocking/advisory finding on the
  operator-entered-vs-computed divergence. The advisory-first precedent (art. 20
  `0023`, art. 19.2.f `0019`) leans toward (a) for the first computed revision,
  with a divergence check added as the computation matures.

- **Dormant-surface consumption.** Option A enrolls the per-birth-order and menor-3
  params, the custodia prorrata factor, and the descendientes-count / aggregate
  profile bindings into the live path; any that remain genuinely unused after the
  engine lands are deleted rather than left dormant.

## Rationale

Option A is the only path that closes #515 and removes the hand-entry mis-tax, and
the whole apparatus to build it already exists (grounded params, eligibility
primitives, the custodia axis, the profile fact tree): it is scaffolded and
stranded, not absent, so the marginal cost is wiring plus grounding, not
green-field design. Option B is chosen as the interim FIRST phase, not as a
substitute, because the compute flip is a real behaviour change gated on the
Art. 58.4 grounding and on per-revision fallback decisions, and shipping the
grounded advisory immediately converts a silent state into an operator-visible one
at near-zero blast radius. The advisory-first, compute-flip-deferred shape mirrors
the accepted art. 20 `0023` and art. 19.2.f `0019` decisions, so this is an
application of an established M100 pattern, not a novel one. Amounts are taken from
the bundled consolidated LIRPF and the corpus-cited registry params, not invented;
the one unverified mechanism (Art. 58.4 temporal prorrateo) is explicitly flagged
as blocking-for-compute rather than asserted.

## Consequences

- **Gains.** Closes the silent under/over-declaration on `0513`/`0514`; the minimo
  por descendientes becomes computed and provenance-grounded rather than a trusted
  hand entry. Consumes the dormant params, the stranded custodia advisory/factor,
  and the dangling aggregate binding, retiring an accumulation of scaffold-ahead
  debt on the M100 tree. The interim advisory ships a real safeguard immediately.
- **Behaviour-change cost, accepted.** The compute flip changes the tax outcome for
  every M100 filer with descendientes. That is the point, but it means the rebind
  cannot land until the descendientes-driven computation is grounded per revision
  and the absent-data fallback is decided; a wrong or premature flip would mis-tax
  in the opposite direction. This is why the flip is deferred behind the advisory
  and phased per year.
- **Grounding debt surfaced.** The Art. 58.4 temporal prorrateo and any per-CCAA
  autonomico minimo divergence are open grounding items the plan must resolve
  before their respective phases; they are named here, not silently assumed.
- **Multi-revision effort.** Six revisions each need their param set wired, their
  `0513`/`0514` rebound, and their fallback verified; the effort scales with the
  year count, in line with the other per-year M100 campaigns.
- **Pitfall.** The dangling `family.descendientes_minimos_aggregate_YYYY` selector
  is a trap for a future agent who assumes the aggregate binding already resolves;
  the plan must either build the property or delete the binding, and must not leave
  the half-wired state that exists today.

## Implementation status (2026-07-02)

**Option B landed** (commit `bc3b89594`, `feat(modelo): M100 custodia-compartida
minimo advisory + fix dangling descendientes selector (#515)`):

- The `custodia_compartida_advisory` (Art. 61.1a LIRPF — corrected citation, see
  below) now surfaces as a non-blocking `CalculationSourceDiagnostic` /
  operator-facing `Notice` on the M100 calculate path whenever the active
  profile carries at least one Art. 58.1-eligible descendant flagged
  `custodia_compartida=true`. A companion advisory fires when eligible
  descendientes are present but casilla 0513 (parte estatal, located by its
  stable `semantic_role` across every revision year) resolved to zero.
- The dangling `renta-2024-profile-descendientes-minimos-aggregate` binding
  (selector `family.descendientes_minimos_aggregate_2024`, never implemented,
  never consumed) was deleted per `no-dormant-source-resolvers`. The sibling
  `descendientes-count` binding (a real, resolvable selector, simply
  unconsumed) was left in place as harmless future Option A fuel.
- New module `src/aeat/application/modelo/_minimo_descendientes_advisory.py`,
  wired into the post-calculation advisory coordinator
  (`_calculation_diagnostics.py`) with real-adapter tests (encrypted bucket,
  loaded registry snapshot, real domain eligibility logic — no mocks) in
  `src/aeat/application/modelo/tests/test_minimo_descendientes_advisory.py`.

**Citation correction found during implementation:** the custodia-compartida
prorrateo is Art. **61.1ª** LIRPF ("Cuando dos o más contribuyentes tengan
derecho a la aplicación del mínimo por descendientes... su importe se
prorrateará entre ellos por partes iguales"), not Art. 61.4ª as stated
elsewhere in this ADR and in the pre-existing
`CUSTODIA_COMPARTIDA_PRORRATA_FACTOR` constant comment
(`src/aeat/core/external_constants.py`). Norm 4ª of Art. 61 covers a
completely different case (the fixed reduced amount on a descendant/ascendant's
mid-year death). This pre-existing citation error was corrected in the new
module's own docstrings and messages; the constant's comment and any other
call sites still carrying "61.4ª" are a separate, out-of-scope follow-up.

**Art. 58.4 grounding resolved: the mechanism does not exist.** Cross-checked
directly against the bundled consolidated LIRPF
(`src/aeat/_data/corpus/normatives/html/ley-35-2006.html`, Art. 58, last
updated 28/11/2014, in force from 01/01/2015 — the same version the registry
params already cite): Art. 58 has exactly two numbered subsections (58.1
ordinary birth-order amounts, 58.2 menor-3-años supplement) and NO within-year
birth/adoption temporal prorrateo of any kind for descendientes. Art. 61
(normas comunes) fixes personal/family circumstances as of the devengo date
(norm 3ª — a year-end snapshot rule, not a prorrata), prorrates only for a
mid-year DEATH (norm 4ª — a fixed reduced amount, unrelated to birth/adoption
timing), and its half-period residency prorrata (norm 5ª) is scoped explicitly
to ascendientes, never descendientes. No AEAT Renta manual is bundled in this
corpus that states such a rule either. Per the bundled-corpus-cross-check
discipline, absent a grounded mechanism the compute flip (Option A) stays
deferred — this closes only the interim safeguard, not #515 itself. Issue
#515 remains OPEN pending either (a) a grounded temporal mechanism sourced
from a live AEAT Renta manual / BOE consolidation the operator supplies, or
(b) a decision that no temporal prorrateo applies to descendientes at all (in
which case Option A's per-descendant amount is simply the full annual
birth-order figure regardless of entry date within the year, and Option A can
proceed without further grounding blockers on this axis).

## Implementation status (2026-07-02, Option A landed)

**Option A landed** across all six revisions (2020-2025). Ruling (b) above is
confirmed: the bundled AEAT Renta manuals contain no within-year temporal
prorrateo for descendientes, so `RentaFamilyProfile.minimo_descendientes_estatal`
applies the full annual birth-order amount regardless of the descendant's entry
date within the ejercicio.

- New domain method `RentaFamilyProfile.minimo_descendientes_estatal` (
  `src/aeat/domain/contribuyente/family.py`) ranks Art. 58.1-eligible
  descendants by `birth_date` ascending, sums the birth-order tranche (1º/2º/3º/
  4º-y-siguientes) plus the Art. 58.2 menor-3 supplement, and applies the
  Art. 61.1ª custodia-compartida 0.5 factor per descendant. Amounts are passed
  in by the caller from the revision's own registry `money` parameters — the
  domain method contains no hardcoded euro figure.
- New application-layer injector
  `inject_derived_minimo_descendientes_facts` (`src/aeat/application/modelo/_profile_binding.py`)
  reads `snapshot.revision.parameters` for the per-year tranche/menor-3 params,
  computes the aggregate, and projects it onto the (previously-dangling)
  user-profile schema field `renta_family.descendientes_minimos_aggregate_{year}`
  — retiring the exact dangling selector this ADR flagged, rather than minting
  a new key. A genuinely childless profile resolves to the legally correct
  zero; the fail-direction concern (a computed zero over-writing a correct
  manual entry) does not apply on this unreleased pre-beta app, which carries
  no prior manual `0513`/`0514` data to protect (`no-legacy-compatibility`).
- Casillas 0513/0514 are `input_kind = "computed"` with a dedicated formula
  (`renta-{year}-minimo-descendientes-estatal` /
  `-autonomico`) in every revision 2020-2025, projecting the binding's
  aggregate via a trivial `{ op = "copy", args = [{ binding = ... }] }`
  expression.
- The interim Option B advisory module
  (`_minimo_descendientes_advisory.py`) is retired: its two checks (confirm
  the hand-entered figure was halved; flag a blank entry) are structurally
  unreachable now that the casillas are computed and the engine itself applies
  the custodia-compartida halving.
- New legal catalogue entry `ley-35-2006:art-61` (previously absent — no prior
  `legal_refs` citation actually pointed a registry value at Art. 61) grounds
  the custodia-compartida prorrata, sourced from a new dedicated corpus excerpt
  `ley-35-2006-art-61.html` extracted verbatim from the bundled consolidated
  LIRPF (`ley-35-2006.html`, en vigor 01/01/2015).

**Known limitation, deferred per this ADR's own scoping (not closed by this
landing): the autonómico half (0514) mirrors the estatal aggregate (0513) for
every CCAA.** A RAG discovery pass over the bundled AEAT Renta manuals
surfaced that at least the Comunidad de Madrid publishes its OWN mínimo por
descendientes figures for the 3rd and 4th-y-siguientes tranches (Decreto
Legislativo 1/2010, Art. 2: 4.400 € / 4.950 €, vs the general LIRPF Art. 58
figures of 4.000 € / 4.500 €) that SUBSTITUTE the general figures for the
autonómico (0514) computation only — the 1º/2º/menor-3 amounts coincide with
Art. 58 and are unaffected. This ADR already named "per-CCAA autonómica minimo
divergence" as an open grounding item deferred from Option A's initial
landing, and the mirror-estatal default is this ADR's sanctioned fallback
for that gap, not a silent omission — but it is confirmed now, not merely
hypothetical, and is recorded here as a scoped follow-up: a Madrid-resident
filer with 3+ descendientes will see an UNDER-computed 0514 until a per-CCAA
autonómica mínimo-por-descendientes table is authored and the engine's
autonómico projection is made CCAA-conditional (mirroring the dispatch shape
the Madrid nacimiento/adopción deducción already establishes for casilla
1039). Tracked as a follow-up; not blocking for closing #515, which is scoped
to the estatal-half compute-flip and the standard-case autonómico mirror.
