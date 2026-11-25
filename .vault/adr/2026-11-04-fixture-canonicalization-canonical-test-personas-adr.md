---
tags:
  - '#adr'
  - '#fixture-canonicalization'
date: '2026-11-04'
modified: '2026-11-04'
body_schema: 'body-v2'
body_hash: 'sha256:1beed393db9851c784143f6756068722619a150777cc585dfc1b1c85d385ac9c'
related:
  - "[[2026-11-04-fixture-canonicalization-research]]"
  - "[[2026-06-01-verification-fixture-roles-adr]]"
  - "[[2026-06-03-multi-bucket-test-fixture-adr]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-11-03-backend-served-surface-adr]]"
---

# `fixture-canonicalization` adr: `Canonical test personas` | (**status:** `accepted`)

Operator approval recorded 2026-11-04 in the fixture-canonicalization design session, covering this ADR, the projection ADR and the plan.

## Problem Statement

Every fixture population invents its own taxpayer, so the backend asserts on one person, the window renders another and the docs show a third, and one placeholder identity plays five roles. Scenario meaning must be defined once so that tests, window and docs exercise the same flows and obligation simulations can be built on them (`2026-11-04-fixture-canonicalization-research`).

## Considerations

- Divergence is semantic, not byte duplication; copying JSON would not fix it.
- Shipped code may not import `dev`, and `cadrumo.tests` is core-only, so a Python persona module cannot serve every consumer; data files can.
- Fixtures must be synthetic and seeded through real operations; a direct storage write tests nothing the operator does.
- Years come only from the supported-years declaration.
- Existing specimen provenance (`2026-06-01-verification-fixture-roles-adr`) and executed docs seeding (`2026-07-13-docs-cli-sequences-adr`) stay binding.

## Considered options

- One shared JSON store read by every consumer: rejected; loses value types, couples every suite to one serialisation and conflicts with executed docs seeding.
- Typed Python persona module in a test package: rejected; docs tooling, frontend scripts and Rust cannot read it without crossing contracts.
- Data-only persona catalogue under `dev/fixtures/personas/`, replayed through production operations: chosen.
- Status quo with stricter review: rejected; 38 hand-synchronised commits show review does not hold.

## Constraints

- Applies to scenario definitions only: taxpayer facts, household, identities, ledger rows, document references, periods and expected obligations. External specimens stay with their parsers; protocol vectors stay with their owners.
- Persona files hold no Python, no year literals and no real data. Every identity is a checksum-valid synthetic value used for exactly one role.
- Materialisation uses production operations only. Test-only storage writes may not seed a persona.
- Docs seed recipes remain executed CLI steps; they are generated from personas and checked, not hand-maintained.
- One scenario clock: every materialisation and generator runs at an as-of instant derived from the persona and the registry envelope.

## Implementation

We will hold every canonical taxpayer and flow under `dev/fixtures/personas/<persona>/`:

- `persona.toml`: profile facts as question id to value, validated against `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`; household; regime; period tokens (`horizon`, `horizon-1`, `floor` plus month and day) resolved through `supported_filing_years()`.
- `ledger.csv` and `documents.toml`: ledger rows in the CLI import format and references by path to existing specimens.
- `expectations.toml`: hand-grounded expected obligations, deadlines and key casillas per period, each citing its provision; never recorded from a run.
- `dev/fixtures/personas/identities.toml`: the identity catalogue, one synthetic identity per role.

A reader in `cadrumo.tests` parses and validates the files; a materialiser in `src/cadrumo/entrypoints/tests/` replays a persona through the profile patch, ledger import and evidence operations into a profile. Python tests, the docs sandbox, `native/desktop/frontend/scripts/modelo_fixtures.py`, the `dev/desktop_*_fixture.py` producers and the TUI harness consume personas only through these two modules. Module names are implementation hypotheses within these constraints.

## Rationale

Data files are the only form every consumer can read inside the import contracts, and replay through production operations keeps fixtures honest. Defining identity and roles once removes the five-role placeholder. The obligation simulation needs one scenario source that window, docs and tests share.

## Consequences

- Backend tests, window projections and docs describe the same taxpayers; a profile schema change is made once.
- Accepted cost: identity re-pointing rewrites docs goldens and window projections once; persona edits ripple into every consumer, which is the intent.
- The 177 profile builders migrate family by family; shared builders that restate facts are removed with their consumers, without forwarding aliases.
- Reconsider if the production patch operation cannot express a fact a persona needs; the fix is in the operation, not a test bypass.
