---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` research: `manual ledger transaction entry and bucket-scoped ledger storage`

Bounded research for manual ledger transaction entry and bucket-scoped ledger storage across backend storage/profile buckets, secure objects, transaction catalogue, ledger review/edit, IVA/base/proportionality aggregation paths, reachable CLI surfaces, and the active CLI workflow redesign ADR and plan surface.

## Findings

### Storage and bucket boundaries

- Profile bucket storage is implemented and profile-scoped. `PROFILE_BUCKET_NAMESPACE` is `aeat.application.profile.bucket`, `ProfileBucketRepository.load_bucket` loads an encrypted `Envelope[ProfileBucket]`, `ProfileBucketRepository.save` writes with `SensitivityClass.IDENTITY`, and `WorkflowState` stores only `ProfileBucketPointer` entries plus `active_profile`. Evidence: `src/aeat/application/profile/_repository.py:19`, `src/aeat/application/profile/_repository.py:27`, `src/aeat/application/profile/_repository.py:59`, `src/aeat/application/profile/_repository.py:97`, `src/aeat/application/workflow/_models.py:100`, `src/aeat/application/workflow/_models.py:142`, `src/aeat/application/workflow/_models.py:161`.
- Ledger transactions are not bucket-scoped at the repository boundary. `TransactionCatalogueRepository` uses static `_TX_NAMESPACE = "aeat.domain.transactions"` and `_TX_OBJECT_KEY = "catalogue"`; `exists`, `load`, `save`, and `merge_raw_transactions` all address that single catalogue. Evidence: `src/aeat/domain/transactions/_repository.py:38`, `src/aeat/domain/transactions/_repository.py:39`, `src/aeat/domain/transactions/_repository.py:80`, `src/aeat/domain/transactions/_repository.py:92`, `src/aeat/domain/transactions/_repository.py:119`, `src/aeat/domain/transactions/_repository.py:141`.
- Transaction identity is global rather than bucket-relative. `derive_transaction_id` derives the id from transaction content, and `Transaction` plus `TransactionCatalogue` have no `bucket_id` field. Identical manual rows or imported rows in different buckets can collide unless a future bucket-aware identity rule is introduced. Evidence: `src/aeat/domain/transactions/_models.py:38`, `src/aeat/domain/transactions/_models.py:247`, `src/aeat/domain/transactions/_models.py:381`.
- The secure object table supports encrypted namespace/object-key storage but does not supply bucket scoping by itself. `SecureObjectRow` is unique on namespace and object key, and `SecureObjectRepository.save` HMAC-digests the natural object key at the column boundary. Repository callers must encode bucket identity into the namespace, key, or payload contract explicitly. Evidence: `src/aeat/adapters/persistence/storage/sql/_orm.py:121`, `src/aeat/adapters/persistence/storage/sql/_orm.py:136`, `src/aeat/adapters/persistence/storage/sql/secure_objects.py:453`, `src/aeat/adapters/persistence/storage/sql/secure_objects.py:465`.
- The active epic plan records profile bucket completion but leaves profile-scoped storage bucket work as a separate unfinished wave. W08 notes profile values live only in `PROFILE_BUCKET_NAMESPACE`; W13 remains the storage-bucket implementation area. Evidence: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md:562`, `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md:564`, `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md:857`.

### Manual entry and ledger mutation surface

- The reachable `aeat app ledger` CLI currently has `import`, `review`, and `edit`; there is no manual `add`, `create`, or `entry` command. Root registration exposes only `config` and `app`, and the mounted app families include ledger under the application surface. Evidence: `src/aeat/entrypoints/cli/_ledger.py:117`, `src/aeat/entrypoints/cli/_ledger.py:239`, `src/aeat/entrypoints/cli/_ledger.py:322`, `src/aeat/entrypoints/cli/__init__.py:222`, `src/aeat/entrypoints/cli/__init__.py:235`, `src/aeat/application/operator_surface/_contract.py:145`.
- `ledger_import` persists imported rows through `TransactionCatalogueRepository.merge_raw_transactions` and only echoes the optional `--period` in command output. It does not persist a period, bucket id, or bucket event. Evidence: `src/aeat/entrypoints/cli/_ledger.py:125`, `src/aeat/entrypoints/cli/_ledger.py:171`, `src/aeat/entrypoints/cli/_ledger.py:178`.
- `ledger_edit` writes review annotations into workflow state through `update_ledger_review`; it does not update `Transaction.business_classification`, `Transaction.business_pct`, or `Transaction.category_id` in the transaction catalogue. Manual entry would therefore need an explicit persisted transaction mutation path rather than relying on the current review overlay. Evidence: `src/aeat/entrypoints/cli/_ledger.py:345`, `src/aeat/entrypoints/cli/_ledger.py:356`, `src/aeat/application/workflow/_models.py:134`, `src/aeat/application/workflow/_models.py:146`, `src/aeat/domain/transactions/_service.py:73`, `src/aeat/domain/transactions/_service.py:162`.
- Direction inference already differs between reachable and retired surfaces. `aeat app ledger import` treats non-negative amounts as incoming, while the retired financial ingest path historically distinguished zero as an internal transfer. A manual-entry ADR needs to settle zero-amount and transfer semantics before exposing operator input. Evidence: `src/aeat/entrypoints/cli/_ledger.py:52`, `src/aeat/entrypoints/cli/financial/ingest.py:77`.

### Bucket event history

