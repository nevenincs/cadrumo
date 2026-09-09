---
tags:
  - '#adr'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1c0d8e4d940bdf4b42fc00a7bd33089db7f470a98b48a5e25e8d9ca25d8e803d'
related:
  - "[[2026-09-09-registry-generator-corpus-provenance-research]]"
  - "[[2026-09-09-registry-generator-divergence-evidence-research]]"
  - "[[2026-09-09-registry-generator-signal-coverage-research]]"
---

# `registry-generator` adr: `a dependable, reproducible registry and the signals that keep it honest` | (**status:** `accepted`)

## Problem Statement

The registry is the authority every filing calculation reads, and half of it cannot be shown to
derive from the official documents it cites. A measured census found divergence between the
official designs and the shipped declarations across a fifth of the generated surface, and the
larger authored surface cannot be measured at all.

The corpus is not merely unproven; it is red today. Eight assertions in the modelo 390 registry
tests demand a signed wire field on four revisions, and the shipped declarations say unsigned. That
is the defect this record addresses, arriving as a test failure rather than as a filing error, and
it is the reason the earlier characterisation of the gates as uniformly green is withdrawn: the
gates were green through the discovery period, not now.

A decision is needed now because the defects found are not independent bugs. They share one cause,
and ad-hoc correction of the artefacts is futile: the generator overwrites its output on the next
run, so a fix applied to data is a fix that will be undone. The rulings below therefore bind the
*producer* and the *attestation*, not the produced files. Most of that producer code lives under
`dev/registry`, outside the shipped package; D4's runtime limb and D10's oracle are the rulings
that bind `src/cadrumo`.

Grounding: `2026-09-09-registry-generator-corpus-provenance-research` (what the corpus is),
`2026-09-09-registry-generator-divergence-evidence-research` (what diverges and why),
`2026-09-09-registry-generator-signal-coverage-research` (what the gates can see).

## Considerations

Five facts from the grounding shape every ruling here.

**The generator is faithful to what it reads.** Where the design states a fact in a column the
generator consults, divergence is zero across tens of thousands of fields. The defects are
concentrated in the columns it does not consult. This is not an unreliable generator; it is an
incomplete contract. Grounding: `2026-09-09-registry-generator-divergence-evidence-research`.

**The failure is silence, not error.** The generator refuses loudly when a design is unclear —
sixty-one refusal sites in `dev/registry/pipeline/_export_tree.py` alone. It stays silent when the
design *contradicts itself*, believing one column and discarding the other without recording that
a conflict existed: the same module writes `signed=False` as an unconditional literal at three
sites. The single arithmetic check that could have caught the largest instance passes, because
both readings of the slot sum to the same width. Grounding:
`2026-09-09-registry-generator-divergence-evidence-research`.

**Verification is circular.** Every gate compares output against a function of the same inputs
that produced it. That proves stability and cannot prove correctness. No artefact, test or manifest
compares a shipped field to the design row it claims to come from — even though the join that would
do it is already serialized in every `_generation.provenance.json` and read by nothing. Grounding:
`2026-09-09-registry-generator-signal-coverage-research`.

**Severity does not follow size.** The sign axis fails closed at
`src/cadrumo/domain/calculations/registry/fixed_width_codec.py`: a filing needing a negative in an
affected slot refuses rather than emitting a wrong figure. The required axis fails open across a
much larger, undefended population: a mandatory value left absent renders as a clean,
complete-looking record. Ranking work by count would invert the ranking by risk. Grounding:
`2026-09-09-registry-generator-divergence-evidence-research`.

**The official type column is not a controlled vocabulary.** Of 15,566 field derivations, 4,396
carry `N`, 7,256 `Num`, 3,172 `An` and 163 `A` — but 579 carry a spelled-out word or a non-type:
`Numérico` 241, `Alfanumérico` 145, `Alfabético` 70, `No consta` 95, `Blancos` 28. Any ruling that
treats the type cell as decidable must say what it does with these, and modelo 347 — named below as
the first repair target — consists *entirely* of them, carrying zero `N` and zero `Num` fields.

## Considered options

**Correct the shipped declarations.** Rejected. The generator regenerates them; the correction
survives until the next run. It also treats a class as a list of instances.

