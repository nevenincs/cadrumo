---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:142e0aaf1384144367335700162a63e131a394194ac926c9d87644bf18907761'
step_id: 'S245'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S245 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Audit this campaign's fixtures for shapes no producer emits, the inverse of the drive-the-real-producer discipline. A notice fixture was found building a CARRIED anchor under an UNANCHORED outcome, which no producer at that surface emits, and because the gate asserted that shape was correct it DEFENDED the conflation of three states into two notices. So the fixture did not merely miss the defect, it certified it. The discriminating question per fixture is whether its shape was hand-built from what the code currently DOES or derived from what a producer actually EMITS, and the first is how a gate comes to protect the behaviour it was written to constrain. Four other instances landed this campaign already: three export fixtures asserting routing from rows recording no counterparty country, with a docstring saying so, and a feed-parity fixture placing one party in the US and the other nowhere on the very axis it existed to prove agreement about. Prioritise fixtures on the money paths, category resolution, relief and export routing, over presentation surfaces and ## Scope

- `src/cadrumo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

**A money-path finding that is production rather than fixture.** The counterparty
coupling gate has two arms. The intra-community arm withholds on an absent
identification and its docstring states the principle: absent is absent, and it does
not fall back to the address. The export arm reads the counterparty country and
treats ABSENT as a non-EU country, so a base whose row records no country routes as
an export exactly as a genuine third-country row does.

Measured, with controls in both directions so a gate that says yes to everything
would be visible: a third country routes, a Member State withholds, and both an
absent and a blank country route.

This is the defect the three export fixtures cited in the row were certifying.
Correcting only those fixtures would leave it live, which is why it is reported as
its own finding rather than absorbed here.

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

The export arm, probed with controls:

    EXPORT arm
      third country US        -> routes=True
      member state DE         -> routes=False
      ABSENT country (None)   -> routes=True
      ABSENT country (blank)  -> routes=True
    INTRA-COMMUNITY arm, for comparison
      identified DE           -> routes=True
      identified ES           -> routes=False
      ABSENT identification   -> routes=False

Every probe ran from outside the repository; nothing under source control was
modified by this Step.

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
