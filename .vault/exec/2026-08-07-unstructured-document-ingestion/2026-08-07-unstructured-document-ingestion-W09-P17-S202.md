---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6c0ddc5c0b2bd1e529aa74c86c5f72bc986089b4c3e7baf8800541d6dcfbc600'
step_id: 'S202'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Outcome

The identification rename sweep is complete at HEAD. All 41 preflight unit tests
pass. Closed against measurement rather than against the row's own premise —
which had gone stale between the row being written and being read.

## What the row asserted, and what was actually true

The row was opened claiming two things remained: the intracom preflight fixtures
expressed a counterparty **country** where the check now reads an
**identification state**, and the four locale catalogues still carried the old
`domestic_counterparty_on_intra_community_transaction` key with no new key
present. Both were measured facts when written.

Both were false within the hour. Sweeper commit `24267e3167` landed the fixture
and locale work. At HEAD the catalogues carry
`domestic_identification_on_intra_community_transaction`, the old key appears
nowhere in `src/` or `dev/`, and the fixtures assert the identification-keyed
reason.

## The sequence

The rename keys intra-community reasons on VAT **identification** rather than
establishment, per LIVA art. 25 — an intra-community supply is exempt on the
acquirer's identification in another Member State, not on where it is
established. The two are independent, and the old naming sent the operator to
check the wrong field in **both** directions: a Spanish-established acquirer
holding a German VAT number, and a German-established acquirer purchasing under
a Spanish NIF-IVA.

The export case was deliberately left keyed on establishment. An export leaves
the Union, so the question is where the counterparty **is**, not who VAT-identifies
it. The narrowing is one concept, not a global substitution.

The owning lane's production change sat **uncommitted** when its session ended.
It was landed as `2ccb5fd000` to preserve it, together with a two-reference
mechanical sweep of the test file. The remaining fixture and locale work was
left rowed rather than guessed, because the fixture change is a domain judgement
about what the test should assert, not a substitution.

## Two measurement failures worth recording

**Attribution from enum contents rather than from a traceback.** Two lanes
triaged the same red to two different causes. The enum showed both defects; the
failure output showed one.

**A filter that excluded its own target.** A sweep for remaining references ran
`grep -v "_preflight.py"` to skip the production file — which also swallowed
`test_preflight.py`, the only file still holding stale references. The result
read as a clean sweep with two references standing.

## Verification

    pytest src/cadrumo/application/ledger/tests -n0 -m unit -k preflight
    41 passed, 1076 deselected

The `unit` lane only. Working-tree reading: an untracked totality gate from a
concurrent lane is present and passing. The HEAD-specific claims above were each
checked with `git show HEAD:<path>`.
