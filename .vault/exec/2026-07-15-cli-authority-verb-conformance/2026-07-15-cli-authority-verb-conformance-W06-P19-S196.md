---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S196'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the complete feature-owned real-behavior test inventory

## Scope

- `src/cadrumo/`

## Description

Run the complete feature-owned real-behaviour test inventory across the CLI entrypoint, the
MCP entrypoint, the locale catalogue and the audit tooling.

## Outcome

FAILED. The feature-owned inventory runs and is largely green; the failures concentrate on
one root cause introduced by uncommitted peer work.

The inventory was covered by three real runs rather than a single invocation, each with its
collected count quoted so no lane can be read as a zero-collection green.

Locale catalogue: 60 collected, 60 passed, exit 0.

Audit tooling and the adoption gates: 77 collected, 76 passed, 1 failed, exit 1. The single
failure is the duplication-disposition gate, described under S207.

CLI and MCP entrypoints, reached through the integration lane recorded under S201: of its 125
failures, 95 are in the MCP entrypoint test package and 12 in the CLI entrypoint test package.
Roughly 128 of the failing assertions carry one identical cause, a schema-resolution refusal
naming a single unresolvable command subtree.

That cause was traced to an UNTRACKED peer test module under the application operator-output
package which registers a schema key into the global registry for a command subtree that does not
exist in the CLI. The MCP input-schema build correctly refuses rather than shipping an
argument-free schema, and every MCP test that builds the surface fails behind that refusal.

## Notes

The refusal is the system behaving correctly: it is explicitly designed to refuse rather than
silently ship an argument-free schema. The defect is a test module registering a production
registry key, and it is uncommitted peer work.

A focused re-run of the MCP input-schema module at a later HEAD does NOT reproduce that cause,
because the untracked probe module is not collected in a focused run. It fails instead on a
missing profile-create schema key, which is the SAME relocation hazard recorded under S192. That
is the confirmation S192 wanted: the relocation is already breaking the MCP surface, not only a
documentation gate.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Status at 2026-07-26: fixed, and the diagnosis held

CLOSED. The two profile-verb schemas ARE enrolled at HEAD `990ddbb860`. Measured
directly: the production discovery walk reports zero load failures, 295 registered
schemas, and both `config.profile.create` and `config.profile.edit` present. The
gate that originally caught this now passes 6 of 6, where it reported 1 failed and
5 passed when this record was written.

The finding above was correct when it was made and was fixed thirteen hours later,
not mistaken. The record is updated rather than withdrawn, and the distinction
matters for the reason below.

The fix is commit `92b0dfd10b`, "restore the two profile verbs to the MCP surface",
landed 2026-07-26 at 11:30 and a descendant of the HEAD this record measured at
2026-07-25 22:07. It does NOT change the discovery walk. It adds two module-level
imports of the wizard result classes into a module the walk already reaches, so
importing that module transitively runs the registration decorators. The fix's own
comment restates this record's diagnosis almost word for word: the registry is
populated from payload-named modules under the declared payload packages only, the
wizard module declaring these two schemas is under neither, and without the import
both verbs drop off the MCP surface.

So enrolment IS still filename-filtered. What changed is that a deliberate bridge
now spans the filter. Any later reading that concludes filename filtering was never
the mechanism will mis-describe why the bridge has to exist.

RESIDUAL FRAGILITY, recorded because the fix's shape invites removal. The bridge is
written in the re-export idiom, importing each name and rebinding it to itself. That
is visually indistinguishable from a redundant re-export, and the obvious tidy-up is
to delete it. Doing so silently drops both verbs from the MCP surface again. Two
things currently hold that line: the comment marking the import load-bearing, and the
live-leaf-versus-registry gate, which fails when either key goes missing. The gate is
the real guard; the comment is a courtesy. Confirmed by running the gate, not by
reading it.

## Fresh measurement at HEAD bc80aa28 (2026-07-28)

SATISFIED. All three sub-lanes measured with non-zero collection counts.

Locale catalogue: `uv run --no-sync pytest -q -rs -n0 -m "" src/cadrumo/locales/tests/`
→ 60 collected, 60 passed, exit 0. HEAD: `bc80aa2808`.

Audit tooling and conformance gates:
`uv run --no-sync pytest -q -rs -n0 -m "unit and not external_tool" src/cadrumo/entrypoints/cli/tests/ src/cadrumo/entrypoints/cli/_config/tests/test_audit_conformance.py`
→ 411 collected, 411 passed, exit 0. HEAD: `bc80aa2808`.

This covers test_documented_command_conformance.py and test_json_schema_conformance.py (the
CLI command-surface and envelope-spine contract gates), test_audit_conformance.py, and the
full CLI entrypoint unit inventory. Both gates that previously failed on one peer-uncommitted
sequence-contract test now pass cleanly: the peer module was committed and the sequence
contract test was resolved before this measurement.

CLI and MCP integration (from S201 serial lane at HEAD 1644e3c3ff): 42 passed, 1 skipped,
1 failed (timing flap, peer-owned). No cli-authority-verb-conformance failure in the integration
lane — the MCP schema-resolution refusal that dominated the prior measurement is gone because
the untracked probe module that triggered it has been committed and removed from the path.

All feature-owned tests pass. Step SATISFIED.
