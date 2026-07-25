---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S120'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths

## Scope

- `src/cadrumo/entrypoints/cli/_ledger.py`

## Description

Restrict `app ledger link` to invoice-only linkage, route the write through the
atomic application writer, and remove the evidence-id and evidence-update result
paths so evidence mutation has one door.

## Outcome

`ledger_link` (`src/cadrumo/entrypoints/cli/_ledger.py:904`) takes the subject as a
positional `typer.Argument` (`:906`) resolved through the single shared
`_resolve_id` helper (`:931`) — no `--id` option and no second resolver — and takes
a required `--invoice-id` Option (`:911`). No evidence-id parameter remains on the
verb, so the removed grammar has no hidden spelling.

The write itself is delegated to the atomic application writer
`link_manual_transaction_invoice` (imported `:934`, called `:958`); the CLI performs
no direct catalogue mutation and constructs no evidence-update result.

Two pre-write instructive gates run before the writer, keeping the operator's first
refusal surface informative rather than a bare failure: an invoice id absent from the
active profile's catalogue is refused with a typed localized message (`:941`), and a
cross-bucket invoice is refused at `:948`. Both refuse before any mutation, so a bad
link cannot half-apply.

The help text names `aeat app ledger attach` as the evidence door (`:899`), so the
removed path routes the operator to the retained verb rather than leaving a dead
instruction.

Asserted by `test_link_requires_invoice_id`
(`src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py:39`) and
`test_link_rejects_removed_evidence_id_grammar` (`:46`), with the grammar gate
`test_ledger_link_rejects_retired_evidence_id_grammar`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:201`) covering
the same removal from the root surface. All passed in the coordinator's W04 gate run
(`1 failed, 154 passed`; the single failure was the unrelated S112 control).

## Notes

The separate `app ledger evidence` family (`_ledger_evidence_cli.py`) legitimately
retains its own `--evidence-id` options and stays in the profile-bound write guard
`PROFILE_BOUND_WRITE_VERB_PATHS`
(`src/cadrumo/application/storage_write_policy.py:152`-`:154`). Only the `link`
verb's evidence grammar was retired; the hand-sweep of that unscanned allowlist
confirmed `app ledger link` remains guarded (`:113`) and no dead entry was left.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
