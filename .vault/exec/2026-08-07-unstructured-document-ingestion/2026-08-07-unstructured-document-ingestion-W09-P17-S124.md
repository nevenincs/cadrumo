---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8965e6ac36ef9b95458e48e21137d9865e450b89cc1eeb1294ce7ffc42f5c07b'
step_id: 'S124'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/locales`

## Description

- Reproduce the duplication end to end against a real encrypted bucket before
  changing anything, and capture the transcript.
- Establish the actual creating path from a document to a persisted record, and
  the guard that did and did not fire on each of three re-run shapes.
- Build the idempotency candidate with the full argument set the creating writer
  receives, so the candidate is the record that would be written.
- Add a document-identity guard keyed on the attachment content address, read
  off the manifest link the confirm path already writes.
- Derive the guarded-retry match from the invoice model fields, excluding only
  the five a later verb owns.
- Refuse a divergent re-confirm through the typed invoice validation error,
  naming the divergent fields, with the message in all four locale catalogues.
- Rewrite the CLI gate that asserted the duplication as its contract.
- Add an application-level gate over the deterministic structured lane, and a
  CLI-level gate proving the refusal is reached through the real command tree.

## Outcome

### The reproduction came first

The defect fired before any edit, against a real encrypted bucket, a real
content-addressed attachment store and the real Facturae parser. Two confirms of
one evidence record, the second restating the invoice number, left the catalogue
holding two invoices, and the run log shows the single attachment
`b58ac2df...` linked to both invoice ids:

    REPRO-A first:  b4500d31... created=True
    REPRO-A second: 7cda1c21... created=True
    REPRO-A catalogue size: 2
    AssertionError: DUPLICATION: 2 invoices from one document

Both records feed the same M303, M347 and M390 aggregations, and AEAT reconciles
some of those against the counterparty's own declaration.

### The creating path is the confirm verb, and it mints an invoice

The brief framed this as a duplicated ledger transaction.
`create_manual_transaction` has exactly one caller in the tree — the manual
`ledger add` CLI handler — and no document path reaches it. The document-to-
record door is `confirm_invoice_draft_from_evidence`, which delegates to
`create_catalogue_invoice`, the sole sanctioned catalogue writer. The blast
radius argument is unchanged, because an invoice feeds the same aggregations;
the guard would have been placed in the wrong module had the noun been taken on
trust.

The batch runner never confirms anything. It writes an evidence record and a
draft and stops, keyed on content address plus declared direction through the
evidence store's own idempotency key. So there is one creating door, and the
guard-on-one-path-but-not-the-other asymmetry this codebase keeps producing has
no surface to appear on here.

### Two live failures, one root cause

The derived invoice id folds six fields: kind, invoice number, issue date,
counterparty tax id, currency and grand total. That answers "is there already a
record carrying these figures". It cannot answer "has this document already been
turned into a record", and the confirm path had no other guard.

The loud failure is duplication: a re-confirm resolving any of the six
differently — an operator correcting a mis-read number, a second reading lane
rounding a total differently — hashes to a fresh id, passes the same-id check
and mints a second record.

The quiet failure is worse and was equally live. A re-confirm differing only
*outside* the six addressed the stored record and was returned unchanged, so an
operator correction to the counterparty name, the IVA category, a retención or
the notes vanished with nothing surfaced. The contract names that as the subtle
failure, and it was in the product.

The mechanism behind the quiet half is the part worth keeping: the candidate
handed to the lookup was built with a **subset** of the arguments the creating
call receives — no category, no retención, no invoice class, no series. The
comparison was correct over what it was given; it simply was never given those
fields. No amount of reading the comparison logic would have revealed it.

### Identity basis, and what was excluded

Identity is the **attachment content address** — the SHA-256 of the document's
bytes — read off the manifest's linked-invoice list, which the confirm path
already writes through the sanctioned linking helper. No second index is
introduced, nothing is folded into any derived id, and the address is clock-free
by construction. Because the attachment store is content-addressed, the same
bytes re-attached under a fresh evidence id resolve to the same document, so a
re-run of an ingest is covered without a special case.

Excluded deliberately: **one logical invoice captured as two different files**
(a rescan, or a PDF beside its embedded XML) whose resolved fields differ.
Issuer tax id plus invoice number plus date is the derived id's own basis minus
the totals, and refusing on it would block a rectificativa, a number legitimately
repeated across series, and a corrected re-issue. That is a judgement about false
refusals rather than a gap to close reflexively, and it is carried as its own row
rather than being decided silently inside this one.

### The match compares every persisted field

The comparison is **derived from the invoice model's declared fields**, not a
hand-written list, so a field added to the model joins the match when it is
declared rather than when someone remembers. Five fields are excluded, and each
is one a *later* verb owns: payment status, payment id, linked transaction ids,
and the two record-lifecycle stamps. Comparing them would make an ordinary paid
invoice refuse its own re-confirm, which is why the exclusion is argued in a
named constant with its reasoning rather than inlined.

Three outcomes reach the operator. An identical retry returns the stored record
as a no-op with the existing info notice on the shared envelope spine. A
divergent re-confirm refuses through the typed invoice validation error, naming
the divergent fields, because the operator's next move depends entirely on which
field moved — a corrected number means the stored record is wrong, a different
total means these are not the same invoice. A genuinely new document creates.

### A test that blessed the defect

The CLI gate `test_confirm_of_a_different_override_mints_a_distinct_invoice`
asserted `created is True`, two distinct ids, and a catalogue count of two. That
is the duplication written down as the contract, which converts a live bug into
verified behaviour and makes the next reader hesitate to change it. It now
asserts the refusal and a count of one, renamed for what it actually pins.

## Verification

Application-level gate, five cases over the deterministic structured lane:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_document_identity.py -n0 -m "unit" -p no:randomly
    5 passed, 15 warnings in 45.97s

CLI-level reachability, three cases through the real Typer tree:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_duplicate_cli.py -n0 -m "integration" -p no:randomly
    3 passed in 18.70s

Regression across the whole confirm surface, seven files:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_document_identity.py src/cadrumo/application/ledger/tests/test_evidence_draft.py src/cadrumo/application/ledger/tests/test_evidence_confirm_recargo.py src/cadrumo/application/ledger/tests/test_evidence_confirm_iva_category.py src/cadrumo/application/ledger/tests/test_evidence_confirm_multi_rate.py src/cadrumo/application/ledger/tests/test_evidence_confirm_grounds_for_renta.py src/cadrumo/application/ledger/tests/test_evidence_confirm_rate_derived_category.py -n0 -m "unit or integration" -p no:randomly
    42 passed, 15 warnings in 65.38s (0:01:05)

Lint, format and type checks clean on every touched file under `ruff check`,
`ruff format --check` and `ty check`.

### Mutation proofs

Both mutations were installed from a plugin module **outside** the repository at
plugin scope, each asserting the replacement is not the original so a patch that
never landed cannot pass as a proof, and each printing on install. No tracked
file was edited to produce them.

Blinding the document-identity lookup so it reports nothing was ever minted:

    2 failed, 3 passed, 15 warnings in 42.84s

Both failures are `DID NOT RAISE InvoiceValidationError` — the duplication
reproduces. The three that stayed green did so legitimately: the no-op case has
no duplicate to catch, the swallow case is still caught by the whole-record match
on the same-id branch, and the field-coverage case is a unit on the comparison
helper the mutation does not touch.

Blinding the whole-record match so it reports no divergence:

    3 failed, 2 passed in 25.48s

The two greens are legitimate: a blind match makes everything look identical, so
the no-op case is still answered correctly, and the same-bytes case asserts only
that the document guard raises without reading the field list.

The same document-guard mutation against the CLI gate:

    2 failed, 1 passed in 10.51s

which is what establishes the refusal is reached through the real command tree
rather than merely present in the module.

## Notes

**One claim shipped unproven, and it is named rather than passed.** The existing
CLI confirm suite cannot run in this environment: all seven cases fail with a
local inference connection failure at the *extraction* stage, before reaching any
code this Step touched. Six of the seven are untouched by this work and fail
identically, which is how the failure was attributed to the environment rather
than the change. No local model was started, because live local inference crashes
the session outright. The corrected gate in that file is therefore committed but
unproven green. The new CLI gate added here deliberately uses the structured
document rather than a text-bearing PDF, so the deterministic parser carries it
and it runs on any machine — which is exactly why it runs where the sibling suite
cannot. Making that suite runnable without a live model is carried as its own row.

**A sweeping bare commit took this work mid-flight.** A peer's whole-index commit
landed the guard source, the new application-level gate and all four locale
entries before they were committed here. Nothing was lost — the swept content is
byte-identical to the final version, verified by an empty diff afterwards — but
had the sweep caught the work mid-edit, a partial duplication guard would have
landed under another author's message, and a partial guard reads as protection
while providing none. Every edit in this Step was built from the committed HEAD
bytes rather than the working copy, and a concurrent peer's unrelated in-flight
hunk in the same file was verified intact before and after each patch.

**One gate could not be committed.** The repository index lock has been held with
a frozen modification time for several minutes, so the holder is dead rather than
contending. It was left untouched, and the commit was skipped rather than forced.
While diagnosing it, the index was found holding a staged set that is the exact
inverse of another lane's just-landed commit — every file a pure deletion — which
would revert that lane's work if any bare commit fired against it. Reported
rather than touched.

**A shell pipeline once reported a false success.** A retry loop tested the exit
status of a pipeline ending in `tail`, which reports the last command's status
rather than the commit's, so a failed commit read as a successful one. Caught
immediately and corrected before anything depended on it; the underlying commit
had not landed.