**Strengthen static type checking over the pipeline.** Rejected as the primary remedy, on evidence
rather than preference. The wrong values are not defaults — the field is required at both the
schema and the generator's parameter, and each site passes it explicitly. Construction goes through
validation from a mapping, which erases the declared type, so enriching the schema field catches
none of the sites even inside a checked scope. Static checking is retained as a *secondary* control
with a narrow, effective form (below).

**Derive the missing facts from the official columns and emit them.** Rejected as a first move. It
makes the pipeline decide a legal reading for thousands of fields with no reviewer, which is the
failure the existing declaration discipline was built to prevent, and the re-interpretation is not
uniform across designs.

**Refuse to emit a fact the generator did not determine, and make the disagreement visible.**
Accepted. It fails closed, cannot be undone by regeneration, and generalises to the next axis.

**A cross-period generator that derives a modelo's revisions together.** Rejected as an authority
mechanism, accepted as a diagnostic. A sibling revision is not evidence of law, and a cross-period
generator would have propagated one wrong decision into every revision of a modelo identically —
looking reassuringly consistent while doing so.

## Constraints

- A gate that fails on the day it lands cannot be cleared by the change that adds it. Baselines,
  frozen counts and allowlists are not available as a bridge.
- Population floors must be invariants or named sets, and a floor without a planted defect is
  unproven.
- Joins between design and shipped field use the pipeline's own anchor machinery. Coordinate joins
  are prohibited: designs restart offsets per page and a coordinate join on this corpus produced a
  confident number that was pure noise.
- No ruling here may assert what the law says. The registry cannot guarantee the official documents
  are correct; it can only guarantee that a shipped value agrees with the captured document, or
  that a disagreement is adjudicated with recorded evidence, or that it is refused.
- Adjudications must test the question they adjudicate. An adjudication that reasons from the
  surrounding default inherits the defect instead of examining it.

## Implementation

**D1a — The generator refuses an undetermined sign.** Where a derivation path cannot establish the
sign of a numeric wire field from an authority, it raises rather than writing a constant. The
official type column states this fact (`N` signed, `Num` unsigned), so a refusal here is clearable
by grounding the design. Affected revisions become unrenderable until grounded; that is the
intended, visible cost.

