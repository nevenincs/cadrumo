---
tags:
  - '#audit'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
  - "[[2026-07-17-ledger-evidence-atomicity-adr]]"
  - "[[2026-07-17-ledger-evidence-atomicity-audit]]"
---

# `ledger-evidence-atomicity` audit: `Close honesty review`

## Scope

Fresh-context close honesty review of the `ledger-evidence-atomicity` plan, which reports
seventeen of seventeen steps complete. The reviewer carried no prior context in this
campaign and treated every plan and exec-record claim as unverified until re-checked
against the tree at HEAD (`76cc1a082bbf`). The mid-campaign `2026-07-17-ledger-evidence-atomicity-audit`
document is a continuous-gate review scoped to phases P01 and P02 only (two low findings,
both since closed under P03.S16/S17); it is not a close review and does not substitute for
this gate.

Every one of the seventeen exec records was read in full and cross-checked against source
at HEAD: the write-authority guard (`_EVIDENCE_PATCH_FIELDS`, the `_evidence_authority`
threading), the atomic split writer, the invoice-link writer, the replay-removal surface,
and the contract-migration steps (payloads, help/risk metadata, four locale catalogues,
docs, absence proofs). Every cited test module was executed live rather than trusted from
prose: `test_actions_update_evidence.py` + `test_actions_create_evidence_validation.py` +
`test_llm_evidence_split_apply.py` (22 passed), the CLI proof suites `test_ledger_link_check_verbs.py`
+ `test_audit_verbs.py` + `test_root_grammar_invariants.py` (39 passed, integration), the
full `application/ledger` suite (417 passed), `test_json_schema_conformance.py` (157
passed, integration), `test_documented_command_conformance.py` (352 passed, integration),
`test_parity.py` (33 passed), `test_risk_table_parity.py` + `application/operator_surface`
(56 passed), `domain/buckets` (19 passed), ruff on every touched module (clean), and a
full-tree `--collect-only` (13813 collected, zero errors). Replay-surface absence
(`EvidenceBundleService.replay`, `modelo audit replay`, `ModeloAuditReplayResult`,
`MODELO_AUDIT_REPLAYED`, `LedgerLinkEvidenceUpdatePayload`, the retired `link --evidence-id`
grammar) was independently re-swept with `rg` across `src/` and `docs/`, not read from the
exec records' own claims. The four locale catalogues were parsed and diffed directly to
confirm the `ledger.link` block carries no orphaned evidence keys in any language. No file
was modified; all verification was read-only plus live test execution.

## Findings

### invoice-link-writer-not-atomic-on-success-path | high | The "single atomic invoice-only linkage writer" performs two independently-committed writes

