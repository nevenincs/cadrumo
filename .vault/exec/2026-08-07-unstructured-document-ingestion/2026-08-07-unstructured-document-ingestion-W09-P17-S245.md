---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0e6498e116b0222acdcd385d969375569c4194383b678601763260d1ce9a9afa'
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

## Notes

**This Step is NOT complete and the row stays open.** What is finished is the anchor
axis, exhaustively and with controls. What is not started is the rest of what the row
asks for: category resolution and relief fixtures were not audited, and the export
axis was reached through a production probe rather than through its fixtures. Naming
that here rather than closing the row is the point -- an audit that measured one axis
well and reported a clean tree would read as a completed sweep.

The instrument generalises only where a producer invariant can be written down. The
anchor axis had two, because the grounding stage states them. Category resolution
would need the assembly's missing-input accounting evaluated at runtime rather than
by AST, which is a different instrument and not a widening of this one.

One minor honesty nit, deliberately not changed: the stale-stamp fixture in the party
attribution suite builds a structured envelope carrying an anchor under an unanchored
outcome, which that producer would not emit. It is input to a re-grounding pass, the
anchor plays no part in what the test asserts, and it certifies nothing false.
