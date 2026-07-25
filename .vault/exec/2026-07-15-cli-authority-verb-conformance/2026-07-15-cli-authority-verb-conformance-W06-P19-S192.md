---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S192'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run generated CLI reference and static-tree conformance

## Scope

- `dev/docs/tests/`

## Description

Run generated CLI reference and static-tree conformance.

## Outcome

FAILED, peer working-tree churn carrying a latent committed hazard.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
dev/docs/tests/test_cli_reference_conformance.py dev/docs/tests/test_cli_tree.py
dev/docs/tests/test_cli_anchor_parity.py`.
Collected 23, 22 passed, 1 failed, exit line `1 failed, 22 passed in 171.36s`, exit code 1, at
HEAD `1844ef2ea0`.

The failing case asserts every live CLI leaf has a registered output schema. Two leaves, the
profile create and edit verbs, are unregistered as far as the production discovery walk can see.

Root cause established by exact search: both schemas ARE declared, in a NEW UNTRACKED module
under the application wizard package named for results. The production discovery walk imports
only modules whose name contains the payload token, inside the declared payload packages. An
application-layer module named for results is outside both filters, so the registration
decorators never run and the registry never learns the two keys.

## Notes

The gate is non-tautological and it is right: it compares the live tree against the
registry, two independent sources, and consults no generated page.

The hazard is real rather than cosmetic. If that relocation is committed as it stands, the two
leaves lose their schema in the contract manifest and in the MCP tool surface, not only in this
gate. The owning campaign should either keep the declarations inside a discovered payload module
or extend the discovery walk in the same commit.

The JSON schema conformance suite recorded under S188 is green over the same state, because it
does not compare the live leaf set against the registry.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
