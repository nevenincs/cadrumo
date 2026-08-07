---
tags:
  - '#adr'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1e20cdedf4b3040276102f4db98c949a39e5897201acf59aa9b3e657d5eb6e23'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
  - "[[2026-07-26-multi-activity-profile-reference]]"
  - "[[2026-07-26-multi-activity-profile-adr]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - '[[2026-08-07-calculation-chain-integrity-m390-annual-under-modelling-research]]'
---
# `calculation-chain-integrity` adr: `Activity-type axis placement: the value is a profile activity row, the transaction carries a reference` | (**status:** `proposed`)

## Problem Statement

RIRPF art. 95 fixes the retención rate by ACTIVITY: 15 %/7 % professional
(apartado 1), 2 % agrícola/ganadera with a 1 % engorde de porcino y avicultura
carve-out (apartado 4), 2 % forestal (apartado 5), 1 % estimación objetiva
(apartado 6.1.º). Nothing in the tree records which activity produced a given
euro of income, so two consumers are blocked on the same missing axis.

The inferred-retención advisory in `application/aggregation/_retencion_rate_advisory.py`
must decide whether a cash shortfall equal to 1 % of the base is a genuine
sectoral withholding or a phantom credit. Measured: excluding estimación
objetiva alone removes no VALUE from the rate set, because apartado 4.1.º also
fixes 1 %, so a régimen-only filter is provably inert.

Modelo 130 casilla 08 (agrarian objetiva volume) is manual and silently zero for
an agrarian-objetiva filer. The accepted `2026-06-19-silent-zero-base-aggregation-adr`
defers it explicitly: it "needs an agrarian-vs-directa classification axis the
transaction model lacks".

The decision needed now is WHERE the axis lives. Candidate placements already
exist in three separate documents and two code surfaces, and the default failure
is to add a fourth rather than reconcile them.

## Considerations

- The rate is a per-ROW fact, not a per-taxpayer one: a taxpayer may carry on an
  estimación-directa activity and an agrarian-objetiva one in the same period.
- The registry already models the axis STRUCTURALLY, as a partition of the M100
  declaration by section: `reg_estima_directa`/`actividad_est_directa` against
  `reg_estima_obj_agricola`/`actividad_agr`. Both partitions exist in the SAME
  M100 2025 revision, which is structural proof that one taxpayer files both.
- AEAT records *Tipo de actividad* per activity SLOT, alongside sección I.A.E.
  and grupo o epígrafe, as part of a triple. It is a declared fact per activity,
  not a derived classification.
- An epígrafe identifies an activity only within its sección, so an epígrafe
  alone cannot address the activity it claims to.
- Agricultural activities are largely IAE-exempt, so an IAE-epígrafe field is
  emptiest for exactly the filers a sectoral-rate screen must identify.
- A name that promises an activity type may hold an estimation regime or an
  epígrafe key; each candidate must be judged on what it HOLDS.

## Considered options

**A. A scalar activity-type field on `TaxpayerProfile`.** Rejected. It models the
axis per taxpayer while the rate is selected per row. The refutation is
structural rather than a matter of degree: the M100 2025 revision carries the
directa and the agrarian-objetiva partitions concurrently, so a single scalar
cannot represent a filer who holds both. `TaxpayerProfile.irpf_estimation_regime`
already embodies this flattening, which is why filtering on it measured inert.

**B. A per-transaction marker beside `irpf_category`, set at classification
time.** Accepted in part, and only as a REFERENCE. The research behind
`2026-06-19-silent-zero-base-aggregation-adr` proposes it, and per-row
attribution is genuinely required. Carrying the activity TYPE VALUE on the
transaction is rejected: the type is a fact AEAT records per activity slot, so
copying it onto every row duplicates an upstream declaration and will drift from
it.

**C. The registry casilla M100 `0166` `irpf_ed_actividad_tipo_clave`.** Rejected
as the axis. Despite the name, it is `data_type = "text"` (not a closed set),
its section path is `["toma_datos_ampliada", "reg_estima_directa",
"actividad_est_directa"]` so it is scoped to estimación directa only, and it is
an annual-declaration input rather than a per-row fact. It is an epígrafe key
inside one partition, not a discriminator across partitions. Its value to this
decision is evidential: it confirms AEAT records a per-activity type.

**D. Reuse `TaxpayerProfile.iae_epigraph`.** Rejected, and already refuted in
the advisory module's own docstring. It is a free string, and agricultural
activities are largely IAE-exempt, so the field is systematically absent for the
filers the axis must identify. Narrowing on its absence would be narrowing on no
evidence.

**E. The per-activity profile ROW of the proposed
`2026-07-26-multi-activity-profile-adr`, which adds *Tipo de actividad* to a
collection-valued activity model.** Accepted as the home of the VALUE. This
placement was not among the three the step named, and it is the one already
designed for the shape the evidence supports: repeatable rows, each carrying the
AEAT triple, with a principal-activity projection for the modelo that wants a
single answer.

**F. Add a fourth axis.** Rejected. Every fact required is already declared or
designed; what is missing is the join between them.

## Constraints

The value-side placement depends on `2026-07-26-multi-activity-profile-adr`,
which is `proposed`, not accepted. This ruling does not accept it by reference:
the build step is blocked until that record is accepted or its row model is
otherwise settled. Sequencing this dependency is the practical cost of not
adding a fourth axis.

