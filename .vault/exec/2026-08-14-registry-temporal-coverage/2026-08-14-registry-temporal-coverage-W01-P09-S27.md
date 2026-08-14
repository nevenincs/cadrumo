---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:db8f2131b2b456e9ddc550c87be7314484755db0c7c52d176136c851a974b63e'
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

625 findings across 243 files and directories, all adjudicated: 254 enrolled to a
plan row, 337 deferred against the census audit, 34 allowlisted as not regulatory
data. Zero unadjudicated, zero stale, zero ambiguous. Enrolments land on five
rows: 104 on the supported-filing-years row, 8 on the embed classifier, 2 on the
dev artefact collapse, and one each on the applicability migrator and the embed
migration.

The known-instance control did its job by failing. The first build recovered the
applicability table, the supported ejercicio set, the seasonal coefficients, the
Lorca 2022 reduction and the export-tree grammars, but MISSED the
difficult-justification percentage, which is written Decimal("1"): the value-shape
detector skipped it as a scale literal and the name-driven detector skipped it
because the assigned value is a call rather than a bare number. The name-driven
detector could therefore see no constant written NAME = Decimal(...) at all, which
is how this repository writes every regulatory quantity. Teaching the value test
to look through a Decimal call raised the census from 614 findings to 625 and
surfaced eleven constants nothing had reported. All four values the row names in
that module are now recovered.

The census corrects one figure the plan carries. The applicability rule table
holds 27 constructions across 27 modelos, not 28: a grep for the constructor also
matches the class definition line. The migration is unchanged; the number quoted
in a deletion inventory is not.

The census also found one realised defect rather than a latent one: the Madrid
autonomic deduccion filing year is declared independently in two modules, so the
two can disagree with nothing detecting it.

One residual detector limitation is stated rather than fixed: the name-driven
detector is vocabulary-driven, so a regulatory constant named in English outside
the AEAT vocabulary stays invisible. EXPECTED_MODULE_DISTRIBUTION_VECTOR in the
orden constants module is the worked example, covered here only because the whole
file carries a file-level decision.

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
carries 14,995 findings, overwhelmingly expected values a test takes from an
external authority as the quality-gates rule requires; it is measured, reachable
on demand, and deliberately not adjudicated. And 337 of the 625 findings are
deferred rather than enrolled, because no plan row covers them; the audit
recommends four new rows and each deferral names that record.
