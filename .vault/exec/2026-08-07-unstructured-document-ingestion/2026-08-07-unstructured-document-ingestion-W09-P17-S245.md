---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:42da9da6d20ad74a0b23a433a766ac64d5b6c40069b5782668175fb3d7077f6d'
step_id: 'S245'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Audit this campaign's fixtures for shapes no producer emits, the inverse of the drive-the-real-producer discipline. A notice fixture was found building a CARRIED anchor under an UNANCHORED outcome, which no producer at that surface emits, and because the gate asserted that shape was correct it DEFENDED the conflation of three states into two notices. So the fixture did not merely miss the defect, it certified it. The discriminating question per fixture is whether its shape was hand-built from what the code currently DOES or derived from what a producer actually EMITS, and the first is how a gate comes to protect the behaviour it was written to constrain. Four other instances landed this campaign already: three export fixtures asserting routing from rows recording no counterparty country, with a docstring saying so, and a feed-parity fixture placing one party in the US and the other nowhere on the very axis it existed to prove agreement about. Prioritise fixtures on the money paths, category resolution, relief and export routing, over presentation surfaces

## Scope

- `src/cadrumo`

## Description

- Build an AST instrument over every test module, keyed on two invariants read off the grounding stage rather than off the fixtures.
- Correct it once: its first five findings were all artefacts, and the correction widened it to bare envelopes, which is where the originating instance lived.
- Give each invariant a positive control before reading its zero.
- Adjudicate by hand the five shapes the instrument declines to judge.
- Probe the export routing arm on the money path, with controls in both directions.

## Outcome

**The anchor axis is clean, and the reading is controlled.** Two producer invariants
were scanned across 2685 test modules: an ANCHORED stamp on a value that is not the
deterministic parse of its own anchor, and a post-grounding unanchored envelope
carrying an anchor without the self-reported flag. Zero real instances.

That zero is only worth stating because both invariants fire on a control. The
originating fixture, recovered from history, is found by the instrument; a synthetic
fixture stamping ANCHORED on a mismatched pair is found on both the decimal and the
textual arm.

**The first instrument was wrong in both directions and its output looked plausible.**
It reported five findings. Two came from comparing a decimal literal as a string, so
an anchor that parses correctly read as a mismatch. Three came from flagging
envelopes deliberately fed INTO the grounding stage as though they were claims about
its output. A homogeneous finding set of five, every member an artefact, is the tell
that the instrument rather than the tree is being measured.

Correcting it also widened it. The first walk only saw envelopes written inline
inside a draft literal, and the originating instance was a module-level helper
returning a bare envelope -- so the instrument as first written could not have found
the very defect that motivated the row.

**The exemption is small enough to adjudicate rather than trust.** A module that
calls a real producer is exempt, because a reader-shaped envelope there is input
rather than a claim. That exempts five shapes, all read: three are inputs to the
grounding stage, one is a shape a producer-reachability test proves emittable, and
one is a deliberately stale envelope fed into a re-stamping pass to prove the pass
does not latch.

**A money-path finding that I reported and have since RETRACTED.** The counterparty
coupling gate has two arms, and the export one tests its country against the Member
State set without first requiring a country to exist, while the intra-community arm
two lines above demands a positive fact. I probed it, saw an absent country route as
a third country would, and reported a live under-declaration.

It is not one. The probe used a duck-typed stub that allowed an absent country; the
real invoice model requires the field and refuses an omitted, null, blank,
ISO-unassigned or malformed value outright, so the empty string cannot reach that
site. The two arms differ because their input contracts differ -- the bank path's
country is genuinely nullable and guards accordingly -- not because a ruling was
applied to one and not the other.

The error is the one this very row exists to catch. I asserted behaviour over an
input shape no producer emits, which is the row's own discriminating question asked
of fixtures and not of my own instrument. What remains is a latent coupling rather
than a defect: the arm's correctness rests on a validator in another module, and it
would fail open silently if that field ever became optional, with no test able to
notice because no test can build the input today.

## Verification

    uv run --no-sync python <scratch>/audit_fixture_shapes.py src/cadrumo
    0 candidate fixture shapes across 2685 test modules

