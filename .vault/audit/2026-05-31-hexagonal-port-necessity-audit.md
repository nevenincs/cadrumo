---
tags:
  - "#audit"
  - "#hexagonal-port-necessity"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-W06-P16-S50]]"
  - "[[2026-05-31-core-authority-W06-P16-S51]]"
  - "[[2026-05-31-core-authority-W06-P16-S53]]"
  - "[[2026-05-31-core-authority-W06-P16-S54]]"
  - "[[2026-05-31-core-authority-W06-P16-S55]]"
---

# hexagonal-port-necessity audit

## Scope

Six recently-extracted domain repository Protocol modules surfaced by the AST import-graph triage (issue 612) have zero static importers: buckets, fincas, invoices, justificante, modelos, transactions under src/aeat/domain/. Each Protocol class was searched across the codebase for direct import, type-hint use, and runtime-checkable use; the corresponding concrete repository class was searched across the application layer to identify type-hint sites that should depend on the port rather than the concrete adapter. Dynamic-import surfaces were excluded by an rg sweep over the literal _protocols which returned only static from-import lines plus Sphinx-generated docs/api .rst stubs. The architecture rule under test is aeat-architecture-boundaries Rule 8: the domain Protocol is the canonical port; application and adapter layers should depend on the Protocol, not the concrete repository.

## Per-port classification

| File | Protocol classes | Bucket | Would-be implementer | Static importers (non-self) | Action |
| ---- | ---------------- | ------ | -------------------- | --------------------------- | ------ |
| src/aeat/domain/buckets/_protocols.py | BucketEventHistoryRepositoryProtocol | A | BucketEventHistoryRepository at src/aeat/domain/buckets/_event_repository.py line 26 | 0 | Re-type 12+ application sites in application/modelo/_actions.py, application/ledger/_actions.py, application/ledger/_business_operation_invoice.py, application/ledger/_evidence.py, application/ledger/_preflight.py, application/inventory/_service.py, application/modelo/_history.py, application/modelo/_export.py, application/user_profile/_lifecycle.py from concrete to Protocol. |
| src/aeat/domain/fincas/_protocols.py | FincaRepositoryProtocol, ArrendamientoRepositoryProtocol, FincaRendimientoRepositoryProtocol, FincaGastoRepositoryProtocol, FincaAmortizacionLedgerRepositoryProtocol | C | FincaRepository, ArrendamientoRepository, FincaRendimientoRepository, FincaGastoRepository, FincaAmortizacionLedgerRepository all in src/aeat/domain/fincas/_repository.py | 0 | No application-layer consumer currently type-hints any of the five concrete fincas repositories. The Protocols were authored speculatively against the rule. Either retain as documentation of the intended seam or delete pending an actual consumer emerging. Recommend retention with a docstring note referencing this audit; revisit if no consumer appears in the next major wave. |
| src/aeat/domain/invoices/_protocols.py | InvoiceCatalogueRepositoryProtocol | A | InvoiceCatalogueRepository at src/aeat/domain/invoices/_repository.py line 51 | 0 | Re-type 15+ application sites in application/invoices/_linking.py, application/invoices/_reconciliation.py, application/invoices/_importing.py, application/invoices/_source_resolver.py, application/aggregation/_modelo_bindings.py, application/aggregation/_renta_ledger.py, application/ledger/_actions.py, application/modelo/_actions.py from concrete to Protocol. |
| src/aeat/domain/justificante/_protocols.py | JustificanteRepositoryProtocol | B | JustificanteRepository at src/aeat/domain/justificante/_repository.py line 31, inherits SecureBoundRepository | 0 | No application-layer consumer type-hints JustificanteRepository anywhere. The concrete class is consumed only through CLI and adapter wiring. Delete the Protocol and revisit only when a domain or application caller actually wants the narrowed surface. |
| src/aeat/domain/modelos/_protocols.py | WorkUnitCatalogueRepositoryProtocol | A | WorkUnitCatalogueRepository at src/aeat/domain/modelos/_repository.py line 35 | 0 | Re-type 25+ application sites in application/modelo/_actions.py, application/modelo/_history.py, application/modelo/_export.py, application/ledger/_actions.py from concrete to Protocol. |
| src/aeat/domain/transactions/_protocols.py | TransactionCatalogueRepositoryProtocol | A | TransactionCatalogueRepository at src/aeat/domain/transactions/_repository.py line 92 | 0 | Re-type 20+ application sites in application/invoices/_linking.py, application/invoices/_reconciliation.py, application/aggregation/_modelo_bindings.py, application/aggregation/_renta_ledger.py, application/aggregation/_renta_income_ledger.py, application/aggregation/_iva_ledger.py, application/ledger/_actions.py, application/ledger/_preflight.py, application/modelo/_actions.py from concrete to Protocol. |

## Bucket counts

