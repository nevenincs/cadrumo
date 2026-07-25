---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S194'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run a fresh uncached import graph and require all five contracts

## Scope

- `.importlinter`

## Description

Run a fresh uncached import graph and require all five layering contracts.

## Outcome

FAILED. Three of five contracts kept, two broken, none of the broken sites owned by this
feature.

Command: `uv run --no-sync lint-imports --config .importlinter --no-cache`.
Corpus proven non-empty by the tool's own line: `Analyzed 3660 files, 17595 dependencies`.
Result line `Contracts: 3 kept, 2 broken`, exit code 1, at HEAD `c293706ce3`.

Kept: the registry-must-not-import-renta contract, the domain-must-not-import-adapters contract,
and the core-must-not-import-outer-layers contract.

Broken, with every violating site named:

Domain must not import application. Three sites, all in one bucket payload-version contract test,
reaching the inventory, user-profile and workflow application packages.

AEAT layered architecture. Three application-to-adapters sites: user-profile registration
reaching the storage master-key package, and the operator-output sandbox notice reaching the
storage package and its bucket subpackage. Four adapters-to-entrypoints sites: the TUI visual
verification, manager screen, theme and registration screen tests all reaching the CLI config
manager frontend.

## Notes

An earlier run at HEAD `1844ef2ea0` failed differently and earlier: the configuration
carried an ignored-import entry naming a registry test module deleted by a symbol-relocation
commit, so the tool refused before evaluating contracts. A concurrent campaign corrected that
between the two runs, which is why the second run reaches a contract verdict at all. Both runs
are recorded because the first shows the gate can be blocked by stale configuration rather than
by a real edge.

The four adapters-to-entrypoints sites are the concurrent TUI campaign reaching into the CLI
config package from its own tests. That direction is the one this feature's boundary work cares
about, so it is flagged for the owning campaign even though this feature did not create it.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
