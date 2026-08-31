---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ebe50097db269579126ade76ff25115c692ae332142e53173f22971140476c15'
step_id: 'S63'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Audit every help string that makes a negative capability claim against the live policy declarations, including the never-file prohibition across all 294 leaves

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH live_write census..."` -> `0 of 294 leaves declare live_write`
- `verify:` `python -c "...app live family..."` -> `36 leaves, none declaring a live write`

## Notes

No code changed. This generalises S61 from one wrong help string to the class:
every help string that claims a capability is ABSENT, checked against what the
spec actually declares. A negative claim is the kind that gets stale silently,
because nothing breaks when a command quietly gains the power its help denies.

Nineteen help strings make such a claim. Twelve are the `app live` family
declaring itself read-only, which is the safety-critical posture
`sensitive-financial-data-secure-storage-only` states as "never perform live
AEAT submission".

The first pass at checking them was wrong and is recorded here because the error
is instructive. Selecting `app live` leaves whose `write_route != "none"`
returned twelve apparent contradictions -- every `pull` verb in the family. They
are not contradictions: `write_route` is the LOCAL storage axis and `live_write`
is the AEAT axis, and a `pull` that persists what it fetched is
`profile-bound` by definition. The help says "Read-only AEAT", scoped to the
axis that matters. Reading the flag without reading which axis it names produced
twelve false positives.

On the correct axis the result is clean and worth stating plainly: **zero of 294
leaves declare `live_write=True`.** The prohibition holds at the declaration
layer across the whole operator surface, with no exception and no allowlist. All
thirty-six `app live` leaves confirm their own claim.

Seven leaves declare a filing `handoff` -- the export verbs, `modelo work file`,
`reconcile import` and `spreadsheet push`. Those hand a filing artefact to the
operator to file outside the application, which is the sanctioned shape; none of
them submits.

Two other negative claims were checked and hold: `config storage check` says it
verifies "without repairing" and declares `write_route=none`; `config storage
reclaim` names itself for the space it frees but its help says plainly that it
deletes regenerable contents, and it declares `destructive=True`.