`link_manual_transaction_invoice` (`src/cadrumo/application/ledger/_actions_manual.py:259`)
is the writer this campaign built and centralised: P01.S01's step text calls it "a single
atomic invoice-only linkage writer" and its own docstring states "Every rejection fires
before any catalogue write, so a refused link leaves the transaction, invoice catalogue,
and event history unchanged." That refusal-path claim is true and is proven by
`test_failed_invoice_link_leaves_transaction_and_history_unchanged` and
`test_invoice_linkage_does_not_mutate_evidence`. The success path is a different story: the
writer delegates to `link_invoice_transaction_repositories`
(`src/cadrumo/application/invoices/_linking.py:75`), whose persistence is
`invoices_repo.save(result.invoices)` followed by `transactions_repo.save(result.transactions)`
— two calls, each opening its own independent `session_scope` (confirmed by reading
`InvoiceCatalogueRepository.save` and `TransactionCatalogueRepository.save`, each committing
its own transaction via `SecureObjectRepository.save`/`apply_batch`). A process crash, a
disk error, or any exception raised between these two calls leaves the invoice catalogue
showing `linked_transaction_ids` containing the transaction while the transaction row's
`invoice_id` field is never written (or the reverse, depending on which write lands first)
— exactly the partial-commit divergence the campaign's own ADR names as one of its two
motivating defects ("Combined invoice and evidence linking can partially commit, leaving a
transaction whose evidence links, provenance, and event history disagree with each other").
No test forces a failure between the two saves to prove the success path is atomic, because
it is not: only the pre-write refusal path is guarded. There is also no detection safety
net — `verify_link_consistency` / `LinkInconsistency`
(`src/cadrumo/domain/invoices/_service.py:236`) exists and is exercised in its own unit
tests, but no CLI verb calls `verify_invoice_repository_links`
(`src/cadrumo/application/invoices/_queries.py:90`) anywhere in `src/cadrumo/entrypoints`;
an operator has no way to discover a drifted link even after the fact. This two-write
pattern in `_linking.py` predates the campaign (traced via `git log --follow` back through
pre-relocation history) and the CLI's pre-campaign combined `link --invoice-id/--evidence-id`
command called into the same non-atomic function — so the gap is not a regression this
campaign introduced. What the campaign did was rename, centralise, and market this exact
function as "the sole invoice-linkage writer" and an "atomic" one, close the CLI's only
alternate route to it, and mark the step complete without correcting or even scoping the
atomicity claim to the refusal path only. The infrastructure to fix this already exists
one file away: `_save_transaction_catalogue_and_events`'s sibling
`_save_transaction_catalogue_invoices_and_events`
(`src/cadrumo/application/ledger/_actions_common.py:829`) already composes a transaction
catalogue, an invoice catalogue, and bucket events into one `apply_batch` using
`to_secure_object_write()` on both repositories — the exact pattern this writer needs and
does not use. One mitigating fact worth recording for balance: both `link_transaction`
(invoice side) and `link_invoice` (transaction side) are individually idempotent by design
(`link_transaction`'s own docstring: "Duplicate links are idempotent: calling this helper
with an already-linked transaction returns a value-equal catalogue rather than raising"),
so a manual retry of the same `ledger link` command after a crash would self-heal the
divergence. That does not make the write atomic — it only means the operator has to know a
crash happened and choose to retry, with no detection surface prompting them to.

### stale-docstring-describes-removed-split-then-patch-path | medium | apply_evidence_split's own docstring documents the atomicity model this campaign deleted

`apply_evidence_split` (`src/cadrumo/application/ledger/_llm_classification.py:1210`) is the
production entry point P02 rewired onto the new atomic writer. Its docstring (lines
1222-1228) still reads: "Composes the established single writers rather than
re-implementing them ... first `split_transaction` redistributes the parent into children
... then for each child `update_manual_transaction_fields` stamps the model-selected expense
category and IVA category ... the parent invoice's evidence link, and the `llm:<model>`
provenance." That is a precise description of the PRE-campaign split-then-patch path P02.S04
existed to remove — the actual body (verified by reading the function in full) calls
`split_transaction_with_classified_children` once and performs no generic per-child field
patch at all. `git log` on this file confirms commit `8120535d40` (P02.S04, "atomic
evidence-driven split persistence in one transaction") is the exact commit that rewired the
body without touching the docstring above it, and neither S05 nor S17's later commits on
this same function caught it either. This module is autodoc'd
(`docs/api/cadrumo.application.ledger._llm_classification.rst`), so the stale description
ships into the generated developer reference misdescribing the atomicity guarantee of the
one function this whole phase exists to make atomic. A neighbouring staleness: the sibling
`apply_evidence_classification` docstring (~line 1338) compares itself to "the per-child
write `apply_evidence_split` performs" as if that per-child write still goes through
`update_manual_transaction_fields`, which is no longer true for the split path.

### pathspec-commit-swept-peer-locale-wip | low | Disclosed, adjudicated, no data lost, but land it in the record

S13's exec record self-discloses an incident: the finalising commit `59ba31fcef` used a
pathspec `git commit -- <4 .yml>`, which — per the documented
`pathspec-commit-takes-working-tree` behaviour — commits WORKING-TREE content rather than
the staged apply-cached index, so it captured an unrelated peer campaign's live
passphrase/recovery locale WIP alongside the intended link-key removal. The reviewer
independently re-read `git show 59ba31fcef` and confirms the disclosed scope exactly: the
intended ~15-line `ledger.link` grammar change is present, plus ~20 swept lines of
`cli.config.secrets.*` and `cli.config.profile.passphrase.change` keys in all four
catalogues that belong to a different campaign. All content is present at HEAD; nothing was
lost, only mis-attributed to this SHA. The exec record states this was adjudicated ACCEPT by
the team lead at the time, with a reasoned no-amend/no-revert rationale (the commit is
buried under two later commits). This is exactly the honest self-report the close-honesty
discipline exists to reward, not penalise — recorded here only so the campaign's git-history
provenance note lives somewhere durable beyond one exec record's Notes section.

## Recommendations

Fix `invoice-link-writer-not-atomic-on-success-path` before treating this campaign's
atomicity claim as complete: either (a) give `link_manual_transaction_invoice` a
`bucket_event_repository` parameter and route its persistence through a new
`_save_invoice_and_transaction_catalogues` composed the same way
`_save_transaction_catalogue_invoices_and_events` already composes transaction + invoice +
events into one `apply_batch`, so a crash between the two catalogue writes becomes
structurally unreachable the same way it already is for attach and split; or (b), at
minimum, narrow the writer's docstring and the plan's own "atomic" claim to state plainly
that only the refusal path is atomic and the two-catalogue success write is not, and wire
`verify_invoice_repository_links` behind a CLI verb (e.g. `aeat app ledger invoice check`)
so a drifted link is at least detectable by the operator. Option (a) is preferable: the
composing primitive already exists in the same package and the change is small.

Fix `stale-docstring-describes-removed-split-then-patch-path` by rewriting the
`apply_evidence_split` and `apply_evidence_classification` docstrings to describe the actual
`split_transaction_with_classified_children` single-writer path, so the generated API
reference stops shipping a description of a write pattern this campaign deleted.

No action needed for `pathspec-commit-swept-peer-locale-wip` beyond this record; it is
already adjudicated and non-destructive.

## Verdict

NOT structurally complete as a closed atomicity guarantee, though close. Sixteen of the
seventeen steps hold up fully against re-verification: the evidence write-authority guard,
the atomic split writer, the replay removal, and the contract migration are all real,
tested, and independently reproduced by the reviewer with live test runs rather than trust
in prose. The one load-bearing gap is squarely inside the campaign's own thesis: the
"single atomic invoice-only linkage writer" P01.S01 built and P03.S07 made the CLI's sole
route to is atomic only on its refusal path, and the success-path write it performs across
two catalogues is exactly the class of partial-commit hazard this campaign exists to close.
This is not a regression the campaign caused — the two-write pattern predates it — but the
campaign's own closure claim ("atomic ... linkage writer") is not fully substantiated by
what ships, and no test or CLI-exposed check would catch the drift if it ever fires. Treat
the seventeen steps as landed and keep the plan's checkboxes as they are (the work described
in each step genuinely happened), but do not declare the campaign's THESIS — invoice linking
is atomic — true until the high finding above is closed with a real fix and a forced-failure
test proving the two-catalogue write is now atomic, mirroring the proof pattern P02 already
established for the split writer.