- Bucket event history exists but the closed event enum currently covers modelo lifecycle and profile events, not ledger transaction events. There is no `LEDGER_TRANSACTION` object type. Evidence: `src/aeat/domain/buckets/_event.py:54`, `src/aeat/domain/buckets/_event.py:77`.
- The active plan explicitly states non-modelo emitters land with owning waves, and the bucket event history ADR requires transaction events for import, classification, split, and sanitization. Manual entry would need its own event name and emission point rather than treating import or review-edit as equivalent. Evidence: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md:920`, `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md:930`, `.vault/adr/2026-05-12-cli-workflow-redesign-bucket-event-history-adr.md:123`.
- Profile actions currently emit bucket events and also append legacy workflow events. Ledger paths do neither, so adopting the profile pattern without planning the legacy/workflow-state relationship may create duplicated or divergent histories. Evidence: `src/aeat/application/profile/_actions.py:35`, `src/aeat/application/profile/_actions.py:47`, `src/aeat/application/profile/_actions.py:88`, `src/aeat/application/profile/_actions.py:99`, `src/aeat/application/profile/_actions.py:141`.

### Aggregation paths

- Renta ledger aggregation reads the global transaction catalogue and invoice catalogue from repositories. It consumes `Transaction.business_classification`, `business_pct`, and `category_id`; review annotations are not part of this path. Manual entries and manual edits must update the catalogue fields that aggregation reads, or aggregation will report missing classification/category issues and omit operator review intent. Evidence: `src/aeat/application/aggregation/_renta_ledger.py:136`, `src/aeat/application/aggregation/_renta_ledger.py:184`, `src/aeat/application/aggregation/_renta_ledger.py:208`, `src/aeat/application/aggregation/_renta_ledger.py:229`, `src/aeat/application/aggregation/_renta_ledger.py:273`.
- IVA/base aggregation is a registry binding resolver over supplied `IvaLedgerObservation` objects. The invoice helper can derive observations from invoice lines, but the researched surface did not reveal a bucket-scoped repository-backed builder that turns active ledger transactions into IVA/base observations for model calculation. Evidence: `src/aeat/domain/calculations/registry/_bindings.py:1047`, `src/aeat/domain/calculations/registry/_bindings.py:1076`, `src/aeat/domain/calculations/registry/_bindings.py:1124`, `src/aeat/domain/invoices/_iva_classification.py:210`.
- Prorrata aggregation is currently a pure function over supplied `VatOperation` values, and usage ratios persist under static namespace/key `aeat.domain.usage_ratios` and `profile`. Bucket-scoped manual ledger storage must not conflate article 101-103 VAT prorrata with app ledger usage ratios, and ratio storage itself is still not bucket-scoped in the implementation. Evidence: `src/aeat/application/aggregation/_prorrata.py:137`, `src/aeat/domain/usage_ratios/_service.py:26`, `src/aeat/domain/usage_ratios/_service.py:30`, `src/aeat/domain/usage_ratios/_service.py:79`, `src/aeat/domain/usage_ratios/_service.py:91`.

### Reachable CLI and retired-surface drift

- The root CLI mounts `config` and `app`; retired `financial` and `data` surfaces are documented in the operator contract as replacements rather than public roots. Their modules and tests still exist, so behavior can drift from canonical app-ledger semantics unless downstream work removes or strictly quarantines them. Evidence: `src/aeat/entrypoints/cli/__init__.py:235`, `src/aeat/entrypoints/cli/__init__.py:237`, `src/aeat/application/operator_surface/_contract.py:44`, `src/aeat/entrypoints/cli/financial/__init__.py:35`, `src/aeat/entrypoints/cli/data/__init__.py:20`.
- The review queue remains reachable under `aeat app review` and emits stale drill commands for retired surfaces, including `aeat financial txs classify`, `aeat financial invoices show`, and `aeat filing show`. Manual ledger entry should not inherit these command strings as operator affordances. Evidence: `src/aeat/entrypoints/cli/__init__.py:227`, `src/aeat/application/review/_adapters.py:202`, `src/aeat/application/review/_adapters.py:279`, `src/aeat/application/review/_adapters.py:372`, `src/aeat/application/review/_adapters.py:390`.
- `project_review_queue` stamps projected review rows with the active profile bucket id, but the underlying transaction and invoice adapters load global catalogues. That can make global ledger rows appear bucket-local in the operator surface before storage is actually bucket-scoped. Evidence: `src/aeat/application/review/_operator.py:61`, `src/aeat/application/review/_operator.py:135`, `src/aeat/application/review/_adapters.py:202`.

### ADR constraints for downstream work

- A downstream ADR should resolve where bucket identity lives for ledger rows: object key, namespace, payload field, or a composed storage repository. The current secure object repository is capable of encrypted storage but does not enforce domain bucket identity.
- A downstream ADR should resolve transaction identity for manual rows and cross-bucket duplicates. Current transaction ids are content-derived without bucket input, which is risky for repeated cash payments, corrections, and template-like manual entries.
- A downstream ADR should separate manual-entry persistence from review overlays. The current review edit path is useful for operator annotations but is not the source consumed by Renta aggregation.
- A downstream ADR should define event semantics for manual creation, edit/classification, split, removal, and evidence attachment, then add closed bucket event enum values before exposing commands.
- A downstream ADR should require aggregation-visible fields at creation or validation time: date, amount, currency, direction, counterparty/narrative, business classification, business percentage when mixed, spending category, IVA base/rate/amount when applicable, prorrata substrate references where applicable, proportionality/usage ratio context, evidence links, and provenance.
- A downstream plan wave should sequence bucket-scoped repository contracts before CLI command work, because the current reachable CLI can import and annotate ledger rows without proving bucket-local persistence or aggregation routing.