Positive control, invariant B, against the originating fixture recovered from
history:

    control/test_evidence_field_notices.py:54: B UNANCHORED 'grand_total' carries anchor='4.528,32', not self-reported, module drives no producer
    1 candidate fixture shapes across 1 test modules

Positive control, invariant A, on both the decimal and the textual arm:

    controlA/test_synthetic_control.py:7: A ANCHORED 'taxable_base' anchor='100,00' parses to 100.00, draft states 250.00
    controlA/test_synthetic_control.py:13: A ANCHORED 'currency' anchor='USD' != value 'EUR'
    2 candidate fixture shapes across 1 test modules

The exempted population, measured rather than assumed:

    5 shapes exempted by the module-level producer test

The export arm, probed with controls -- a sound reading of an unreachable input,
recorded because the probe's soundness is exactly what made the conclusion
convincing:

    EXPORT arm
      third country US        -> routes=True
      member state DE         -> routes=False
      ABSENT country (None)   -> routes=True
      ABSENT country (blank)  -> routes=True
    INTRA-COMMUNITY arm, for comparison
      identified DE           -> routes=True
      identified ES           -> routes=False
      ABSENT identification   -> routes=False

The real invoice model, asked whether that input can exist at all:

    control: the factory produced country='CH'
      omitted        -> REFUSED (('counterparty_country',): missing)
      None           -> REFUSED (('counterparty_country',): string_type)
      blank '  '     -> REFUSED (value_error)
      unassigned XX  -> REFUSED (value_error)
      malformed ZZZ  -> REFUSED (value_error)

Every probe ran from outside the repository; nothing under source control was
modified by this Step. A production edit made on the retracted premise was reverted
by hand, hunk by hand-written hunk, because the module carries eighteen peer hunks
and writing HEAD bytes over it was not available.

## Category resolution: instrumented, not concluded

The runtime instrument the anchor axis could not provide now exists. It intercepts
every construction of the classification criteria model wherever it happens, and
splits the constructions in two by call stack: those passing through the assembly,
which production really emits, and every other, which is a test stating a
combination itself. A combination asserted but never emitted is the candidate.

**Its first version reported a clean zero over 1949 passing tests and was measuring
nothing.** It wrapped the pydantic post-init hook, which the model binds once at
class construction and never re-reads, so the rebinding took hold and never fired.
A dead hook is indistinguishable from a tree with nothing to find. The instrument
now proves itself before the suite runs: it constructs one criteria object and
requires the counter to move, and aborts if it does not.

**The headline number is dominated by a test doing exactly the right thing.** Of 287
asserted-but-never-emitted combinations, 275 come from ONE site: a deliberate
exhaustive product sweep over the whole criteria space, which exists to prove no
rule in the table reads the customer status. Visiting shapes the assembly may never
produce is that test's purpose, not its defect. Reading the members rather than the
count is what separates the two, and the count alone would have produced 275 false
findings.

**The remaining twelve are candidates the instrument cannot adjudicate, and the
limit is the denominator.** They are domain rule-table tests, whose contract is
criteria in and category out, and the combinations they state look emittable -- one
is a domestic Spanish pair whose customer holds a German VAT identification, which
is precisely the establishment-versus-identification split this campaign established
as real. The producer set they were measured against holds 52 combinations harvested
from four test modules, so "never emitted" here means "not emitted by those four",
which is not the question.

**That is a design fault in the instrument, not a gap in the run.** Harvesting the
producer's output from incidental test execution makes the denominator a property of
whichever suite was run. The suite-independent denominator is the assembly's own
output space: drive the assembly across the cross-product of its INPUTS and collect
what it emits. Until that lands, no combination should be called unreachable.

## Verification, category axis

    control: the hook fired (0 -> 1), counters reset
    1949 passed, 26 deselected, 16 warnings in 318.84s   [unit lane]

    producer-emitted : 52 distinct, 210 constructions
    test-asserted    : 303 distinct, 355 constructions
    unreachable      : 287 distinct, 333 constructions
      275 distinct at test_classification_assembly.py:848   (the exhaustive sweep)
       12 distinct across domain rule-table tests           (candidates, denominator-limited)

## The suite-independent denominator now exists

The enumerator drives the assembly across the cross-product of its own inputs and
collects what comes back, so what counts as emittable is a property of the producer
rather than of whichever suite ran. Every axis is derived from its authority -- the
enums themselves, and the bundled country vocabulary the scope resolver consults --
because a hand-listed axis pins today's catalogue exactly as a hand-listed country
list once did.

