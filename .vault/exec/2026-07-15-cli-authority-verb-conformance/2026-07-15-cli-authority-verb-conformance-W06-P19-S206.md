---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S206'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Confirm every semantic candidate with exact declaration, import, export, caller, writer, persistence, CLI, schema, locale, test, documentation, and generated-artifact searches before classification

## Scope

- `src/cadrumo/`
- `dev/`
- `docs/`
- `.github/`
- `justfile`

## Description

Confirm every semantic candidate with exact declaration, import, export, caller, writer,
persistence, CLI, schema and generated-artefact searches before classification.

## Outcome

SATISFIED as the substitute for a degraded semantic instrument, not as a confirmation of it.

The semantic sweep under S205 produced no usable candidate: every one of its ten results was a
miss. There was therefore nothing to confirm and everything to establish from scratch. All ten
clusters were resolved by exact search over declarations, consumers, writers and the live CLI leaf
dump, and by reading the owning modules.

Declaration counts, each obtained by an exact search whose output shape was verified rather than
assumed. The clone-detection command builder and its version constant: one site each, both in the
audit duplication runner. The bytes and file digest helpers: one site each, in the core hashing
module. The secure-object namespace definition model: one site. The attachment store class: one
declaration with seven production construction sites, all routing through it. The certificate
secret backend protocol: one, with exactly one implementation. The profile bundle export and
serialise entry points: one site each. The revision selector and the validated authority snapshot
method: one site each. The official-source-kind frozenset that gates cross-period clean state: one
declaration, every other occurrence being documentation prose that names it.

Absence was established the same way. The evidence service exposes build, show, check and export
and no replay method, and the live CLI leaf dump carries audit check, audit export and audit show
with no replay verb. Certificate secrets do not reach the OS keychain: the only two production
keychain writes are the master key and the persisted session, neither a certificate.

## Notes

One methodological correction is recorded because it nearly produced a false negative. An
early consumer sweep filtered test files with a forward-slash path pattern while the search tool
emits Windows separators, so the filter matched nothing and the production sites were hidden
behind test noise. The pattern was corrected to the tool's actual output shape and the sweep
re-run. An empty result from a pattern that cannot match the data is not evidence of absence, and
this Phase treated it as a defect in the query rather than a finding.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-verified 2026-07-28 at HEAD `a4534b8a2bfbf9d9d95eed883f98d2098a437ec0`

Written three days after the sections above, against a tree that has moved. The
figures below supersede any that conflict; nothing above is edited, so the
original measurement stays readable next to what it became.

The confirmations recorded above stand, and their conclusions have since been
acted on rather than left as findings: every cluster this Step resolved by
exact search now has its canonical owner in place, the four duplicate
declarations it identified having been retired under their own Steps.

Re-confirmed at this HEAD by exact search rather than by re-reading the entry:
the four retired symbols no longer collide in a fresh structural scan over 1411
production modules and 4250 hashed bodies. The confirmation method is unchanged
- exact search over declarations, consumers, writers and the live command tree,
plus reading the owning modules - because the semantic instrument is still
unusable and is now measurably worse, at 20 indexed sections.

One correction to how this Step's result should be read. It is SATISFIED as a
confirmation method, not as evidence that no unconfirmed candidate remains: the
fresh scan surfaces 25 cross-file collision groups that have NOT been through
the substitutability pre-filter. They are a named residue, not a clean sheet.

Command and result for the structural scan cited above, added because the
evidence bar asks for the invocation and not only its corpus. The scanner was
run as a standalone module against the production tree:
`python ast_twin_scan.py` over `src/cadrumo`, production modules only, 70-node
floor. Result line: `corpus: 1411 production modules, 4250 bodies hashed, 0
unparseable` followed by `collision groups: 39 total, 25 spanning more than one
file`, exit code 0. Its discrimination proof printed first and must pass or the
run aborts: `discrimination: twins collide = True (want True); control collides
= False (want False)`.
