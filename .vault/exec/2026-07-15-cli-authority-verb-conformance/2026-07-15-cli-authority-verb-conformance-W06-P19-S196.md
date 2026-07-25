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
