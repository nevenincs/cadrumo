# Transaction ledger domain and classifier contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-151` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 18 files (5,245 lines; 47,166 measured tokens) in `domain/transactions`. It includes raw and normalized transaction records, immutable catalogues and provenance models, gross and cash-accounting validators, date routing, Modelo 210 classification, registry-backed withholding facts, LLM prompt/response contracts, and repository ports. The concrete persistence adapter and model transports are outside this chunk.

## Product capabilities

The domain keeps a bank movement and its tax treatment in a strict `RawTransaction`/`Transaction` pair. The raw side preserves provider identity, dates, nonnegative amount magnitude, ISO currency, statement provenance, and source fields; flow direction is a separate enum. The normalized row adds business classification, income/expense tax substrate, category and invoice references, usage/prorrata axes, jurisdiction, FX, filing evidence, and lifecycle state. Immutable catalogues key rows by stable transaction IDs and validate that keys match embedded IDs. Import identity is separately designed for cross-format duplicate detection: the transaction ID follows provider/date/amount/narrative, while an import fingerprint includes date, amount, currency, direction, and normalized narrative; a coarser day-and-amount key can raise a probable-duplicate warning rather than silently treating divergent narratives as identical (identity helpers (`src/cadrumo/domain/transactions/models.py`)).

The row models preserve the reasons and actors behind classification, edits, attached evidence, lifecycle transitions, and split/merge lineage. They also encode the ledger’s tax-routing dimensions: the business share applies only to `MIXED`; IVA, recargo, IRPF, and retención facts are separate; source jurisdiction is distinct from counterparty establishment and IVA identification; and an operation’s legal devengo date is distinct from its bank settlement date. These distinctions support later model-specific aggregation without inferring statutory facts from amount sign, missing country data, or an unrelated identity field (transaction boundary (`src/cadrumo/domain/transactions/models.py`), lineage records (`src/cadrumo/domain/transactions/lineage_models.py`)).

Validation couples the tax substrate to cash where both base and IVA are present, with explicit exceptions for self-assessed IVA and supported withholding cases. Cash-accounting rows require an operation date, a nonempty payment-evidence series, base and IVA substrate, permitted direction, aggregate settlement amounts no greater than the substrate, and dates no later than the statutory fallback. Period reads can use a conservative eligible-date span that covers the ordinary ledger date plus operation, collection, and fallback dates for cash-accounting rows. A separate partition shape can report excluded rows using only transaction IDs and dates, avoiding decryption of their financial details (gross check (`src/cadrumo/domain/transactions/gross_validation.py`), cash-accounting check (`src/cadrumo/domain/transactions/cash_accounting_validation.py`), eligible date span (`src/cadrumo/domain/transactions/dates.py`), partition contract (`src/cadrumo/domain/transactions/models.py`)).

The domain resolves withholding rates and their legal references from dated governed facts, including activity-rate families and administrator rates/turnover conditions. It also resolves M210 income-code and payer-mode declarations from registry revisions, and validates model selections against those declared options. Typed IRPF taxonomy descriptors are likewise projected from governed facts. These surfaces keep statutory parameters and applicability in the registry while leaving the ledger to validate and carry operator/classifier selections (withholding facts (`src/cadrumo/domain/transactions/retencion_facts.py`), M210 declarations (`src/cadrumo/domain/transactions/m210_income_classification.py`), IRPF category projection (`src/cadrumo/domain/transactions/irpf_categories.py`)).

The LLM boundary builds prompts from closed classification and category allow-lists, optionally enriched with registry-derived Spanish category labels and IVA category hints. Responses are frozen typed records with confidence and business-share bounds; the model selects categories and may suggest split proportions, but the prompt forbids it from returning euro amounts or statutory rates. Flat classification parsing scans candidate JSON objects until one validates against both schema and allow-list. Concrete transports and the choice of whether invoice text or images may reach a provider remain caller responsibilities (prompt specification (`src/cadrumo/domain/transactions/llm.py`), flat parser (`src/cadrumo/domain/transactions/llm.py`)).

## Security and quality assessment

The model layer uses frozen records, closed enums, exact `Decimal` arithmetic, content-derived IDs, field normalization, and cross-field validators. Raw source paths are reduced to basenames; secure storage is explicitly assigned to an encrypted adapter, with keys qualified by profile bucket. The repository protocol supports ID-scoped reads and date partitions whose out-of-window payloads contain only IDs/dates, limiting sensitive data access. These are sound boundaries, but this chunk does not include the adapter implementation, encryption configuration, index completeness gate, or transaction services, so those properties must be confirmed at their concrete call sites (bucket-qualified keys (`src/cadrumo/domain/transactions/repository.py`), read-side repository port (`src/cadrumo/domain/transactions/protocols.py`), raw provenance (`src/cadrumo/domain/transactions/raw_transaction.py`)).

