---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:3298f782b415b79bf71994385088e49506889dd8c9572b035374c03055b21133'
step_id: 'S168'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Align the command and configuration overview with the accepted hierarchy and security semantics

## Scope

- `docs/reference/commands-and-configuration.md`

## Description

- Check the command-and-configuration overview against the accepted hierarchy
  and the product/authority ownership split.
- Confirm every structured-map target it routes to exists.

## Outcome

SATISFIED by verification; no rewrite was needed, and the reason it needs none
is worth stating.

The page is deliberately a LOOKUP MAP, not a command enumeration. It names live
help as the command authority and routes each family to a generated reference.
So the absence of `config login`, the recovery family, certificate secrets and
the reset lifecycle from its text is by design, not staleness - the same
distinction that governed the curated-help row in the previous phase.

Against what the row does require: the accepted hierarchy is correct, with the
two roots `config` and `app` and no third family, matching the architecture
constraint. The security semantics are correct, splitting product-owned
`CADRUMO_*` state from authority-owned `AEAT_*` integration controls and
stating the former are not aliases for the latter. No removed spelling appears:
`config switch`, `config lock`, `rekey`, `sandbox use` and audit `replay` are
all absent.

Every routing target resolves - the CLI overview, config, app, schema and
automation references, the explanation index, the how-to index and the
generated API root all exist on disk.

Gates at HEAD `ec62e04591f495a4553abd9da23b0a28766938c8`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.89s`. The
  conformance suite resolves every command these pages cite against the live
  Click tree, so a spelling error here is a hard failure rather than a silent
  dead instruction.

## Notes

An initial count of accepted-grammar mentions on this page read as a large gap:
login, recovery, certificate secret and reset start all at zero. That count was
measuring the wrong property. A delegating map scores zero on command
enumeration by construction, and treating that score as staleness would have
produced a rewrite duplicating the generated reference, which would then drift
from it.
