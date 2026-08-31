---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fa693b5c91e197cc1ffdefb213c966d8ed3f98dcc30245892fdaf5924c046cbb'
step_id: 'S54'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct the always-on CLI contract rule, whose worked example cited two pull compounds on a family that does not carry them, and audit every verb the rule names against the live graph

## Scope

- `.vaultspec/rules/aeat-cli-contract.md`

## Changes

- `M` `.vaultspec/rules/aeat-cli-contract.md`
- `M` `.claude/rules/aeat-cli-contract.md`
- `M` `.agents/rules/aeat-cli-contract.md`
- `M` `.codex/rules/aeat-cli-contract.md`
- `M` `.gemini/rules/aeat-cli-contract.md`
- `verify:` `vaultspec-core sync` -> `4 updated, 195 unchanged`
- `verify:` `python -c "...every verb in the How section against COMMAND_GRAPH..."` -> `12 of 12 resolve`

## Notes

Found while checking the `pull` compounds against the contract's own grammar.
The compounds themselves are all legal -- `<token>-all` is cardinality,
`<token>-<subject>` is sanctioned, and the verb-grammar gate already refuses a
locus suffix. What was wrong was the rule's worked example: it offered `aeat app
live justificante pull`, `pull-all`, `pull-sources` as the model to copy, and
`app live justificante` carries only `list`, `pull` and `view`. The family that
actually carries all three is `app live filed`.

This is the `firmware-reference-parity` failure inside a rule rather than a
skill: a name in always-on prose that resolves to nothing. It is worse here than
in a docstring, because the rule is loaded into every agent context in this
repository, so the dead citation was being handed to every session as the
example to imitate.

Corrected on the `.vaultspec/rules/` source and propagated with
`vaultspec-core sync`; the generated provider copies were never hand-edited.

The rest of the rule's How section was then audited rather than assumed: all
twelve verbs it names -- the filed pull trio, `ledger import`, both reconcile
transports, both censo transports, `evidence add`, `certificate register`,
`spreadsheet calculate` and `work file` -- resolve against the live graph.
