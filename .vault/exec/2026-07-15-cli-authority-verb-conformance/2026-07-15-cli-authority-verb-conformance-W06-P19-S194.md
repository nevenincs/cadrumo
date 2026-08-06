---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4d17328325d0689f341d7feb8f49de6fd58599fed210de75b9fdf8f4f7f52884'
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

Re-run before reporting, at HEAD `593559067c`: `Analyzed 3664 files, 17626 dependencies`,
`Contracts: 3 kept, 2 broken`, the same two contracts. The verdict is a standing tree property, not
a single-HEAD reading.

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

## Re-measurement at HEAD bc80aa2808

SATISFIED. Both broken contracts from the previous reading were fixed by their owning
campaigns between `c293706ce3` and this HEAD. Command: `uv run --no-sync lint-imports`.
Result line `Contracts: 5 kept, 0 broken`, exit code 0, at HEAD `bc80aa2808`.
Analyzed 3668 files, 17633 dependencies. All five layering contracts now keep:
registry-must-not-import-renta, domain-must-not-import-adapters, domain-must-not-import-application,
core-must-not-import-outer-layers, and AEAT layered architecture. The TUI adapters-to-entrypoints
edges recorded in the previous reading were resolved by the TUI campaign before this re-run.