**D1b — Required-ness gains a representable undetermined state, and is held.** The design states
required-ness for 891 of 15,566 derivations; it is silent for 94.3%, across all 32 generated
revisions. Refusal is therefore not payable on this axis — no amount of grounding can clear it,
because no source in this corpus states the fact. The declaration must instead carry `undetermined`
as a third state distinct from required and optional, which is not new policy but restoration of
compliance with `no-silent-under-declaration` ("Missing, unknown, unsupported, deferred… are
distinct states. Do not collapse any of them to zero, empty text, false"). Today `_is_required` in
`dev/registry/pipeline/_export_tree.py` folds "said optional", "said nothing" and "unrecognised
token" alike into `False`. **This ruling is held** pending the consumer lane: whether a third state
is representable end-to-end depends on whether a calculation can distinguish an undetermined value
from an adjudicated one, which this record does not settle.

**D2 — The generator refuses a self-contradicting design.** The contradiction is arithmetic and
decidable from two columns the parser already carries: a width-`W` row whose type column implies a
sign character plus `W−1` digits, while its content cell states integer and decimal digit counts
summing to `W`. The generator raises, naming modelo, revision, field and both readings. It does not
fire on a consistent design — on a `Num` row `15 + 2 = 17` agrees with the type, which is why the
large blank-content and stated-content `Num` populations pass untouched. This is ruled the primary
remedy because it catches the class rather than the instance. Its blast radius is measured, not
estimated: 2,017 fields across 22 of the 32 generated revisions, modelo 390 alone contributing
1,236.

**D3 — The attestation records the verdict, not the pair.** The pair is already recorded: every
`field_derivations` entry in `_generation.provenance.json` carries `parser_field` — `aeat_type`,
`content`, `validation`, `offset`, `length`, `source_cell` — beside the emitted `field`. Recording
it again would change nothing, and the manifest is explicitly ignored by the TOML loader. D3
therefore rules the *comparison*: each entry gains a per-field divergence verdict — agrees,
adjudicated with recorded evidence, or refused — computed at generation time. That is the
acceptance criterion; without it D3 has no effect.

**D4 — Type enforcement is placed where it binds.** Runtime validation at the registry boundary is
the primary control, consistent with this codebase's existing stance. Statically, the effective
change is the generator function's own parameter type, not the schema field, because construction
goes through `model_validate` from a dict literal, which erases the declared type. The scope
question is `dev/registry` — the "registry 200" entry in the burn-down comment in
`dev/quality/types.py`. The shipped `src/cadrumo/domain/calculations/registry` is already inside
every checker's scope. Admitting `dev/registry` is endorsed as a parallel track and is explicitly
*not* a prerequisite for D1–D3.

**D5 — Absence is made unrepresentable where a second fact can ground it, and is held.** The
pattern exists and works: `validate_decimals` in the schema cross-checks a scale against its
declared type and refuses both halves. Applying it to the wire axes requires the *shipped*
declaration schema to carry the official source columns it would tie to, which it does not today —
a schema change across 15,566 generated fields and a further authored population that has no
parser row to supply the value at all. **Held** with D1b, and for the same reason.

**D6 — Cross-period comparison is built as a diagnostic that must be explained.** A field whose
typed shape changes between revisions without a corresponding change in the official designs is
reported as a suspect requiring an explanation or an adjudication. It does not assert correctness
from stability: on this corpus agreement is mostly the absence of evidence, and a layout copied
forward unchanged shows perfect agreement while tracking no regulatory change. No existing
comparator covers this: `_cross_revision_divergence.py` compares label, section, data type,
semantic role and legal references, and carries no notion of wire shape or width.

**D7 — Generation becomes the scaffolded default.** New revisions scaffold the generated path.
Today `dev/registry/newmodelo/manager.py` scaffolds only `export_layouts` and its checklist directs
hand-authoring of the fixed-width layout; two files carry this ruling. Hand-authoring remains
permitted and becomes the declared exception, stating why. A revision declares whether its values
are derived or transcribed, so citation and derivation stop being indistinguishable.

**D8 — Staleness against the live official sources is checked on a schedule.** The detector in
`dev/corpus/sync_aeat_record_design_corpus.py` exists and is invoked by nothing; it is wired. Its
acceptance: it reports a detected republish as a finding against the corpus, it does not block a
change-triggered gate — the official sources are republished on a schedule no local change causes —
and an unreachable network is reported explicitly as a limitation rather than as either pass or
fail, per `aeat-local-execution`.

**D9 — A findings screen that carries a non-zero population is promoted or retired.** The screens
register already carries the distinction this needs: `ScreenEntry.entry_returns` separates
`findings` from `census`. This rules over `findings` screens only. A census screen that always
reports is legitimate and permanent, and is out of scope: a triage stage is legitimate, a triage
stage with no drain is not.

**D10 — An independent oracle is introduced.** Official worked examples — published records
carrying known values, including a negative amount — are decoded through the shipped codec and
compared field by field, so that at least one check does not originate in the generator. This is
not a new principle but unmet compliance with `aeat-calculation-grounding`, which already requires
cross-checking against an independent official example or oracle and rules that expected values
copied from the implementation under test are not evidence.

**Ordering.** D1a, D2 and D3 land first and fail closed. Because the two reproduction gates in
`dev/registry/tests/test_generated_export_trees.py` are parametrised over all 32 generated trees
and re-render each, a refusal landing on 22 of them would turn both gates red on the day it lands —
which the Constraints forbid. Refusals therefore land against
`dev/registry/pipeline/generated_tree_dispositions.toml`, one row per affected revision, each
pinning its source and its reconsideration condition. That ledger is a named, source-bound,
self-retiring set whose own gate fails when a pin goes dormant, and which states that it stores no
counts and no ceilings — so it is not the baseline the Constraints prohibit. Grounding retires rows
one design at a time. Correctness gates land last and green. D6 and D8 are independent.

**First repair target: modelo 347.** Surfaced independently by three instruments — the only modelo
whose manifest disagrees with its shipped declarations, whose monetary fields diverge across a
revision boundary, and whose two revisions are the only ones where check mode is never invoked. Its
defect is record-repeat and binding-rows, and its type cells are entirely the uncontrolled
vocabulary named in Considerations.

**First grounding target: modelo 390.** 347 carries no `N` or `Num` field and so clears no D1a or
D2 refusal; the two targets are separate work. 390 carries 1,236 of the 2,017 D2 refusals and is
the modelo whose fail-closed codec refusal blocks routine negative adjustments today.

## Rationale

The rulings follow from one observation: the pipeline's contract is asymmetric. It refuses
ambiguity and assumes contradiction. D2 removes the asymmetry, and does so at the level of the
class rather than the instance, which is why it and not D1 is the primary remedy — D1 fixes the
axes we found, D2 catches the axis we have not found yet.

D3 is what converts a defect that required a bespoke investigation into one visible in a diff. The
census was only possible because the join already existed in the artefacts; making the comparison
explicit in the attestation means the next such question is answerable by reading, not by
tooling.

D4 is deliberately modest about static typing. The evidence is that the failure was not a missing
value but a missing reading, that the values were typed by hand at every site, and that the
construction path defeats the checker. Overstating what typing buys here would misdirect effort;
understating the runtime boundary would ignore where this codebase actually enforces.

D6 accepts the cross-period proposal while refusing its stronger form. The measurement showed the
signal is informative in one direction only, and that the corpus's apparent stability on the very
axis under investigation is an artefact of that axis being exercised on a handful of identities.
A diagnostic that demands explanations is useful; a gate that reads agreement as correctness would
manufacture false confidence.

D7 addresses the trajectory rather than the stock. Given that new designs arrive yearly and are
revised within periods, an authoring default that produces hand transcription guarantees the
authored surface regrows faster than it is migrated.

## Consequences

**Accepted costs.** Affected revisions become unrenderable and unpublishable until grounded —
loud, blocking, and preferable to shipping an undetermined fact. The cost is measured: 2,017 fields
across 22 of 32 generated revisions, landing as disposition rows rather than as red gates.
Grounding is per-design review work, not a mechanical sweep, and the generated surface currently
depends on hand-written rules for nearly all correctly-signed fields, so this cost is real and
concentrated.

**What improves.** A regeneration begins to mean something: with D2 and D3 in place, output that
reproduces is output whose disagreements with its source were either absent or recorded. With D10,
one check no longer originates in the generator.

**Every new gate needs a planted defect.** D2, D3 and D6 each introduce a check, and
`aeat-quality-gates` requires each to demonstrate detection of a representative defect against an
isolated fixture or temporary tree. This is a condition of acceptance for those rulings, not a
follow-up.

**One premise remains unverified.** The claim that modelo 390's design carries a per-page legend
placing the sign in the first position rests on reading the official binary. It is the sole factual
basis for withdrawing the premise recorded against that modelo, and everything downstream of it —
D1a's application to 390, the bulk of D2's blast radius, and the deferred signed-or-unsigned
question — depends on it. It must be verified against the official document before the grounding
work proceeds, and this record does not treat it as established.

**What this record does not settle, and must not be read as settling.** How the consuming
application behaves when handed a registry that is internally inconsistent, temporally incoherent,
or partially adjudicated has not been examined at all — whether it refuses, degrades or proceeds;
whether a calculation can distinguish an adjudicated value from an undetermined one; whether
filing-grade paths distinguish a silent registry from one that says zero. The producer-side rigour
ruled here is worth little if the consumer accepts whatever it is given. That lane is opened next.
D1b and D5 are held explicitly on its answer, because it decides their primitive rather than
refining it; the rulings that are producer-only — D1a, D2, D3, D6, D7, D8, D9, D10 — do not depend
on it.

**Also deferred.** Whether the largest divergent population should ultimately be emitted signed, or
remain unsigned under a reviewed adjudication, is a per-design question for the grounding work and
is not decided here. D1a and D2 make the question unavoidable; they do not answer it. The existing
principle that a wire fact is declared and never guessed from a token stands and is not relaxed —
only the factual premise attached to one modelo is withdrawn, and "declared" gains a route for
fields whose content cell is populated.

**Amendment, 2026-09-09: the Ordering's ledger premise was false and is corrected.** The Ordering
above states that refusals land against the disposition ledger so the reproduction gates do not go
red. Measured against the live gate, that could not have worked: the gate calls the fresh render
unconditionally before it consults the ledger, so a refusal raises before any row can excuse it,
and the ledger model forbids extra fields and admits only the record-drift class, so a refusal row
would be rejected on load and would fail its own dormancy assertion. The mechanism is still right;
it was not yet capable. The plan therefore carries a prerequisite Phase that gives the ledger a
refusal class under a new schema version and moves the consultation ahead of the render, and no
refusal lands before it. The second reproduction gate is unaffected, because it resolves anchors
without rendering - which is why the refusal must stay in the export-tree module and not migrate
into the join.

**Amendment: the independent oracle extends an existing mechanism.** D10 is discharged by
extending the external-oracle corpus and grounding fold that already exist, not by building a
second oracle surface beside them; a parallel implementation would violate the canonical-definition
boundary. The bundled corpus already holds twenty-two worked-example payloads across several
modelos, so the constraint on D10 is whether any of them carries a negative amount in an affected
fixed-width slot, not whether material exists.

**Amendment, 2026-09-09: D2's contradiction definition is withdrawn, and D1a becomes the primary
remedy.** Executing the plan's first Phase produced the evidence that refutes it. The supposed
contradiction was that a width-17 row typed as signed needs a sign position, leaving sixteen digit
positions, while its content cell states fifteen integer and two decimal digits. The corporate tax
modelo's own official note resolves this in the design itself: the amounts are fifteen integer
digits, or the sign character plus fourteen, and two decimals. The sign displaces the leading
integer digit rather than demanding an eighteenth position, so the content cell describes the
non-negative capacity and no contradiction exists. Measured confirmation: that modelo carries
sixteen width-17 signed rows whose content cell is the same string, and its shipped declarations
treat them as signed and correct. A refusal on this arithmetic would therefore reject roughly two
thousand fields, including declarations this project already holds to be right.

The defect the corpus actually has is narrower and is what D1a names: the generator ignores the
type column for width-17 rows that carry no membership rule, and writes a literal in place of a
determination. D1a refuses exactly that and is clearable by declaring the rule. D2 is retained only
in the form that remains decidable in every reading - a row whose stated digits exceed its own
width - which is a much smaller class and may be empty. The ordering consequence is that the
prerequisite ledger Phase is still required, but the population it must absorb is far smaller than
the measured two thousand and seventeen, and is bounded by the revisions that lack a membership
rule rather than by the whole signed population.

This correction is the direct product of sequencing verification ahead of mechanism. Had the
refusal landed first, the false refusals would have been built, ledgered and then unpicked.

**Amendment, 2026-09-09 (later): the deferred representation question is ANSWERED, and D1a becomes
a derivation rather than a refusal.** This record deferred whether the largest divergent population
should be emitted signed, and treated one modelo's per-page legend as its sole unverified premise.
Both are now settled from a primary official source: AEAT's own "Disenos de registro - breve manual
de uso", version 2 of 12 December 2022, states the convention that governs every design. Numeric
fields are right-aligned and zero-filled and are carried without signs; only negative amounts are
preceded by the character N; and a numeric field with nothing to report is filled with zeros, not
blanks.

Three consequences follow, and none of them is a refinement.

The shipped codec was wrong, not merely ungrounded. It reserved a leading byte on every signed slot
and wrote a blank into it, and its parser refused a digit in that position, so it could not read a
correctly formed official record. The sign marker displaces the leading digit when the value is
negative and claims no byte otherwise, which is what the corporate-tax design means by "fifteen
integer digits, or N plus fourteen" on a seventeen-byte slot. That capacity had been
unrepresentable.

D1a therefore lands as a DERIVATION. The type column states the fact and the manual states the
representation, so the generator emits the sign rather than refusing it. The refusal was the right
posture while the representation was ungrounded and it is not the right posture now; the refusal
disposition rows this record's ordering created are retired by the same change that derives the
sign.

The unverified premise is withdrawn as a premise. The legend exists, at a stable cell in every
revision of that modelo, and it agrees with the general manual rather than standing alone. The
content cell that appeared to contradict the type column never did: it states the NON-NEGATIVE
capacity, which is why the same string sits on signed and unsigned rows throughout the corpus.

**What this says about the record's method.** Every ruling here was reasoned from the corpus, and
the corpus could not answer the question that mattered most; a published general manual could, and
it took one retrieval. The lesson is not that the analysis was wrong but that the authority
boundary was drawn too narrowly: "no source in this corpus states it" was read as "no source states
it". D10's independent oracle exists for exactly this gap and should be treated as load-bearing
rather than last.
