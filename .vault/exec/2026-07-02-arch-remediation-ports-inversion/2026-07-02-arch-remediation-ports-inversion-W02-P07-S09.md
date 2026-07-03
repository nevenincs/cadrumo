---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Relocate the transactions repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries and ## Scope

- `src/aeat/domain/transactions/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the transactions repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/transactions/_repository.py`

## Description

- Create the persistence adapter `src/aeat/adapters/persistence/profile/transactions.py` holding the concrete `TransactionCatalogueRepository`, behind the pre-existing `TransactionCatalogueRepositoryProtocol`; redeclare the persisted-envelope namespace/version constants adapter-side to avoid orphaning stored envelopes.
- Trim `src/aeat/domain/transactions/_repository.py` to its pure surface: the `ImportSummary` record, the `transaction_object_key` / `transaction_index_object_key` key-derivation helpers, and the namespace/version constants. Drop the concrete from the domain facade `__all__`.
- Import the adapter's pure domain dependencies (errors, models, key helpers) through the public `domain.transactions` facade so the relocation adds zero import-hygiene Family-1 violations.
- Sweep ~130 consumers to the adapter home via an AST-guided rewrite; verify zero residual concrete imports in all three forms (absolute, intra-domain relative, deferred/function-local).
- Move the two dedicated repository tests to the adapter tests folder as `test_transactions_repository.py` / `test_transactions_repository_roundtrip.py`; retag `hex_domain` to `hex_persistence_adapter`; update the logger assertion to the adapter module.
- Re-point the invoices-test transaction roundtrip, the runtime-repository enrollment gate, and the docstring core-struct anchor to the adapter home.
- Update `.importlinter` (drop 5 stale domain edges, add 81 application + 3 domain adapter pins, bump the application-to-adapters ratchet 747 to 828) and `test_lazy_import_policy.py` (move deferred storage edges to the adapter class, add the four app deferrals, drop two converted stale domain edges, raise ADAPTER_INTERNAL_DEFERRAL 162 to 170 and APPLICATION_DEFERRAL 500 to 502).
- Regenerate the apidocs stub and its parent toctree entry.

## Outcome

Relocation landed on the `chore/eliminate-shims` branch. The transaction repository and roundtrip suites pass against real encrypted SQLite; `pytest --collect-only -q src/aeat` is clean; the importlinter ledger ratchet, sensitivity, enrollment, docstring, and hardening-convention gates are green. The layered contract, `test_lazy_import_policy`, and `test_import_hygiene_gate` remain red only from committed peer features (LLM run-telemetry #407, bucket-maintenance sandbox #422, rectificativa-amendment #234, plus the calc-move test-debt) that pre-date this landing; none of the residual violations are transactions edges.

## Notes

- The originating Step row cited `src/aeat/domain/transactions/_repository.py` only; the actual blast radius spanned ~130 consumers plus the two moved tests and the four structural gates, all landed in one atomic commit.
- A concurrent peer edit to the telemetry test `test_llm_classify_run_telemetry.py` (a transactions consumer that also carries #407 run-telemetry code) briefly reverted the retarget in the working tree, so the first commit captured a broken domain-facade import for that one file; corrected by amending the retarget hunk into the relocation commit after confirming the staged set carried no peer content.
- Peer WIP (renta M100, rectificativa-amendment, LLM run-telemetry, bucket-maintenance sandbox, overview pipeline) was left untouched in the working tree and out of the commit.