One grounding gap is open and must be closed before the rate mapping is
implemented: whether AEAT's *Tipo de actividad* code set discriminates
profesional, agrícola/ganadera, forestal and objetiva at the granularity RIRPF
art. 95 requires, including the engorde de porcino y avicultura carve-out that
art. 95.4.1.º fixes at 1 %. If it does not, a mapping from the AEAT code set to
the art. 95 partition must be grounded and declared in the registry rather than
inferred in code. Assuming the two sets align is the failure mode this
constraint exists to prevent.

## Implementation

The axis is a JOIN, not a new field. The activity-type VALUE is owned by the
per-activity profile row; a ledger transaction carries a REFERENCE to the
activity slot that produced it, resolved at classification time beside
`irpf_category`. One canonical home for the fact, one per-row attribution, no
duplication.

Rate selection then reads: transaction to activity slot, slot to declared type,
type to the art. 95 partition, partition to the grounded rate subset already
exposed by `professional_activity_retencion_rates` and
`sectoral_activity_retencion_rates`. The inferred-retención advisory narrows its
comparison to the rates that filer's activity can lawfully attract, which
restores the catch a régimen-only filter provably could not.

Modelo 130 casilla 08 reads the same join, summing the volume of income rows
whose referenced activity is agrarian-objetiva. The two consumers need the same
mechanism, not different ones, which is the finding that makes one placement
sufficient.

A row whose activity reference is absent resolves to no partition and must widen
rather than narrow: an unattributed row keeps today's full-set comparison and
raises the existing advisory. Absence is not evidence of a non-sectoral
activity, and the advisory channel must never suppress on it.

## Rationale

Reconciling rather than adding turns a missing field into a missing join, which
is a smaller and better-grounded change. Every fact the rate selection needs is
already declared somewhere: AEAT declares the type per activity slot, the
registry partitions the declaration by regime, and the transaction model already
carries per-row IRPF attribution through `irpf_category`. Nothing new needs to
be invented; the pieces need to be connected.

Splitting value from reference is what keeps the fact single-homed. Copying the
type onto each transaction would put a declared AEAT fact in two places with no
mechanism keeping them equal, and the copy would be the one consulted. A
reference cannot drift from the thing it points at.

The per-row conclusion is forced by the evidence rather than chosen: the M100
revision that carries both the directa and the agrarian-objetiva partitions is
the same revision, for the same filer, in the same period. Any per-taxpayer
placement contradicts a structure the registry already ships.

## Consequences

Two deferred items unblock on one capability: the inferred-retención rate
narrowing, and M130 casilla 08, which an accepted ADR defers pending exactly
this axis. Both consume the join rather than each growing their own signal.

The build acquires a dependency on a proposed ADR, which is a real cost and is
stated as a constraint rather than absorbed silently. A reader who wants the
capability sooner should push on accepting the multi-activity row model, not on
adding a fourth placement.

Until the AEAT code-set mapping is grounded, the rate partition cannot be
derived and the advisory keeps its current full-set behaviour. That is the
correct interim state: it is visible, non-blocking, and never suppresses a
finding on an unverified fact.

## Amendment 2026-08-07: the grounding constraint is closed, and the placement was not honoured

Recorded by the campaign's close honesty review rather than left for a reader to
rediscover.

**The Constraints paragraph above is satisfied.** It required establishing, before
any rate mapping, whether AEAT's *Tipo de actividad* code set discriminates at the
granularity art. 95 needs. `W03.P05.S37` located the code table -- published in the
Modelo 036 instrucciones, not with the diseño, which is why sweeps of the diseño
corpus kept coming back empty -- and bundled it with provenance. `W03.P05.S38`
answered the question: the set discriminates three of the four boundaries and
**not** the art. 95.4.1.º engorde de porcino y avicultura carve-out, because the
table's finest livestock grain is `B02 Ganadera`.

The fallback this paragraph specifies therefore applies, and was taken: the mapping
is grounded and declared in the registry as the `rirpf-art-95:selector-m036-*`
parameters, each with its own `legal_refs`, never inferred in code. The engorde
partition carries a deliberately EMPTY code set so the gap is legible where the
mapping is read.

**The placement ruling was NOT honoured, and that is a defect in the execution, not
a revision of this ruling.** `W03.P05.S11` shipped `tipo_actividad: TipoActividad`
on `Transaction` -- the activity type VALUE on the row -- which option B above
rejects in exactly those words. The step was implemented without reading this
record; its own exec note argues the per-row placement from first principles and
never mentions that a decision already existed. The campaign applied its discovery
discipline to code and skipped it for decisions.

The mitigation is real but partial: this ADR and the multi-activity ADR it depends
on are both `proposed`, no per-activity profile row exists in the tree, and waiting
would have blocked the Modelo 131 agrarian aggregation behind two unaccepted
records. Nothing is duplicated today because there is no upstream declaration to
duplicate.

The hazard is dated rather than absent. When the per-activity profile row lands
carrying its own tipo de actividad, `Transaction.tipo_actividad` becomes a second
home for one fact and the drift this ruling predicted begins, invisibly -- both
fields individually correct, diverging only for a taxpayer who edits one. A
tripwire now fails at that moment: `src/cadrumo/tests/test_tipo_actividad_single_home.py`
asserts exactly one stored home and its refusal states the rule and names the readers
to repoint. The refusal deliberately does NOT name this record: code never cites the
vault, and the remedy text is self-contained without the citation, so an author who
trips the tripwire learns what to do from the message itself. It was mutation-proven
by adding a second stored field and observing the
red, then reverted.

So this ruling stands unamended in substance. What changed is that its constraint is
discharged, its violation is recorded rather than quietly carried, and the moment it
starts costing something is now guarded.
