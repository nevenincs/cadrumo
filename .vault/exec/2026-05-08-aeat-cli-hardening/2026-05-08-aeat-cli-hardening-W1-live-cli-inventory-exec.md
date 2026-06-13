---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-inventory-audit]]'
---



# `aeat-cli-hardening` `W1 Live CLI Inventory`

W1 captured the current executable root and reconciled it against CLI modules on
disk before implementation.

- Modified: `2026-05-08-aeat-cli-hardening-plan.md`
- Created: `2026-05-08-aeat-cli-hardening-inventory.md`
- Created: `2026-05-08-aeat-cli-hardening-W1-live-cli-inventory.md`

## Description

The root currently exposes `setup` and `app` only. The executable tree matches
the pasted audit for the main setup/app surfaces and adds one extra registered
technical command: `app registry audit-oracles`.

The file inventory found multiple Typer app modules outside the registered root
tree. They are not changed in W1; they are tracked for boundary classification
under `DISCOVERED-001`.

Four implementation findings were appended to the plan before code work:
`DISCOVERED-004` through `DISCOVERED-007`.

## Tests

W1 verification used real CLI help invocation plus Typer command-tree
introspection:

- root, setup, setup auth, setup profile, app, overview, ledger, invoice,
  declaration, and registry help commands rendered successfully;
- root has no `--version`, `doctor`, `init`, `config`, `topic`, or conceptual
  help surface;
- root app registration does not apply the shared structured error boundary;
- CLI modules on disk exceed the registered root tree and require boundary
  classification.

No application behavior was changed in W1.
