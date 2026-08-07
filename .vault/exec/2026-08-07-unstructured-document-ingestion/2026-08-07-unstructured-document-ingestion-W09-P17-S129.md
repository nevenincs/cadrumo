---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5fa2ace1bb71e7328e8a12a2de48fe3c41a9a2a263d08776487431b017520156'
step_id: 'S129'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add a CLI-level gate driving `evidence add` then `evidence confirm` twice
  through the real command tree, reading the operator-facing JSON envelope.
- Cover all three contract outcomes at the CLI: identical retry, divergent
  re-confirm, and the same bytes added twice as two evidence records.
- Carry the cases on the deterministic structured document rather than a
  text-bearing PDF, so the gate runs with no on-host reading model.
- Mutation-prove reachability by blinding the document-identity lookup from
  outside the repository and confirming the CLI cases red.

## Outcome

The guard this record covers was gated at the application layer only. That
proves the logic and says nothing about whether any operator command reaches it,
and this campaign has already shipped surfaces that were built, gated and
unreached — a refusal nobody's command runs is indistinguishable from no
refusal, and the failure mode is silent in both directions.

The gate drives the real Typer tree end to end and asserts on the envelope the
operator actually receives, not on a return value. All three outcomes hold
there. An identical retry exits zero, reports the record as not newly created,
and leaves one row in the catalogue. A re-confirm restating the invoice number
exits non-zero, names the divergent field in the envelope, and leaves the count
at one. The same bytes added twice produce two distinct evidence records that
still resolve to one document, and the second confirm refuses — which is the
case an evidence-id-keyed guard would let straight through, and re-running an
ingest is the single most likely way an operator arrives here.

### The fixture choice is load-bearing, not incidental

The cases run on a Facturae 3.2.2 document rather than the text-bearing PDF the
sibling confirm suite generates. The structured lane is the deterministic parser,
so these need no on-host reading model and execute on any machine.

That is not a convenience. The sibling suite cannot run in this environment at
all: every one of its cases fails on a local inference connection failure at the
*extraction* stage, long before reaching the confirm logic. A CLI-surface
regression on that path would therefore be invisible — the suite reports the same
red whether the surface works or not. Choosing the lane that runs without a model
is what makes this gate a standing signal rather than a conditional one. Making
the sibling suite runnable on the same basis is carried as its own row.

### The gate reached HEAD under another author's commit

While the repository index lock was held by a dead holder, a sweeping
whole-index commit took this file into the tree before it could be committed
here. The landed content is byte-identical to the final version, verified by an
empty status afterwards, so nothing was lost or truncated. It is recorded because
the file's authorship in the log does not match its authorship in fact, and a
later reader reconstructing why this gate exists would otherwise look in the
wrong commit.

## Verification

The gate, three cases through the real command tree:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_duplicate_cli.py -n0 -m "integration" -p no:randomly
    3 passed in 18.70s

Re-run after formatting, confirming the selection was not disturbed:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_duplicate_cli.py -n0 -m "integration" -p no:randomly
    3 passed in 23.79s

Lint, format and type checks clean under `ruff check`, `ruff format` and
`ty check`.

### Mutation proof

The document-identity lookup was blinded to report that nothing was ever minted,
installed from a plugin module **outside** the repository at plugin scope, with
an assertion that the replacement is not the original so a patch that never
landed cannot pass as a proof, and printing on install. No tracked file was
edited.

    MUTATION INSTALLED: document-identity lookup blinded
    2 failed, 1 passed in 10.51s

The two reddened cases are the two refusal outcomes, which is what establishes
the refusal is reached through the command tree rather than merely present in the
module. The single green is the identical-retry case, which is legitimately
unaffected: with the lookup blinded there is no duplicate to detect, and the
no-op remains the correct answer.

## Notes

**A staging signal that reads as a failure and is not.** Re-staging this file
after the lock cleared returned exit zero with nothing staged, which invites a
blind retry loop. It meant the file was already tracked and unmodified, having
been swept into the tree in the interval. The question is answered by asking the
log for the path's history, not by reading the staging exit status or an empty
diff — the same class of misleading signal as a working-tree diff that reads
empty because the content has become HEAD.

**A shell pipeline reported a false success during the same window.** A retry
loop tested the exit status of a pipeline ending in `tail`, which reports the
last command's status rather than the commit's, so a failed commit read as
successful. Caught before anything depended on it.
