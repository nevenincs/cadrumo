---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5bb5e410e04ef0c0a3c7dc2a17bed4791c919056d7b335468b7ea916c9b04d82'
step_id: 'S39'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Ship the verb-grammar gate D6 promised: refuse a leaf that declares a transport locus while wearing a retired token

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/test_transport_verb_grammar.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_transport_verb_grammar.py -p no:randomly -n0` -> `4 passed`

## Notes

**This record was written after the fact, and that is the finding.** The Step was
marked closed with no execution record, which is the one thing
`aeat-agent-orchestration` forbids outright: without a record,
delivered-as-specified, delivered-narrower and recorded-but-not-implemented wear
the same checkbox.

It was caught by auditing every closed Step against the record directory --
sixty-one closed, sixty with a record, this one without. The gap traces to the
plan repair: seven rows (S36-S42) had been lost from the plan while their
records survived on disk, and the rows were reconstructed from those records'
own headings. S39 was the single row with no record to reconstruct from, so its
text came from the close audit's prose instead, and nothing then created the
missing record.

The work itself is real and was verified before this record was written rather
than assumed from the checkbox: `test_transport_verb_grammar.py` is present, and
its four tests pass. The gate refuses a leaf that declares a transport locus
while wearing a retired token, asserts `file` still names exactly one leaf
(`app modelo work file`), refuses a `<token>-<locus>` compound, and carries an
anti-vacuity floor so a collapsed graph cannot green it.

W05.P12 had shipped only the option-spelling half of what D6 promised; this is
the verb half.
