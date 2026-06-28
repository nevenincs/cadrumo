---
tags:
  - '#adr'
  - '#envelope-conformance-gate'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
  - "[[2026-06-01-envelope-conformance-gate-research]]"
---

# `envelope-conformance-gate` adr: cli json schema registry has zero allowlist | (**status:** `accepted`)

## Problem Statement

CLI leaves that emit JSON are required to be covered by an `OutputSchema`
registered in `SCHEMA_REGISTRY`. Without a conformance gate the registry
drifts: new leaves ship without a schema, retired leaves keep stale
entries, and operators see envelope shapes the contract no longer
documents. Allowlist-style gates accumulate exceptions and silently
legalise the drift they were meant to catch.

## Considerations

Two enforcement shapes were considered. An allowlist gate lists the
known-missing leaves and accepts new ones into the list as they appear;
this is what the coverage-canonicalisation audit retired as a structural
smell. A symmetric-diff gate computes the live CLI leaf set and the
registry key set, asserts equality, and reports both directions of drift
(missing registration + stale registration) with no escape hatch.

## Constraints

The gate must walk the live Typer `app` graph, not a curated module
list, so registry coverage tracks every actual `_lazy()`-mounted
subcommand. It must run as part of the standard unit lane (no special
marker) so every developer commit hits it. It must not depend on a
hand-maintained "expected leaves" file.

## Implementation

`src/aeat/entrypoints/cli/test_json_schema_conformance.py` builds the
live CLI by calling the application factory, walks the Typer command
tree to collect every leaf command path, and compares the resulting
`set[tuple[str, ...]]` against `set(SCHEMA_REGISTRY.keys())`. Failures
report the two directions separately ("registered but no live leaf"
versus "live leaf but no registered schema") so the operator-facing
diagnostic is actionable. There is no allowlist parameter and no
exclusion list; every divergence is a test failure.

## Rationale

Allowlist gates encode "we know this is broken" as durable state;
symmetric-diff gates encode "this must always be true" as a structural
contract. The coverage-canonicalisation work demonstrated the failure
mode of the former by retiring a 66-entry allowlist that had absorbed
every drift introduced over a year of growth. Applying the same shape
to envelope conformance closes the same class of drift before it can
accumulate.

## Consequences

Adding a new JSON-emitting CLI leaf requires registering its schema in
the same commit; the gate rejects the commit otherwise. Retiring a leaf
requires removing its schema registration; the gate rejects the commit
otherwise. The single-step ergonomic cost is the load-bearing property
that keeps the registry honest. No follow-up audit pass is needed to
reconcile drift, because drift is not allowed to land.
