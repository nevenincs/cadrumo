---
tags:
  - '#adr'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:06df6ff3b3bd476480d3f63daaf1f0b262056162d45eb34f8bdfdf3e8beb10c4'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - '[[2026-08-10-aeat-export-fragment-generator-authority-s08-authority-gap-research]]'
---
# `aeat-export-fragment-generator-authority` adr: `the export-tree lifecycle needs an operator invocation surface` | (**status:** `proposed`)

## Problem Statement

The generated export-tree pipeline has a complete authority and no way for a person
to invoke it. Both entry points are reachable only from pytest: `check_generated_export_tree`
is referenced by the pipeline re-export and two test modules, and
`publish_validated_generated_export_tree` by its own module, the re-export and one
test module. No CLI verb, `__main__`, script or console entry point drives either.

This is not theoretical debt. Two enrolled trees are owed and cannot be satisfied,
and every remaining row-binding repair is stuck behind the same wall: any change to
a semantic map alters the fresh render, which makes the committed tree differ, which
reds the enrolment gate until the tree is republished — and republishing is the thing
that cannot be done. A decision is needed now because the work queued behind it is
otherwise permanently unlandable, not merely delayed.

## Considerations

- The authority itself is sound and is not what is in question. Check mode validates a
  candidate through the real loader and refuses on unreviewed schema keys at every
  projection level. Grounding: `2026-08-31-aeat-export-fragment-generator-authority-semantic-map-cannot-express-binding-rows-audit`.
- The separation of check from publish is deliberate and gated: the check module is
  asserted to carry no publisher surface. Any surface must preserve that split.
- Publication is transactional — journal, backup sibling, cutover, post-cutover
  manifest and digest verification, recovery on interrupt. A surface must drive that
  path, never reimplement or bypass it.
- The convention already exists elsewhere in the same tree: the aeip, locales,
  identity and docs development lanes each ship their own entry point. The export
  pipeline is the exception rather than the rule.
- Publication writes shipped registry content, so the surface is a privileged
  development tool and must not become a user-facing capability.

## Considered options

- **A development CLI verb pair, check and publish, in the owning dev lane.** Matches
  the existing per-lane entry-point convention, keeps the two modes distinct, and
  drives the real transactional publisher. Chosen.
- **Publish only, leaving check test-only.** Rejected: an operator who can publish but
  cannot first ask whether a committed tree still reproduces has only the dangerous
  half of the pipeline.
- **Extend the product CLI.** Rejected: the product's root surface is fixed at two
  families and this is a development tool that writes bundled registry content; it is
  not a taxpayer-facing capability.
- **Keep it test-only and treat a passing enrolment row as publication.** Rejected: a
  test asserts a tree already matches, which cannot produce a tree that does not yet
  exist, and it would put registry writes inside the test suite.
- **Do nothing.** Rejected: it makes the owed trees permanently owed and converts every
  future map correction into an unlandable change, which is a slow ratchet toward
  committed trees that no longer reproduce from their own authored inputs.

## Constraints

No new dependency and no change to the authority. The surface is a thin driver over
existing functions, so the risk is concentrated in argument handling and in resolving
the target rather than in the pipeline. It must inherit the publisher's exclusive lock
and journal semantics rather than reimplementing them. It depends on nothing unlanded.

## Implementation

A development entry point in the lane that owns the pipeline, exposing two verbs over
one target selector of modelo, revision, source and filing context. Check regenerates
into an isolated candidate, validates it through the real loader and reports whether
the published tree still attests to the same authorities and bytes, changing nothing.
Publish runs the same validation as its pre-cutover proof and then drives the existing
transactional swap. Both refuse rather than guess when the target is ambiguous, and
publish additionally refuses when check would not pass, so the destructive verb is
never the first question asked. The enrolment rows stay the regression gate; the
surface exists to satisfy them, not to replace them.

## Rationale

The knockout is that the alternatives all leave a capability the project already
depends on reachable only from a test runner. The audit cited above establishes that
the authority is complete and correct, which means the missing piece is reachability
alone — the cheapest possible fix for the largest blocked queue. Choosing the dev-lane
verb pair also keeps the privileged operation out of the product surface, which is
what makes it safe to give an operator at all.

## Consequences

The two owed trees become satisfiable and the queued row-binding repairs become
landable, including the ones currently blocked in another lane. Publication becomes
an auditable operator action rather than an undocumented one.

The reach is wider than the two rows, and this was measured rather than assumed.
Modelo 200's revisions both declare `authority_grade = "calculation"`, and each
states the same reason in its own comment: filing refuses until the canonical
generator publishes the exact design for that ejercicio. That is the tree this
decision is about. So the missing surface does not merely leave two enrolment rows
red -- it holds a modelo below filing grade, which in turn refuses every request
for a filing snapshot of it. Seven of the eleven failures in the filing
export-proof lane are that refusal, arriving there rather than here.

A fourth gate fails on the same absence, in a fourth module. The declared-casilla
walk admits a revision only when it carries an export layout, and modelo 200
carries none on either revision -- confirmed against the loaded authority rather
than a directory listing. So the modelo is enrolled among those the walk must
reach and is never reached, and that gate refuses correctly.

One capability accounts for the owed trees, the modelo's grade, the seven
export-proof refusals, and this walk.

The honest difficulty is that a publish verb makes it materially easier to overwrite
shipped registry content, which today is effectively impossible. That is the point of
the change and also its main hazard, which is why publish is specified to refuse when
check does not pass, and why the transactional path with its rollback sibling is
non-negotiable rather than an implementation detail.

This does not resolve whether a given committed tree should be reproducible at all.
One tree is known to contain a subdivision of a design slot that no semantic map can
express, and a surface to publish it does not make that expressible.
