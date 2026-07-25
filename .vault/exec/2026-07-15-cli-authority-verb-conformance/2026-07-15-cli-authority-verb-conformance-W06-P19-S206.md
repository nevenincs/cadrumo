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