One local correctness gap is visible in FX validation. The field contract says `value_in_eur` is `raw.amount * fx_rate`, rounded to cents, and downstream aggregators use it for non-EUR rows. The transaction validator checks only that rate and converted value are both present or both absent, that neither is negative, that both are absent for EUR, and that rate provenance has a rate; it does not verify the conversion equation. For example, a USD row with raw amount 100, FX multiplier 2, and `value_in_eur` 1 satisfies the local pair checks. That establishes a model-boundary omission, not that a persisted or filed transaction actually reaches aggregation with such a mismatch: the importer or an application service may enforce the equation. Callers must validate the rounded conversion against the native amount and rate, and preserve the import-time rate/date/source together (FX checks (`src/cadrumo/domain/transactions/models.py`)).

The split-response boundary is more permissive than its prompt. The prompt asks for each child’s category, IVA category, and evidence citation, but the child model defaults both categories to `None` and the citation to an empty string; the parser rejects only non-null category values outside the allow-list. It also accepts child proportions whose sum is within 0.01 of one, while the prompt says they must sum to one. Thus a syntactically valid proposal can omit requested tax selections or leave a small allocation residual. A downstream workflow may already refuse such proposals, which this chunk cannot determine; callers must require complete reviewed selections and normalize or reject proportions before deriving child amounts. Unlike the flat parser, the split parser takes the first balanced JSON object and does not search later candidates, so echoed or injected JSON can select or block the parse; it remains a constrained suggestion boundary, not tax authority (split response model (`src/cadrumo/domain/transactions/llm.py`), split parser (`src/cadrumo/domain/transactions/llm.py`)).

Prompts contain transaction narratives and may inline invoice text. The evidence boundary tells the model to use documents only for classification/category selection and never copy monetary amounts, and the response parser bounds selectable values. However, embedded evidence remains untrusted prompt content, and the `LLMClassifier` contract assigns the caller responsibility for deciding whether evidence may reach a given model. Caller policy must preserve that privacy gate and treat the model’s allowed choice as an operator-review proposal; the module cannot make an allowed but mistaken selection correct (evidence prompt (`src/cadrumo/domain/transactions/llm.py`), classifier port (`src/cadrumo/domain/transactions/llm.py`)).

There is also a temporal policy to confirm for stored or historical classifications. M210’s main declaration loader selects a registry revision using `today_madrid()` and `M210IncomeClassification` has no effective-date field; the IRPF category taxonomy query similarly uses today’s date. Other code in this same area deliberately takes a transaction’s effective date or an explicit filing coordinate. Current registry selection may be intentional for new classifications, but replaying an older row under today’s catalogue can change validation meaning. Callers should either bind these fields to an explicit filing-year authority operation or document and enforce a current-vocabulary policy for historical rows (current-date M210 selection (`src/cadrumo/domain/transactions/m210_income_classification.py`), current-date IRPF taxonomy (`src/cadrumo/domain/transactions/irpf_categories.py`), explicit withholding coordinate (`src/cadrumo/domain/transactions/retencion_facts.py`)).

## Dependencies and follow-up

The domain depends on shared identity, money, locale, time, IVA and registry contracts; governed authority facts supply dated tax parameters; application services own import, classification, mutation and filing workflows; adapters own encryption and indexes; and optional LLM transports sit beyond the prompt/parser protocols. Before relying on the ledger for filings, inspect importer FX arithmetic, split review/application gates, prompt-provider privacy routing, historical M210/IRPF authority coordinates, and whether date-index completeness always falls back to a full scan without losing candidate rows. No tests are included in this chunk, and this review did not execute the application or validate jurisdictional rule outcomes against source law.

## Complete assigned-file coverage

- `src/cadrumo/domain/transactions/__init__.py`
- `src/cadrumo/domain/transactions/cash_accounting_validation.py`
- `src/cadrumo/domain/transactions/classification_rule.py`
- `src/cadrumo/domain/transactions/dates.py`
- `src/cadrumo/domain/transactions/enums.py`
- `src/cadrumo/domain/transactions/errors.py`
- `src/cadrumo/domain/transactions/gross_validation.py`
- `src/cadrumo/domain/transactions/irpf_categories.py`
- `src/cadrumo/domain/transactions/lineage_models.py`
- `src/cadrumo/domain/transactions/llm.py`
- `src/cadrumo/domain/transactions/m210_income_classification.py`
- `src/cadrumo/domain/transactions/model_tier.py`
- `src/cadrumo/domain/transactions/model_validation.py`
- `src/cadrumo/domain/transactions/models.py`
- `src/cadrumo/domain/transactions/protocols.py`
- `src/cadrumo/domain/transactions/raw_transaction.py`
- `src/cadrumo/domain/transactions/repository.py`
- `src/cadrumo/domain/transactions/retencion_facts.py`
<!-- /preserved:article -->