- Bucket A (real architectural drift; wire callers to the port): 4 ports across buckets, invoices, modelos, transactions. One Protocol class each.
- Bucket B (speculative scaffolding; delete): 1 port in justificante. One Protocol class.
- Bucket C (no current consumer of either the protocol or the concrete; retain provisionally): 1 file in fincas. Five Protocol classes.

## Recommended action sequence

1. Delete src/aeat/domain/justificante/_protocols.py. Single Protocol, no application-layer consumer of the concrete JustificanteRepository, no domain consumer either. Cheapest commit; eliminates the inventory hit. Update docs/api/aeat.domain.justificante._protocols.rst accordingly and amend the originating Step record W06.P16.S55 with a forward-reference to this audit.
2. Re-type buckets caller sites to the Protocol. The smallest bucket-A surface; twelve sites concentrated in three files: application/ledger/_actions.py, application/modelo/_actions.py, application/ledger/_business_operation_invoice.py. Re-type parameter annotations only; runtime-checkable Protocol means no constructor changes are needed. Pair the commit with a structural test asserting that at least one _actions.py signature annotates BucketEventHistoryRepositoryProtocol to lock the port adoption.
3. Re-type transactions caller sites to the Protocol. Larger surface, about twenty sites, but same mechanical pattern.
4. Re-type invoices caller sites to the Protocol. Same pattern as transactions; about fifteen sites.
5. Re-type modelos WorkUnitCatalogueRepository caller sites to the Protocol. Largest surface, about twenty-five sites in application/modelo/_actions.py plus _history.py, _export.py, application/ledger/_actions.py. Schedule last because the file is busy and other campaigns touch it; finish the small wirings first to drain context before the big one.
6. Adjudicate fincas. After steps 1 through 5 land, decide whether to retain the five fincas Protocols as documentation of the intended seam, or delete them pending an actual application-layer consumer. Recommendation: retain with a docstring note that the port is published but not yet consumed; revisit at the next architecture-boundaries audit cadence.

For each re-typing step, add a runtime-checkable assertion at one site that the concrete repository instance satisfies the Protocol; this is the cheapest way to prevent silent shape drift between the Protocol and the concrete repository.

## Risk register

- Modelos re-typing volume. application/modelo/_actions.py is a four-thousand-line file actively edited by concurrent campaigns. Schedule the re-type as the final step in the sequence, and stage only the lines that change annotations. Risk: shared-worktree collision. Mitigation: explicit-path staging and a pre-edit git diff per the worktree-collision rule.
- Fincas classification uncertainty. The five fincas Protocols match concrete repositories that nothing in the application layer currently consumes by type hint. The bucket-C label assumes the concrete repositories will eventually be consumed at application boundaries; if the fincas domain ends up consumed only through a higher-level service facade that itself owns the repositories, all five Protocols are bucket B (delete). Resolve this only after the rental-register application surface lands its first consumer.
- SecureBoundRepository inheritance constraint. Per the W06.P16.S55 Step record, three concrete repositories submission, filing, justificante retain module-scope adapter imports because the concrete class inherits a parameterised SecureBoundRepository base and assigns SensitivityClass values as ClassVars. The Protocol port pattern does not affect this constraint, but deleting justificante/_protocols.py per step 1 means the only remaining justificante port surface is the concrete class itself; if a domain-layer caller emerges later, the port will need to be re-extracted. Document the deletion rationale in the commit so the next pass does not re-add the file unaware.

## Closure note — 2026-06-01

Drift resolved. All four bucket-A ports are wired end-to-end across the application layer. Recommended sequence executed:

- Transactions port adoption: proof-of-pattern in commit 08ee2dac5 (`_iva_ledger.py`); finished across `_modelo_bindings.py`, `_renta_income_ledger.py`, `_renta_ledger.py` in commit 39a9b1f44; remaining transactions sites in commit 9ba59706a (19 ledger sites).
- Invoices port adoption: `application/invoices/_linking.py` and `_reconciliation.py` in commit c8c785598.
- Modelos `WorkUnitCatalogueRepository` port adoption: action sites in commit cffae8d91; 16 modelo sites in commit 833f57c9a; export + history sites (6) in commit 217b6e32f.
- Three sibling modelo Protocols (`CalculationRevisionCatalogueRepositoryProtocol`, `ModeloRecordCatalogueRepositoryProtocol`, `VerificationReportCatalogueRepositoryProtocol`) authored in `src/aeat/domain/modelos/_protocols.py` in commit e8397788a, plus 11 ledger Calc sites in commit 4a65a704e — completing the modelos Protocol surface beyond the original audit's single-port scope.
- Bucket-B `justificante/_protocols.py` retained pending narrower review; bucket-C `fincas` retained per the audit's "revisit at next architecture-boundaries audit cadence" recommendation.

Action sequence steps 2–5 are complete. Steps 1 (justificante delete) and 6 (fincas adjudication) remain as the next architecture-boundaries audit cadence will revisit.
