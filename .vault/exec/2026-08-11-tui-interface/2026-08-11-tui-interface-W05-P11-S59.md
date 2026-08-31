---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7c692dd55bc6b2d8db4f8e195f22244d7f96ea3ac4651d316ee5412fc075422e'
step_id: 'S59'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W05-P10a-S49]]"
---

# Prove the C2 read destinations, refusal states and schema/row/provenance matrix green on current source, then record the C2 exit governance fact as an execution record wiki-linking the C2 cohort-open record. Run the workspace suites with -m integration explicitly: they carry no unit marker and a -m unit run reports NOTHING RAN over all 76 collected tests; `src/cadrumo/application/modelo/tests/test_workspace_projection.py and .vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W05-P11-S59.md`. CHAIN DEPENDENCY, MEASURED 2026-08-31: this row is one link in an UNBUILT chain of eight governance records, each specified to wiki-link the previous -- S01 C1-open, S38 C1-exit, S49 C2-open, S59 (this row), S71 C3-prerequisite, S79 C3-exit, S90 C4-exit, S93 C5-aggregate. Every one is unchecked. THIS ROW'S OWN LINK TARGET IS S49's RECORD, WHICH DOES NOT EXIST, so the record cannot honestly be written until S49 is closed. Stated here because the dependency is invisible from the row text: read on its own, this looks like an ordinary prove-and-record step, and a reader would discover the missing target only after doing the proving.

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_projection.py and .vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W05-P11-S59.md`

## Changes

- `A` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W05-P11-S59.md`
- `verify:` `pytest test_workspace_projection.py view/ test_c2_workspace_accessibility.py -m integration` -> `120 passed, 1 failed`, then `121 passed` after the failure resolved

## Notes

THE C2 EXIT FACT. The C2 read destinations, refusal states and
schema/row/provenance matrix are proven by `test_workspace_projection.py`,
the `entrypoints/tui/modelo/view/` suites and
`test_c2_workspace_accessibility.py`, green on 2026-08-31 at 121 tests. HEAD was
`bb51442a841d3f04a822a092ba92b2109679bbcc`; THE RUN WAS AGAINST THE WORKING TREE
AT THAT HEAD RATHER THAN A CLEAN CHECKOUT, as with every record in this chain --
this worktree is shared and several lanes committed throughout the session.

THE MARKER WARNING IN THE ROW IS CORRECT AND WAS NEEDED. These suites carry the
integration marker only, so `-m unit` reports NOTHING RAN across all of them and
exits clean. The run above used `-m integration` explicitly.

THE ONE FAILURE WAS NOT A C2 DEFECT, and the distinction is the point.
`test_no_domain_or_adapter_module_imports_any_modelo_workspace_symbol` failed on
an `IndentationError` raised while PARSING
`adapters/inbound/financial/providers/tests/test_base.py` -- a peer's file, left
syntactically incomplete mid-edit. The gate walks the tree by AST, so any file
being written at that moment takes it down. Confirmed transient rather than
landed: the file was uncommitted, HEAD's version parsed cleanly, and once the
peer's edit landed the whole tree parsed with zero unparseable files and the
gate passed. Re-run rather than triaged, and the 16-minute cost of learning that
is why the retry was scoped to the single test rather than the suite.

A NOTE ON WHAT THAT COST, because it recurs: this session recorded SIX distinct
peer-churn casualties -- `core/_notificacion_estado_servicio`,
`core/_observed_header_fact`, `core.windows_contention`, `core.refund_election`,
this `test_base.py`, and `get_secret_store` from the storage adapter namespace.
A tree-wide scan run while a relocation campaign is live has a good chance of
catching some file mid-write, and the signature is a DIFFERENT casualty on each
run. One run alone reads as a broken gate.

STANDING GOAL NOT COVERED, restated from the row so closure does not bury it:
the retired C2 exit receipt bound its predecessor digests and cohort evidence as
machine-compared fields. This record states the conformance modules, the test
count and the commit in prose. Nothing recomputes them, and nothing fails if
they drift.
