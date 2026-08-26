---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:8bef8191393895015cfb8f53559d58a05e72eff7a8a1a60602b9add83a17f37b'
step_id: 'S44'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Repair `app modelo readiness --revision-id`, which called the PEP 695 RevisionId alias as a constructor and crashed on every use

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_readiness_blocks_modelo_work.py`
- `verify:` `pytest test_profile_readiness_blocks_modelo_work.py -m integration` -> `pass`

## Notes

`RevisionId` is declared `type RevisionId = Annotated[str, ...]`, a PEP 695
alias, and the handler called it as `RevisionId(revision_id)`. A
`typing.TypeAliasType` is not callable, so every invocation carrying
`--revision-id` raised `TypeError` and surfaced as exit 6, an internal error.
This was the only site in the tree constructing the alias; the flag had never
worked. The alias is `str` at runtime and the callee accepts `RevisionId |
None`, so the string passes through unchanged.

The defect survived because the test that exercised it asserted `exit_code ==
0` on profiles the same test declares unready, so it could never pass and its
failure read as expected noise. Those assertions now match the handler's
documented contract: readiness exits 2 while any axis is unready.

Retiring `config profile preflight` is what made this load-bearing: readiness
is now the one home for the question, and `--revision-id` is its replay
override.
