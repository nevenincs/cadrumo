---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0358c7e766fc405c44f23b78697e6e40b2b775d2bc98cdc874a051b96a1b0258'
step_id: 'S27'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Build and run a repo-wide drift detector over src/cadrumo AND dev/, not the registry package alone, explicitly naming the design-prose grammar in dev/registry/_export_tree.py (regex-parsing Spanish AEAT design prose patterns such as "15 enteros y 2 decimales", Constante "00500", and trailing Nota N references to derive filing wire facts) as a known in-scope instance alongside dev/registry/mappings/ and dev/registry/render_profiles/, finding regulatory numeric literals, year sets and modelo-conditional branches outside the sanctioned channels of registry TOML, core external_constants and the allowlisted math constants, with every allowlist entry stating its reason and keyed by path and enclosing function, and persist the census as a vault audit where every finding is enrolled as a plan row or formally deferred with a reference, gated on zero unclassified findings and on a re-run reproducing the census exactly

## Scope

- `dev/`
- `dev/registry/_export_tree.py`
- `dev/registry/mappings/`
- `dev/registry/render_profiles/`
- `src/cadrumo/`
- `.vault/audit/`

## Description

- Add `dev/quality/regulatory_drift_census.py`: eight AST detectors over every
  production module under `src/cadrumo` and `dev`, findings keyed by path,
  enclosing symbol, kind and detail and never by line number, with a `tests`
  scope measured separately.
- Add `dev/quality/regulatory_drift_dispositions.toml`: the reviewed ledger, nine
  shared reasonings authored once and referenced by id, every decision naming one
  file, every allowlist entry naming a file and an enclosing symbol.
- Add the gate under `src/cadrumo/tests/`: zero unadjudicated, zero stale rows,
  zero ambiguous matches, a re-run reproducing the census exactly, the detector
  recovering each instance the plan names, a planted finding refused, and a
  directory-scoped allowlist entry refused at load.
- Persist the census as a vault audit with ten findings, each dispositioned.

## Outcome

614 findings across 239 files and directories, all adjudicated: 253 enrolled to a
plan row, 336 deferred against the census audit, 25 allowlisted as not regulatory
data. Zero unadjudicated, zero stale, zero ambiguous. Enrolments land on five
rows: 104 on the supported-filing-years row, 8 on the embed classifier, 2 on the
dev artefact collapse, and one each on the applicability migrator and the embed
migration.

All three instances the row names as known prior art are recovered
independently: 27 modelo-keyed entries in the applicability table, nine findings
across four kinds in the M303 orden constants including SUPPORTED_EJERCICIOS and
the seasonal coefficients, and five design-prose grammars in the export-tree
generator.

The census corrects one figure the plan carries. The applicability rule table
holds 27 constructions across 27 modelos, not 28: a grep for the constructor also
matches the class definition line. The migration is unchanged; the number quoted
in a deletion inventory is not.

The census also found one realised defect rather than a latent one: the Madrid
autonomic deduccion filing year is declared independently in two modules, so the
two can disagree with nothing detecting it.

Deletion-inventory entries consumed: none. This row detects and enrols; it
deletes nothing.

Gate bite proof: a six-line module planted in the domain package produced four
unadjudicated findings across four detectors and exit code 1; removing it
restored exit code 0. Nothing tracked was modified for the proof.

## Notes

The row as written in the plan is wider than the version quoted in the dispatch
message: the live row also scopes `dev/` and names the export-tree design-prose
grammar, `dev/registry/mappings/` and `dev/registry/render_profiles/` as in-scope
instances. The live row was executed.

The ledger's first shape adjudicated by directory prefix, and the planted-finding
proof failed against it: a broad rule covering a directory and a kind swallowed
new drift of an adjudicated kind in an adjudicated area. The test was right and
the design was wrong. Decisions are now file-scoped, with the two dev data
directories the only exception, so a new file carrying regulatory data is
unadjudicated the moment it is written. The proof passes on the corrected shape
and the limitation that remains is stated: a new literal inside an
already-adjudicated file does not red the gate.

Two scope decisions are recorded rather than taken silently. The test surface
carries 14,712 findings, overwhelmingly expected values a test takes from an
external authority as the quality-gates rule requires; it is measured, reachable
on demand, and deliberately not adjudicated. And 336 of the 614 findings are
deferred rather than enrolled, because no plan row covers them; the audit
recommends four new rows and each deferral names that record.
