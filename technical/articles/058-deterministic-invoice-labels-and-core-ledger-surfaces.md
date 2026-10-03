# Deterministic invoice labels and core ledger surfaces

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-058` · **Topic:** [Ledger, invoices, evidence, and registers](../topics/ledger-invoices-and-registers.md)

<!-- preserved:article -->
## Scope

This chunk covers 15 ledger application modules, 4,244 lines and 38,014 measured proxy tokens. All seven bounded pages were read. They include registry-resolved invoice prompt facts, Spanish/Catalan/English label extraction and arithmetic assembly, manual ledger-add contracts and command preparation, lifecycle mutations, invoice linking, and filtered/paged transaction listing. Static only: no invoice corpus, persistence adapter, frontend or test was executed; bundled label vocabulary is not a claim of exhaustive language coverage or legal authority.

## Deterministic invoice-label reading

The application resolves regulatory values for the extraction prompt through the caller's pinned authority operation. It enumerates IVA rates across every effective boundary overlapping a period rather than sampling one day, and derives withholding rates, no-tax categories and regime-legend phrases from their registered authorities. When no period is supplied, it uses the current civil year's annual period; the model renderer receives a typed value object rather than consulting the authorities itself. This keeps the prompt values tied to one pinned authority generation, though the prompt text and downstream extraction remain separate components. Period and authority value contract (`src/cadrumo/application/ledger/invoice_extraction_authority.py`) Boundary sweep (`src/cadrumo/application/ledger/invoice_extraction_authority.py`) Resolver (`src/cadrumo/application/ledger/invoice_extraction_authority.py`)

The deterministic text reader collects occurrences before choosing values. Its vocabulary covers Spanish, Catalan and English party headings, tax labels, invoice numbers/dates, common amount labels, and a finite set of currency codes/symbols. Party context and explicit qualifiers associate identifiers with supplier/customer; Spanish and EU-format validators reject malformed IDs, and a checksum-valid identifier from an otherwise heading-free document is assigned to the issuer only if no heading words exist and exactly one distinct identifier was observed. Names are read only next to a party heading, not inferred from an issuer letterhead. Collection and party state (`src/cadrumo/application/ledger/invoice_label_collection.py`) Tax-ID verification and role assignment (`src/cadrumo/application/ledger/invoice_label_collection.py`) Bundled vocabularies (`src/cadrumo/application/ledger/invoice_label_vocabulary.py`)

Amounts preserve their printed anchors. A single separator followed by exactly three digits is returned as two possible readings instead of choosing thousands versus decimal notation; mixed and repeated separators use explicit grouping rules. Label assembly requires consensus among repeated values, reconciles base × rate to cuota, checks per-rate breakdown sums, checks invoice total against base/cuota/recargo/suplidos, and checks withholding against the base and payable amount. When conflicting or inconsistent figures are detected, it surfaces candidate ambiguity/findings and clears dependent values instead of choosing a convenient winner. Multirate tables retain tiers; the model fill path later preserves rule-read fields and contributes only missing fields. Amount ambiguity and parsing (`src/cadrumo/application/ledger/invoice_label_value_parsing.py`) Tax-tier reconciliation (`src/cadrumo/application/ledger/invoice_label_assembly.py`) Totals and retention checks (`src/cadrumo/application/ledger/invoice_label_assembly.py`) Label-only completeness and merge (`src/cadrumo/application/ledger/invoice_label_reader.py`)

One grammar edge deserves corpus validation: in the non-table path, `_add_rated_amounts` retains only the first base or IVA amount for each rate, while repeated labels of the same kind/rate are not passed through `single_consensus` or visibly accumulated there. If the intended text grammar permits multiple separate amounts for one rate, verify these are either equivalent repeated observations or should be summed/flagged. Table rows take a different path and are retained. This is a bounded parser-coverage question, not evidence of a production misread without representative documents. Per-rate collection (`src/cadrumo/application/ledger/invoice_label_assembly.py`) Table-tier branch (`src/cadrumo/application/ledger/invoice_label_assembly.py`)

## Manual addition, lifecycle, linking, and listing

Manual add accepts a bounded hidden request, validates canonical date/decimal forms, requires a nonnegative amount magnitude and takes flow from an explicit direction. The command builder resolves categories, business share, source jurisdiction, IVA category and related facts under the pinned authority/profile. A source-jurisdiction-required condition is exposed as a correctable validation result before persistence; registry tokens are not accepted as arbitrary unvalidated strings. The result contract distinguishes successful creation from a refusal with no transaction/event effect, bounds references/messages, and projects a matching profile-bound receipt. Add request bounds (`src/cadrumo/application/ledger/ledger_add_contracts.py`) Command construction (`src/cadrumo/application/ledger/ledger_add_command.py`) Pre-write jurisdiction and registry decisions (`src/cadrumo/application/ledger/ledger_add_command.py`) Outcome invariants and result projection (`src/cadrumo/application/ledger/ledger_add_contracts.py`)

Archive, stash, restore and review exclusion share an exact-profile worker. It resolves the supplied prefix to a full current ID, binds all repositories to the active profile and authority, and enters irreversible custody before calling canonical lifecycle services. The tracked repository distinguishes a canonical refusal before any write (safe bounded refusal, effect NONE) from a validation exception after write entry (propagated rather than mislabeled as a no-op). Access adds COMMIT to whole-profile read authority; the route is CLI-only. Shared lifecycle execution (`src/cadrumo/application/ledger/lifecycle_mutation_operation.py`) Write-entry distinction and results (`src/cadrumo/application/ledger/lifecycle_mutation_operation.py`) COMMIT access (`src/cadrumo/application/ledger/lifecycle_mutation_operation.py`)

Invoice linking delegates to the canonical revision-guarded transaction/invoice/event mutation. Its closed result reports only link IDs, actor, transaction projection and review status; missing or cross-bucket invoices become typed refusals only before a writer attempt. The result projector requires the expected successful UPDATED or refused NONE receipt. Link is exposed on CLI, TUI and MCP with a reviewed, profile-bound access/disclosure policy. Link operation and failure handling (`src/cadrumo/application/ledger/link_operation.py`) Receipt-bound projection (`src/cadrumo/application/ledger/link_operation.py`) Frontend/access registration (`src/cadrumo/application/ledger/link_operation.py`)

Listing parses filters with the canonical review grammar and resolves access periods from that parsed filter rather than trusting a separate caller scope hint. The query performs review/status filters, optional group filter, stable sort, optional grouping and paging in that order; it exposes truthful total/truncation facts and tie-breaks equal sort values by canonical transaction ID. An optional exclusion reads bucket events to identify whether the latest recorded LLM decision is rejection, rather than confusing that with current review status. Result validators enforce the requested window's length and uniqueness. Request and access-derived period (`src/cadrumo/application/ledger/list_operation.py`) Query and filter order (`src/cadrumo/application/ledger/list_query.py`) Stable sorting and model-decision history (`src/cadrumo/application/ledger/list_query.py`) Window invariants (`src/cadrumo/application/ledger/list_operation.py`)

## Assessment and follow-up

These modules put domain decisions in reusable application services: authority values are pinned, label parsing is deterministic and anchored, arithmetic disagreements stay visible, lifecycle operations track writer entry, and list/link surfaces bind results to exact profiles and terminal effects. The main quality questions are the same-rate repeated-label semantics above, actual vocabulary/format coverage on representative invoices, and whether deployed adapters preserve the expected writer and authority boundaries. No tests were reviewed or run. These contracts do not establish current legal correctness, parser recall, or runtime persistence behavior.

## Complete assigned-file coverage

- invoice_extraction_authority.py (300 lines) (`src/cadrumo/application/ledger/invoice_extraction_authority.py`) — all lines read.
- invoice_label_assembly.py (495 lines) (`src/cadrumo/application/ledger/invoice_label_assembly.py`) — all lines read.
- invoice_label_collection.py (204 lines) (`src/cadrumo/application/ledger/invoice_label_collection.py`) — all lines read.
- invoice_label_models.py (114 lines) (`src/cadrumo/application/ledger/invoice_label_models.py`) — all lines read.
- invoice_label_reader.py (255 lines) (`src/cadrumo/application/ledger/invoice_label_reader.py`) — all lines read.
- invoice_label_table.py (73 lines) (`src/cadrumo/application/ledger/invoice_label_table.py`) — all lines read.
- invoice_label_value_parsing.py (266 lines) (`src/cadrumo/application/ledger/invoice_label_value_parsing.py`) — all lines read.
- invoice_label_vocabulary.py (188 lines) (`src/cadrumo/application/ledger/invoice_label_vocabulary.py`) — all lines read.
- ledger_add_command.py (292 lines) (`src/cadrumo/application/ledger/ledger_add_command.py`) — all lines read.
- ledger_add_contracts.py (238 lines) (`src/cadrumo/application/ledger/ledger_add_contracts.py`) — all lines read.
- ledger_add_results.py (125 lines) (`src/cadrumo/application/ledger/ledger_add_results.py`) — all lines read.
- lifecycle_mutation_operation.py (776 lines) (`src/cadrumo/application/ledger/lifecycle_mutation_operation.py`) — all lines read.
- link_operation.py (331 lines) (`src/cadrumo/application/ledger/link_operation.py`) — all lines read.
- list_operation.py (197 lines) (`src/cadrumo/application/ledger/list_operation.py`) — all lines read.
- list_query.py (390 lines) (`src/cadrumo/application/ledger/list_query.py`) — all lines read.
<!-- /preserved:article -->
