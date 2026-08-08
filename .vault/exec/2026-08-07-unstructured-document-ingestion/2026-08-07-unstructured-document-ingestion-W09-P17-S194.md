---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3c9527749e3f29e50730803e7ea154f10c5e92c6c96d6b6a16be281668212262'
step_id: 'S194'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `_confirm_establishment.py`, the confirm path's single reach into the establishment apparatus: it routes the counterparty into the ladder, reads the filer's own territory from the profile authority, places each answer on the issuer or customer slot by the direction the operator settled, and hands both into the classification criteria through the declared-facts channel.
- Call it from `confirm_invoice_draft_from_evidence`, after the blocking gate and before any resolution work, so a draft whose findings are unanswered never reaches the ladder or the counterparty-fact store.
- Carry the outcome on `InvoiceConfirmationResult.establishment`, on the minting path and on the guarded idempotent no-op alike.
- Surface an exhausted ladder, a contradicted confirmed fact and a registration conflict as review items in the review gate's own blocker shape, built through the gate's own identifier derivation rather than a second one.
- Add the end-to-end gate driving a real Facturae document through the real confirm verb to a resolved territory, plus the exhaustion direction.

## Outcome

The ladder had zero production callers. Measured before the change, `resolve_draft_counterparty_establishment` and `resolve_counterparty_establishment_scope` appeared outside their own module and the package facade nowhere at all, and `assemble_classification_criteria` and `DeclaredFacts` were in the same state: the criteria's country and postal parameters were supplied only by tests. Every rung, the identification and establishment split, the country vocabulary, the alpha-3 correspondence and the Spanish postal derivation worked in isolation and nothing invoked any of them from a path a person could run.

They are now reached from the confirm verb. A Facturae document stating a Spanish country and a Las Palmas postal code resolves to the Canarian territory through the postal rung, and the resolution arrives at the criteria as a declared fact rather than as a re-derivation: after the change the assembly no longer reports the issuer's residency among its missing inputs, which is the difference between handing a value to the assembly and the assembly consuming it.

Neither authority is doubled. The assembly can derive a scope from a printed country and postal code itself, and the resolution deliberately hands it neither for a party it has already resolved. The second derivation would be reached exactly where the first refused, so it would resurrect every answer the ladder declined to give.

An exhausted ladder invents no territory. It carries no scope, no rung and no declared fact, and surfaces a resolvable item naming the counterparty's identifier. The items are surfaced rather than refused, which is a stated interim recorded in the module's own prose: the once-per-counterparty answer has no operator-facing verb to persist through yet, so refusing here would make every domestic invoice permanently unconfirmable rather than asking once, and a refusal nobody can answer is not a review gate.

## Verification

The gate, before the change:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_confirm_path_establishment_reach.py -n0 -q -m "unit"
    3 failed in 7.40s

with the confirm itself succeeding and the result carrying no establishment at all, which states the gap as a failure rather than as a claim. After:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_confirm_path_establishment_reach.py -n0 -q -m "unit"
    3 passed in 5.70s

The owning suite, sequentially:

    uv run --no-sync pytest src/cadrumo/application/ledger -n0 -q -m "unit or integration"
    6 failed, 1098 passed, 16 warnings in 229.66s (0:03:49)

The six failures are all in the preflight modules and all one signature: an enum member renamed in the IVA domain and not swept through `_preflight.py`. That file is committed, untouched by this Step, and the rename belongs to the identification re-key lane; the failures are red at HEAD independently of this change.

The confirm-adjacent suites after the type fixes:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_draft.py src/cadrumo/application/ledger/tests/test_counterparty_side_selection.py src/cadrumo/application/ledger/tests/test_evidence_confirm_iva_category.py src/cadrumo/application/ledger/tests/test_establishment_ladder.py -n0 -q -m "unit or integration"
    70 passed in 33.44s

Lint, formatting and the canonical type checker are clean on every file this Step authored or modified.

Two mutation proofs, each patched from outside the repository so nothing under the source tree changed, and each carried to the third rung: a banner proving the plugin loaded, an invocation counter proving the patch was reached, and the intended observable state change asserted.

The silent-default mutation makes an exhausted ladder resolve to the mainland, which is the defect the exhaustion gate exists to catch:

    MUTATION PLUGIN LOADED: exhausted ladder -> ES_MAINLAND
    MUTATION APPLIED at resolve_counterparty_establishment_scope
    MUTATION INVOCATIONS: invoked=3 mutated=1
    1 failed, 2 passed in 6.37s

The exhaustion case reds and the two resolving cases stay green, which is correct: the patch changes only the exhausted document.

The direction mutation swaps the issuer and customer slots, which is the wiring failure that carries a correct territory while meaning the opposite party:

    MUTATION PLUGIN LOADED: declared-fact slots swapped
    MUTATION APPLIED at _declared_facts
    MUTATION INVOCATIONS: invoked=3 mutated=3
    1 failed, 2 passed in 6.50s

## Notes

Two semantic searches ran before any code was written, one on the deliverable in domain terms and one on the mechanism. Both returned the ladder module itself as the top hit and neither surfaced a second implementation of the concept, so this Step adopted the existing apparatus rather than authoring anything parallel to it.

Three surfaces are deliberately not landed and each has a reason.

The package facade export is held. The file carries another lane's uncommitted work for a module that is not yet tracked, so a pathspec commit would have taken their content with it. No consumer needs the export: the confirm path reaches the new module through its own package, which is an intra-package private import and correct. The export belongs with its first cross-package consumer.

The generated API stubs are held for the same reason. A scaffold run regenerates the shared package index, and the regenerated file names another lane's untracked module beside this one, so committing it would point the documentation build at a module absent from the tree and crash it. The stub lands on the next scaffold sweep once that module is in.

The review items are surfaced and not refused, which is the interim described in the Outcome. Closing it needs an operator-facing verb that persists a counterparty-level answer through the existing fact store, whose writer also has no production caller. Until that channel exists, refusing on exhaustion would block every domestic invoice rather than asking once per counterparty.

The counterparty-fact store's writer and the once-per-counterparty deduplication loop therefore remain unreached, and the category-minting convergence stays where it is, held under its own row.
