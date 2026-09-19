---
tags:
  - '#audit'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9765f41d623e4493b237ddbfa7eab72e2011743a7157c2ecb89d41c6ec2e5aed'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-31-tui-interface-path-keyed-evidence-classification-adr]]"
---

# `tui-interface` audit: `final interface review`

## Scope

The interface cohort's architecture, security, accessibility, redeclaration and
scope posture, reviewed at the point where the plan's C1-C4 rows closed.

**THIS IS NOT AN INDEPENDENT REVIEW, and recording it as one would be the first
finding.** The row asks for independence; I authored most of the work under
review, so the reviewer and the author are the same. Two things follow. The
project's own documentation rule retires reviewer TOPOLOGY as a requirement --
"no document requires a particular number or topology of reviewers" -- so the
absence of a second party does not by itself invalidate the review. But the
failure mode independence protects against is real and unaddressed here: a
self-review cannot see the assumption its author did not know they made. Every
finding below is therefore stated with the evidence that produced it, so a
later reader can re-derive it rather than trust it.

The row also predicates itself on "the green C5 receipt". That receipt family
was retired outright, so no such artefact can exist. The review is against the
surviving evidence instead: the conformance suites, the boundary contracts, and
the gates named below.

## Findings

### architecture-boundaries-hold-and-one-was-unguarded | medium | the TUI reaches nowhere it should not, and one of those zeros had nothing keeping it at zero

An AST enumeration of every non-test TUI module returns zero CLI reaches, zero
private-registry reaches, and a single adapter reach in the launcher, which a
contract permits. The boundary posture is therefore sound in fact.

It was not sound in ENFORCEMENT. Nothing forbade the TUI importing a sibling
entrypoint: the existing prohibition covers only the reverse direction. A
contract now closes that, and reports KEPT against the live tree.

A second architectural property is worth recording because it was achieved
rather than found: every area now exposes mountable screens, and the only
application classes remaining are the shared host plus three launch wrappers
over it. The root's inability to compose them is a missing navigation DESIGN,
not a missing precondition.

### accessibility-is-partly-proven-and-the-limit-must-not-be-overread | high | the theme gate proves appearance is not load-bearing, and cannot prove any state is legible without colour

Every routed destination is proven to paint identical glyphs and offer an
identical keyboard order under both appearances, with a control asserting the
two themes genuinely differ. That catches a palette that drops text from the
frame, a layout that reflows, and a status whose wording changes.

It does NOT catch a validation failure signalled only by a red border: that
renders identical glyphs under both themes and passes. The property is not
decidable from two frames of one state -- it needs a comparison between the
FAILING and PASSING states. Anyone reading the green as "every state is legible
without colour" would reach a conclusion the gate does not support. This is the
largest open accessibility gap in the cohort.

Keyboard reachability is separately proven at the smallest supported terminal,
which is where a control gets pushed out of the layout rather than merely
crowded.

### locale-invariance-is-asserted-over-an-axis-that-does-not-move | high | all four shipped catalogues render byte-identical frames, so the invariance assertions are currently weak

The destinations mount an identical control set in an identical order across
all four languages. That is asserted, and it passes -- but every catalogue
resolves to the same source language for this content, so the comparison is
between copies of one input.

Two causes, both measured: the destinations' chrome renders through the AMBIENT
output language rather than the session's, so a screen has two language
authorities; and the workspace content carries no translations, so every
request falls back. The suite now asserts that resolution state explicitly, so
the day a translation lands the assertion fails and announces that the axis has
become live. Until then the invariance claim should be read as unfalsified
rather than as proven.

### no-sensitive-payload-reached-a-fixture-or-a-log | low | the fixtures are synthetic and the surfaces that mask do so

Every fixture added to this cohort seeds through the encrypted profile boundary
with synthetic facts; no real identity, credential or banking value appears.
The masking property for secret surfaces is exercised by an existing gate that
asserts a modal never paints its value.

One limit, stated because it was tested and rejected rather than assumed: a
scan that refuses checksum-valid Spanish identifiers in fixtures would be
wrong. Synthetic test identifiers must often be checksum-valid precisely
because the code under test validates them, so structural validity does not
separate real from synthetic and no decidable property does.

### redeclaration-was-real-and-is-now-removed | high | four implementations of one host existed, three of them carrying the same latent race

A semantic sweep found the shared screen host reimplemented eleven times, three
of those in production. All eleven carried a fire-and-forget screen push, the
race the shared host's own docstring exists to document, and that race had
already manifested twice independently in this cohort. The count of un-awaited
pushes in the TUI tree is now zero.

Two further duplications were removed with them: a redundant second channel
carrying a value the run result already returned, and a workspace seeding
fixture that lived inside one package's private conftest and would have been
copied by the second suite that needed it.

### scope-held-except-where-a-defect-forced-a-production-change | medium | the cohort is test-facing, and one production fix was unavoidable and is the most valuable output

The work is overwhelmingly gates and fixtures. Three production changes were
made and each is justified in its row: the host consolidation, the screens'
switch from reaching into their host to dismissing, and a bound in the
workspace models.

That last one was not planned. Adding a dense real address to a geometry suite
revealed that a lowercase-only locale-key bound rejected a key its own encoder
produces, which made every workspace destination unopenable for Modelo 100 --
the largest IRPF form. It is fixed and gated both ways. A geometry suite
finding a filing-surface outage is a scope excursion in the direction that
matters, and it is recorded here because it argues for enrolling real dense
addresses in more of the cohort rather than fewer.

## Recommendations

The accessibility gap is the one to take next: a comparison between failing and
passing states, which is a different fixture shape from anything the cohort has
now. The locale axis becomes testable only after the ambient-language
composition defect is resolved, and that dependency is recorded on both rows.
