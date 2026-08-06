---
tags:
  - '#plan'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_hash: 'sha256:86d16a8efc3aac8844ea8f1fdb736e0e6fbfc705978a34f79364eaac99e7e40f'
tier: L2
related:
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-research]]'
---

# `invoice-canonical-structure` plan

Retire one of two invoice aggregates so only the canonical structure remains, and make the surviving one usable.

## Description

Executes `2026-08-06-invoice-canonical-structure-adr`, grounded in `2026-08-06-invoice-canonical-structure-research`. One ADR, one plan.

The ADR supersedes `2026-06-10-ledger-invoice-unification-adr` on its ruling that both invoice aggregates survive, because that ruling's premise (rich is the calculation aggregate, slim is the operator-CRUD record) was falsified 18 days after it landed by commit `432fc96d29`, which put the slim store into the M347/M349 calculation mesh. Two stores now feed one aggregation with no reconciliation between them, producing an unguarded double-count in one direction and a clave-asymmetry under-declaration in the other.

**Tier `L2`, chosen from the real structure rather than inflated.** The work has five phases with load-bearing ordering between them and no genuine grouping above the phase level. `L1` cannot express the ordering, which is the plan's most important property: the canonical decision must land before anything is deleted. `L3` would add a Wave frame containing a single wave, which is inflation. `L2` is the honest fit.

Phase ordering is the safety property. `P01` proves the replacement exists, `P02` makes the canonical surface usable, and only then does `P03` delete. `P04` and `P05` are independent of the fold. `P05` is severable and could be lifted into its own campaign without disturbing the rest.

## Steps

### Phase `P01` - Prove canonical coverage before anything is deleted

Establish that every declarable fact the slim store contributes today is reproducible on the canonical aggregate, and resolve the M349 clave asymmetry in the permissive direction. Nothing is removed in this phase, it is the gate on P03.

- [ ] `P01.S01` - Prove the canonical path reproduces the M347 per-party totals and M349 operator rows that the two-store union produces today, for a bucket exercising both stores; `src/cadrumo/application/invoices/tests/test_source_resolver.py`.
- [ ] `P01.S02` - Make the iva_category clave fallback the surviving behaviour and prove an invoice carrying a category but no operation_type is declared rather than dropped; `src/cadrumo/application/invoices/_source_resolver.py`.
- [ ] `P01.S03` - Inventory every slim-store consumer and record the named canonical replacement for each, refusing to proceed to P03 while any consumer has no replacement; `src/cadrumo/application/ledger/_business_operation_invoice.py`.

### Phase `P02` - Extend the writer surface to the canonical model

Additive only. Make the canonical aggregate's existing fields reachable from single-invoice entry, so canonicalisation does not leave one store the operator still cannot express a retencion, a regime, or a mixed-rate invoice in.

- [ ] `P02.S04` - Add retention-rate and retention-amount options to the canonical writer and both entry verbs, with an encrypted roundtrip proving they persist; `src/cadrumo/application/invoices/_creation.py`.
- [ ] `P02.S05` - Add explicit recargo, iva-category, invoice-class and series options so every regime is expressible without inferring one from operation-type; `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [ ] `P02.S06` - Accept operation-date on every entry verb including the guided one, so a guided entry can reach a declared devengo rank rather than only the proxy rank; `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [ ] `P02.S07` - Stop synthesising exactly one line and accept a supplied line set, proving a two-line invoice at different rates persists and aggregates per line with no persisted-schema change; `src/cadrumo/application/invoices/_creation.py`.

### Phase `P03` - Fold and delete the slim store

Move the operator CRUD surface onto the canonical aggregate, then remove the slim model, services, repository, namespace, payloads and locale leaves from the tree. Delete, never bridge.


### Phase `P04` - Close the remaining second-authority and boundary gaps

Resolve the unwired second Invoice writer, rename the misleading category token, and add the confirm-boundary plausibility gate. Independent of the fold.


### Phase `P05` - Close the M303 screen blind spots and give M390 an equivalent

Severable and highest filing consequence. Extend the invoice-versus-ledger screen past its ES-only and cuota-only reach, and add an M390 equivalent, because the M390 blocking rule compares two ledger-derived sides and cannot detect consistent under-population.


## Parallelization

`P01` must complete before `P03` begins. This is the plan's one hard ordering constraint and its reason for existing: `P03` deletes a live M347/M349 source, and `P01` is what proves the canonical path already carries that coverage. A deletion landing before its replacement is verified is how a campaign loses work.

`P02` is additive and may run concurrently with `P01`. It touches the writer surface and the CLI, not the resolver.

`P04` is independent of `P01` through `P03` and may run at any time. Its three steps are mutually independent and may run concurrently with each other.

`P05` is severable from the whole plan. It shares subject matter but touches neither store's shape. It may run concurrently or be lifted into its own campaign.

Two campaigns are live on this surface: `2026-08-05-ledger-invoice-decomposition` and `2026-08-06-llm-invoice-read-reconciliation`, the latter constrained to not alter the `Invoice` domain model. `P03` collides with that constraint and must not begin until that campaign settles. Before any first edit to a shared file, run `git diff -- <file>` and abort on non-authored WIP.

## Verification

The plan is complete when every Step is closed and the following hold.

Coverage is preserved, not merely assumed: a test proves the canonical path produces the same M347 per-party totals and the same M349 operator rows that the two-store union produces today, for a bucket exercising both stores.

The double-count is closed by construction: no `BusinessOperationInvoice` symbol remains in the tree, confirmed by a tree-wide search, and the union at `_source_resolver.py:200-202` is gone rather than guarded. A cross-store dedup helper appearing anywhere is a failed outcome, not a partial success.

The M349 clave asymmetry resolves permissively: an invoice carrying an `iva_category` implying a clave but no `operation_type` is declared, where it is silently dropped today.

The writer surface reaches the model: a strict save-load-equality roundtrip through the real encrypted namespace, with retencion, recargo, `iva_category`, `invoice_class`, `series` and `operation_date` all populated non-default, plus an anti-tautology proof that a mutated on-disk payload surfaces inequality or a `ValidationError`.

Mixed-rate lands: a two-line invoice at different rates persists and aggregates per line, with no change to the persisted schema.

Exactly one `Invoice` writer persists, and `python -m dev.docs.apidocs scaffold --check` plus the locale `scaffold --check` both exit clean after the deletions.

Every deletion step names its replacement in its execution record. Every symbol relocation lands as one atomic explicit-path commit carrying the canonical-site move, every consumer update, every fixture update and every `__all__` update, with `uv run --no-sync pytest --collect-only -q` observed clean immediately before the commit.
