---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S140'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh resolve the three creation flags that have no mapped fact path by reading the profile schema rather than inferring one

## Scope

- `src/cadrumo/domain/user_profile/ and src/cadrumo/entrypoints/cli/_config/`

## Description

- Read each flag's fact path from the authority that declares both together.
- Convert the three sites the missing mappings had blocked.

## Outcome

All three flags resolved from the wizard catalogue, which declares each flag's
identifier and its profile key in one place, so the mapping is read rather than
inferred.

**Two of the three would have been wrong if guessed, and wrong in the worst
available way.** Occurrence counting offers plausible paths for the marital
status and the new-entity profit-period exclusion — and both of those paths
exist in the tree, while neither is the key. A guess would therefore not have
failed loudly. It would have written a fact under a section nothing reads,
leaving the profile silently lacking the fact the test believed it declared,
**with every test still passing.** Wrong-and-green about a filer's marital
status.

That makes this the sharpest instance of the overloaded-vocabulary collision
this campaign has met. The earlier four produced wrong counts and wrong
premises; this one would have produced a wrong fact about a taxpayer, in a
fixture, invisibly.

**A third way to be wrong-and-green sat inside one of the same flags**, and
catching it required reading the catalogue's comment rather than only its
mapping. The new-entity exclusion is deliberately tri-state: undeclared reloads
as absent and is never collapsed onto a declared negative by a default the
operator did not approve. So the negative flag writes a positive false rather
than an absence. Treating it as "omit the fact" would have declared UNDECLARED
where the test meant DECLARED FALSE — the same silent-wrongness one level down.

None of the three was a dead flag, which closes the alternative outcome the row
asked about: all three are live catalogue questions with real keys, so the gap
was a missing mapping in the conversion tool rather than a stale CLI surface.

Three previously blocked conversions landed with it.

## Notes

One conversion is landed UNVERIFIED and needs a re-run. A concurrent campaign's
half-finished package extraction leaves a module unimportable tree-wide, so that
suite cannot be collected at all. It is recorded here rather than in the commit
message because on this tree a commit message is not a reliable home for a
caveat — peer sweep commits routinely claim the work before its author can
describe it.

The reusable warning is about negative CLI flags generally rather than about
this one: where a domain deliberately distinguishes undeclared from declared
negative, a flag that reads as "turn this off" writes a value rather than
omitting one, and a fixture that omits it declares something different from what
its author intended.
