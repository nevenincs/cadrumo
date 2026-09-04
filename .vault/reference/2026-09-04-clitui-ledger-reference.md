---
tags:
  - '#reference'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9a33fb3e272193010ab79d6bd609b15d2a3df9aff6457b30ae95157574e3db21'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `clitui-ledger` reference: `CLI to backend capability authority census`

This reference maps the first semantic-search-led census of Ledger behavior owned by the CLI to existing or proposed frontend-neutral application homes. It is an initial denominator, not an exhaustive command-graph classification. Every implementation step must refresh affected rows against the live tree.

## Summary

### CLI-to-backend disposition matrix

| Capability | Current CLI authority | Backend state or destination | Initial disposition |
| --- | --- | --- | --- |
| Create | `_ledger.py:212` owns state, category, Censo percentage, jurisdiction, FX, and prorrata policy | Writer at `application/ledger/actions_manual.py:113` | Backport typed creation facade |
| Allocate | `_ledger.py:624` derives classification from percentage | Generic patch only | Backport dedicated use case |
| Direct/M210 classification | `_ledger.py:450`; `_ledger_m210_classify_cli.py:25` own route/completeness | Generic update and typed facts exist | Backport discriminated commands |
| Transaction/invoice link | `_ledger.py:682` repeats prechecks | Atomic writer enforces them at `actions_manual.py:340` | Delete duplicate CLI policy |
| List/filter/sort/group/page | `_ledger_list.py:35-361` owns full query/event policy | Fixed-order primitives at `actions_manual.py:432,454` | Backport typed query/result first |
| Check/status/history/view/track | `_ledger_read_cli.py:382-1030` composes preflight, links, events, stale revisions, participation | Granular readers only | Backport composite read facades |
| Rule dry-run | `_ledger_rules_cli.py:102` repeats eligibility/first match | Live apply at `actions_classification.py:428` | Put dry-run in canonical engine |
| Per-file import | `_ledger_import_cli.py:183` parses/invokes | `actions_import.py:322` | Already backend |
| Folder import | `_ledger_import_cli.py:83,236` owns enumeration/loop | Per-source import/aggregation exist | Backport multi-source facade |
| Flat export | `_ledger_read_cli.py:661` delegates | `actions_export.py:79` | Already backend; expand separately |
| Drive evidence pull | `ledger_lifecycle_cli.py:170-414` owns fetch, MIME, secure store, link, partial success | No joined application workflow | Backport one/batch workflows over ports |
| Extraction consent | `_ledger_evidence_cli.py:235` owns eligibility/token policy | Extraction at `invoice_draft_extraction.py:128` | Backport policy command |
| Evidence review | `_ledger_evidence_review_cli.py:48-532` owns projection, blockers, filters, advisories | Atomic helpers only | Backport typed queries |
| Consent survey | `_ledger_evidence_consent_cli.py:80-153` joins adapter rows | No port-backed application reader | Backport composition |
| LLM routes | `_ledger_llm_cli.py:211-904`; `ledger_lifecycle_cli.py:755-949` own route/terminal policy | Primitives in `llm_classification.py` and `llm_review_workflow.py` | Backport discriminated workflow |
| Invoice add/import/list | `_ledger_business_invoice_cli.py:54-637` owns IVA mapping, advisories, mapper, repository list | Creation/import/lifecycle primitives exist | Backport facades; investigate mapper port |
| Ratios | `_ledger_ratios_cli.py:34-240` owns Censo joins, persistence, warnings, events | Pure helpers at `application/ledger/ratios.py:177-294` | Backport atomic workflows urgently |
| Counterparty confirmation | `_ledger_counterparty_cli.py:99-230` infers outcomes/repeats prechecks | Writer/resolver in `counterparty_establishment.py` | Return typed application outcomes |
| Prorrata | `_prorrata_register_cli.py:139-635` owns legality, precedence, blockers, persistence | Lower-level services exist | Backport end-to-end commands |
| Bienes de inversión | `_bienes_inversion_cli.py:58` constructs disposal coupling/record | Service accepts finished record | Backport typed command |
| Inventory | `_ledger_inventory_cli.py` mainly parses/redacts | `InventoryService` owns operations | Already backend |
| Payload families | `_ledger_payloads.py` and siblings redeclare facts | Partial application DTO coverage | Add canonical results, then project |

### Missing capability and reuse map

| Gap | Reusable analogue | Required proof |
| --- | --- | --- |
| Review-grade workbook | Modelo shared plan, guide/evidence facets | Open/read semantics, protection, offline/Google parity |
| Restore archive | Profile capsule | Export→restore→canonical equality, integrity, encryption |
| Google Ledger export | Optional Google adapter and Modelo renderer | One transport-neutral plan, value parity |
| Complete export provenance | Transaction facts and package manifests | Versioned schema, redaction, checksum verification |
| Evidence download | Secure byte loader and file/package export boundaries | Exact bytes/hash, safe destination, cleanup |
| Atomic evidence replace | Content-addressed store and ledger events | Atomic transition, finalized-use guard, retention policy |
| Append-only notes | Bucket event history | Immutable identity, actor/time/source, read order |
| Changed-field provenance | Invoice field provenance and bucket events | Sensitive-value policy and exact change-set round trip |
| Generic batch patch | Batch result/precondition machinery | Atomicity/partial result, idempotency, ID remap, concurrency |
| Application paging | Query DTOs and indexed repository reads | Stable snapshot/order and page contract |

### Existing backend behavior must not be rebuilt

Transaction update; attach/detach; archive/stash/restore/exclude/remove/reset; manual split/merge; per-file import and FX; CSV/JSONL/XLSX export; bulk CSV classification; live rule apply; evidence CRUD; attachment metadata; evidence extraction/confirmation/batch; invoice view/update/remove; inventory; ratio eligibility/validation; participation; and low-level LLM suggest/saturate/split/apply already have application owners. Higher-level facades may compose them, but must not copy them.

### Valid CLI boundary

CLI may own argv syntax, token/date/decimal parsing, confirmations, resolution grammar, locale activation, rendering, redaction, envelope emission, and exit-code translation. Repository selection, joins, audit events, query semantics, provider/retry policy, multi-step effects, partial-success meaning, and regulated defaults belong behind application use cases.

### Migration order for ADR consideration

1. Query/read facades: list, review, check, status, history, track, invoice list, evidence review.
2. Mutation facades: create, allocate, classification, ratios, rule dry-run.
3. Multi-system workflows: LLM routing, Drive evidence, consent, directory import.
4. Adjacent registers: invoice orchestration, prorrata, bienes de inversión.
5. Missing capability services and export products.
6. Canonical outcome DTOs, CLI reprojection, removal of direct business orchestration.

This ordering is research evidence, not execution authorization. Backend completion remains the candidate hard gate before CLI completion, and CLI completion before TUI work.