Two axes are collapsed BY the producer's own gating rather than by judgement about
the rule table. Country and postal are paired instead of crossed, since the postal
half is consulted only where the country names Spain; and one country per distinct
territorial scope is enough, since the assembly reads a country only through the
scope it resolves to.

**It found the previous denominator wrong by a factor of eighty-five, and that is
the deliverable.** 52 harvested shapes against 4438 enumerated ones. 103 of the
combinations the harvested run called unreachable are emittable -- false positives
that a list of names would have sent someone to investigate.

**What remains is 192, of which 177 are the exhaustive sweep** that exists to visit
shapes the assembly may never produce. The residue is roughly fifteen domain
rule-table tests, one combination each, now measured against a denominator that can
be defended.

**They are still not findings, and the reason is now narrow rather than fundamental.**
The enumerated space is a subset of the true one: the collapsed axes are justified by
the producer's gating, but justified is not proven, and a shape the collapse excludes
would read as unreachable exactly as a real instance does. Closing that gap means
proving each collapse cannot lose a shape, which is the next step rather than a
caveat to attach to a list.

## Verification, enumerator

    assembly calls made        : 31488
    calls that emitted criteria: 6874
    DISTINCT EMITTABLE SHAPES  : 4438

    harvested denominator      : 52 shapes
    enumerated denominator     : 4438 shapes
    asserted shapes            : 303
    UNREACHABLE against enumerated: 192
    cleared by the better denominator: 103
      177 at test_classification_assembly.py:848   (the exhaustive sweep)

The enumerator refuses to report at all if it emitted nothing, so a comparison can
never be drawn against an empty denominator -- the control the harvesting instrument
lacked, in the form the dead hook taught.

## Relief axis: a measured zero, and the instrument defect that nearly wasn't

Instrumented the way the category axis ENDED rather than the way it began: the
denominator is enumerated from the producers, composing the assembly enumerator
rather than restating it, and never harvested from whichever suite ran.

**Its first run reported five findings, and all five were the instrument.** Every
one carried ``direction=None`` -- a value the guard's own signature admits and my
enumerated axis never produced, because I ranged over the enum members and not
over the declared type. A homogeneous finding set, suspected rather than reported,
and reading the members found the shared characteristic in one pass. Widening the
axis to the type the guard actually declares took the count to zero.

**Zero unreachable, against a denominator of 3120 reachable inputs**, with the
guard shown capable of answering both ways so the comparison is against a gate
rather than a constant.

A control the reachable-side assertions did not give me was added after an earlier
run: a collection failure had left the ASSERTED population empty, and "0
unreachable" over an empty numerator reads exactly like a clean axis. Both sides of
a set difference need a non-emptiness proof, not only the denominator.

The asserted population is 14 distinct inputs from three modules, which bounds the
claim: no test in those modules exercises the relief guard with an input production
cannot assemble. It does not say the whole tree is clean.

## Verification, relief axis

    reachable guard inputs : 3120
    guard verdicts observed: {'honoured': 3589344, 'refused': 189216}
    asserted inputs   : 14 distinct, 37 calls
    UNREACHABLE       : 0 distinct
    3 failed, 62 passed        [the three are a peer's in-flight reverse-charge work]

## Notes

**This Step is NOT complete and the row stays open.** The anchor axis is finished,
exhaustively and with controls. The category axis has its
suite-independent denominator and roughly fifteen surviving candidates, which stay
candidates until the enumerator's collapsed axes are proven lossless. The relief axis is measured clean with
controls both ways. The export axis produced a retracted claim rather than an audit,
and remains the one axis with no instrument.

The instrument generalises only where a producer invariant can be written down. The
anchor axis had two, because the grounding stage states them. Category resolution
would need the assembly's missing-input accounting evaluated at runtime rather than
by AST, which is a different instrument and not a widening of this one.

One minor honesty nit, deliberately not changed: the stale-stamp fixture in the party
attribution suite builds a structured envelope carrying an anchor under an unanchored
outcome, which that producer would not emit. It is input to a re-grounding pass, the
anchor plays no part in what the test asserts, and it certifies nothing false.
