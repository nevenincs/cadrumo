---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7849d8ddbb0e0eac539ead3ba03565ba86d5475e2463c138754d4d9f197aefeb'
step_id: 'S49'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W05-P10-S38]]"
---

# Prove the Workspace V1 structural invariants and the C2 conformance suite green on current source, then record the C2 cohort-open governance fact as an execution record wiki-linking the C1 record. The suite already ships and passes; no new assertion is authored here. Do NOT assert zero remaining modelo.work.review routes: no TUI route registry or destination table exists in the tree, so that assertion would be vacuous by construction and would encode a moment rather than a property. STANDING GOAL NOT COVERED: the retired C2 dependency receipt bound the workspace schema fingerprint, field-manifest digest, producer inventory and epoch tuple as machine-compared values, and re-minted when they drifted; nothing recomputes those now, so a fingerprint drift will surface as a conformance failure rather than as a receipt mismatch

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_structural_invariants.py`
- `test_workspace.py`
- `test_workspace_models.py`
- `test_workspace_producers.py`
- `test_workspace_manifest.py`
- `and test_workspace_projection.py`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `A` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W05-P10a-S49.md`
- `verify:` `pytest test_workspace.py test_workspace_models.py test_workspace_producers.py test_workspace_manifest.py` -> `128 passed` then `45 passed` after the two gate repairs
- `verify:` `pytest test_workspace_projection.py -m integration` -> `121 passed`

## Notes

THE C2 COHORT-OPEN FACT. The Workspace V1 structural invariants and the C2
conformance suite are proven by `test_workspace.py`, `test_workspace_models.py`,
`test_workspace_producers.py`, `test_workspace_manifest.py` and
`test_workspace_projection.py`, all green on 2026-08-31. HEAD was
`82f05205a77916bb83210efffab9acb8e66aebce`; AS WITH THE C1 RECORDS, THE RUN WAS
AGAINST THE WORKING TREE AT THAT HEAD, NOT A CLEAN CHECKOUT -- this worktree is
shared and several lanes were committing throughout.

TWO OF THIS ROW'S NAMED CLAIMS ARE STALE, both recorded rather than quietly
worked around.

FIRST, the row names `test_workspace_structural_invariants.py`, and the Scope
list above carries it because Scope is machine-filled from the row. THAT FILE
DOES NOT EXIST, under that name or any other. pytest errors on the missing path
and runs nothing at all, exiting without a single failure -- the shape where a
run looks fine precisely because it did nothing. The structural invariants are
covered by the five suites that do exist. This is the second row in this plan to
name a nonexistent test module (W06.P12a.S71 names two), so it is a pattern in
the governance spine rather than a typo.

SECOND, the row instructs: "Do NOT assert zero remaining modelo.work.review
routes: no TUI route registry or destination table exists in the tree, so that
assertion would be vacuous by construction". A route table NOW EXISTS --
`entrypoints/tui/modelo/routes.py` ships `MODELO_WORKSPACE_DESTINATIONS`. The
instruction was correct when written and its premise has since been falsified.
The assertion is still NOT added here, because it belongs to whichever row owns
that table, not to a cohort-open record.

TWO GATE DEFECTS FOUND AND REPAIRED, both wrong about their own SUBJECT and
failing in opposite directions.

(A) `test_the_retired_private_manifest_module_is_gone` asserted that importing
`cadrumo.application.modelo.workspace_manifest` raises `ModuleNotFoundError`.
That is the PUBLIC DESTINATION of the hard move, imported by
`workspace_producers.py` in twelve places, while the gate's own docstring says
"No private path... survives". Both the module and the gate demanding its
absence are in HEAD, swept in by a broad `chore: land the in-flight domain,
application and adapter st...` commit -- so it was landed red and UNSATISFIABLE
WITHOUT DELETING LIVE PRODUCTION CODE. Re-pointed at `_workspace_manifest`, plus
a positive assertion that the public module imports, so it proves the move
happened instead of demanding its result not exist. Proven to bite by injecting
the private module into `sys.modules` IN MEMORY -- deliberately not by creating
the file, because a peer's broad landing commit could capture a mutation left on
disk in this tree.

(B) `test_workspace_producer_docs_and_active_tree_reach_the_public_module_fixed_point`
scanned every `src/**/*.py` and `docs/**/*.rst` for the BARE SUBSTRING
`_workspace_producers`. That string also occurs inside `test_workspace_producers`
-- the legitimately named suite for the public module -- so the gate reported a
sibling test's DOCSTRING as a surviving reference to a deleted module. Now
anchored on a word boundary and verified in both directions: `from
._workspace_producers import`, `_workspace_producers.py` and the quoted name
still match; `test_workspace_producers.py` and prose naming that suite do not.

STANDING GOAL NOT COVERED, restated from the row: the retired C2 dependency
receipt bound the workspace schema fingerprint, field-manifest digest, producer
inventory and epoch tuple as MACHINE-COMPARED values and re-minted when they
drifted. Nothing recomputes those now, so a fingerprint drift surfaces as a
conformance failure rather than as a receipt mismatch.
