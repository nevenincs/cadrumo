---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:969280f4e4323df5f7d135334251cecc01a3243b4762ad32e1b47ac8965642c4'
step_id: 'S94'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Sweep for the shape the workspace port turned out to be, an unreached Protocol whose members shipped classes do satisfy, and act on what it finds: the generated-artifact contract was recorded as having no implementer at all because it requires a sources member no class provides, and two classes in its own module provide all eight. Seven of the eight are bare annotations, so any derivation reading only the class dictionary sees one member and concludes wrongly, which a first draft of the gate reproduced. Give the contract a conformance gate and harden the previous step's the same way.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_static_generated_source_applicability.py`
- `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_static_generated_source_applicability.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../test_static_generated_source_applicability.py` 6 passed;
  `.../test_workspace_producers.py -k realization` passed
- `verify:` teeth proved against the LIVE tree -- renaming a contract member
  fails and names both inspection shapes; restored and re-verified
- `verify:` the three ledger gates 19 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` open symbol decisions 45 -> 44; `ruff check` and `ty check` clean

## Notes

The sweep looked for the shape the workspace port turned out to be: an unreached
Protocol with two or more members that shipped classes satisfy. Five hits, one
of them the port gated last step, which is the control that says the scan
reaches what it should.

`GeneratedArtifactInspection` was recorded as having NO implementer at all --
the entry said it requires a `sources` member no class in the shipped tree
provides. Two classes in its own module provide it and every other member.

The likely origin of that error is worth keeping, because a first draft of this
step's gate reproduced it exactly. Seven of the contract's eight members are
bare annotations and only `sources` carries a body, so a derivation reading the
class dictionary alone sees ONE member. `vars(protocol)` is the obvious
derivation and it is wrong for any Protocol that declares fields; the correct
one unions `__annotations__` with `vars`. The previous step's gate is hardened
the same way -- it happened to be right, because that port declares all three
members with a body, but it was right by luck.

Three unreached Protocols remain from the sweep and are left alone: they are
single-implementer contracts whose one conformer is named in their own module,
which is a weaker case for a gate than a contract several shapes are written to.
