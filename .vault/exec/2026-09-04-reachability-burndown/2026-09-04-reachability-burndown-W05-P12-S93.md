---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e157b39f7cb8341602fe8b70819f679a2b530cff2147c2c5f6237d014ecf229e'
step_id: 'S93'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Sweep every open finding against its module siblings' in-package consumer counts, which is what exposed the execution-policy cluster, and find none at the threshold that discriminated there; then close the last member of the public-types cluster, which is not the displaced shape the other six were. The workspace atomic projection port is the contract its module says eight envelope realizations exist to satisfy, and structural typing let that claim go unchecked, so give it a conformance gate deriving the required members from the Protocol rather than restating them.

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../test_workspace_producers.py` 24 passed
- `verify:` teeth proved against the LIVE tree -- renaming a port member fails
  the gate and names all eight realizations; restored and re-verified
- `verify:` the three ledger gates 19 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` open symbol decisions 46 -> 45; `ruff check` and `ty check` clean

## Notes

The sibling sweep is a negative result and worth recording as one. It compares
each open finding against the in-package consumer counts of its own module's
other public names, which is exactly what exposed the execution-policy cluster
last step -- siblings at two to twenty-six, findings at zero. At that threshold
nothing remains: the execution-policy cluster was the only one of its shape, and
the residue is not unused declarations sitting beside well-used siblings. The
scan located forty-one of the forty-six open symbols, so the silence is not
vacuity.

The public-types cluster went seven to one across this campaign and every
reversal was the same shape, a different construct covering the ground. The last
member is not. `ModeloWorkspaceAtomicProjectionPortV1` is the port its own
module says the eight envelopes exist to satisfy; the comment above them states
each is a thin adapter that exists BECAUSE the port binds its projection to a
pydantic model.

Structural typing is why nothing reached it and also why nobody noticed the
claim was unchecked: the realizations conform without naming it, so one could
rename a member and the comment would keep reading true.

The gate derives the required members from the Protocol rather than restating
them. A copied member list is a second declaration of the same contract and
drifts the moment the port gains a member -- the same reasoning that kept the
calculate shim forwarding `**kwargs` instead of repeating twenty-one parameters.

`__protocol_attrs__` was the obvious derivation and `ty` rejects it as an
unresolved attribute, being a CPython implementation detail. Narrowed to
`vars(port)` filtered to public names, which the checker models and which reads
better anyway.
