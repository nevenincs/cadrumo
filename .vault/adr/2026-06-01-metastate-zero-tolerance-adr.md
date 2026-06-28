---
tags:
  - '#adr'
  - '#metastate-zero-tolerance'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
  - "[[2026-06-01-metastate-zero-tolerance-research]]"
---

# `metastate-zero-tolerance` adr: no migration-progress state in production code | (**status:** `accepted`)

## Problem Statement

Production code repeatedly accreted lists, sets, dictionaries, and
comments tracking the progress of in-flight refactors: "modules still
to enroll", "callers still on the legacy API", "fixtures pending
migration", "wave-3 not-yet-completed slots". These transient
artefacts outlive the project that introduced them, mislead future
readers about the structural state of the codebase, and create a
recurring cleanup tax that itself becomes a campaign. The pattern is
worst when the list lives inside the gate that is supposed to enforce
the rule, because the gate then enforces the migration's intermediate
state rather than its destination.

## Considerations

Three places where migration metastate accumulates were inventoried:
coverage gates that carry an allowlist of "modules without paired
tests yet"; protocol registration sites that maintain an inline list of
"concrete classes not yet behind a Protocol"; docstrings and comments
that name the wave, phase, or step that introduced the current shape.
All three are process notes that have leaked into the artifact.

## Constraints

The rule must be enforceable without code-style heuristics. It must
apply uniformly to gates, registries, fixtures, schemas, public APIs,
and tests. It must not be relaxed for "temporary" lists, because every
historical metastate list was justified as temporary when it landed.

## Implementation

Three acceptable outcomes when a migration introduces a list of
in-flight items:

- Drive the migration to completion in the same commit and delete the
  list. The destination state is the only state allowed to land.
- If the list cannot be eliminated this commit, attach an inline
  rationale next to each entry that justifies the entry on durable
  structural grounds (e.g. "browser-only dependency", "python -m entry
  point"), not on transient grounds ("not yet enrolled", "wave 3
  pending"). This converts the list from a metastate to a rule with
  per-entry justification.
- Delete the list because the constraint it encodes was a process
  artefact that does not need to be enforced at all.

`COVERAGE_GAPS` retirement (see the related
coverage-canonicalisation audit) is the canonical worked example: a
66-entry "modules without tests yet" allowlist was retired in one
commit, leaving a 9-entry `_EXEMPTIONS` set where every entry carries
a durable rationale comment.

## Rationale

Migration-progress lists are write-once, read-by-search-only artefacts
whose accuracy decays from the moment they land. Their presence
obscures the true structural state of the system and shifts the cost
of correctness from the migration owner to every future reader.
Replacing them with either complete enrollment or per-entry rationale
keeps the artefact's claims true over time.

## Consequences

Refactors must either finish in their landing commit or leave behind a
durable rule, never a transient list. The discipline is enforced by
review (this ADR + the standing-review-gate G5 in the project memory),
not by an automated detector, because the false-positive shape of "is
this list metastate or a real rule" requires human judgement on the
per-entry rationale. The rule is absolute: "we'll clean this up later"
is the canonical violation.
