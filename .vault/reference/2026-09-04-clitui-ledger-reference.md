---
tags:
  - '#reference'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:675ed06c36f462242bbd6ff5adb19fe5d5299b036f091d11115ab73687810526'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `clitui-ledger` reference: `CLI to backend capability authority census`

This reference maps the first semantic-search-led census of Ledger behavior owned by the CLI to existing or proposed frontend-neutral application homes. It is an initial denominator, not an exhaustive command-graph classification. Every implementation step must refresh affected rows against the live tree.

## Summary

### Live command denominator

The production `COMMAND_GRAPH` currently contains 91 nodes below `aeat app ledger`: 77 leaf nodes plus the executable `participation` group, for 78 invocable command endpoints. The graph projection supplies the exact path, command key, deferred handler, and result-schema identity; all 77 leaves reported an available handler and schema target. Handler import/attribute validation, schema-type resolution, registration/schema identity comparison, and generated-tree comparison found no missing, dangling, or extra leaf. The denominator comes from `src/cadrumo/entrypoints/cli/command_api.py:33`, `src/cadrumo/entrypoints/cli/command_specs.py:43`, and the command-spec families assembled at `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:24`. It replaces the historical 26-verb count in the 2026-06 interface ADR for this campaign.

The leaf families contain evidence 10, lifecycle 10, prorrata 8, foundation 6, operations 6, management 6, invoice lifecycle 5, ratios 5, evidence follow-up 4, counterparty 3, inventory 3, rules 3, bienes de inversión 2, inventory analysis 2, invoice intake 2, classification 1, and participation rebuild 1. Every Ledger leaf currently declares `TuiCapability.NOT_IMPLEMENTED`; this command metadata is distinct from the separate installed workbench components and is another reason the matrix must not conflate CLI enrollment, TUI component existence, and installed reachability.

Focused command-graph/spec tests passed 27 tests, the root Ledger help and all 13 nested group help invocations exited zero. A broader generated-reference run had 19 passing tests and one unrelated failure caused by a config-profile `archive import` versus `restore` mismatch; it does not contradict the exact Ledger tree comparison, but remains visible as pre-existing global documentation drift.

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

### Direct backend behavior gate

| Backend family | Current proof | Gate verdict |
| --- | --- | --- |
| Lifecycle archive/stash/restore/exclude/remove/reset | Direct persistence, event, evidence-detach and finalized-Modelo guard tests | Complete for existing primitives |
| Typed field edit and attachment/link primitives | Direct encrypted repository, event and back-reference tests | Complete for existing primitives; allocate/classification facades missing |
| Manual split/merge | Direct catalogue transition, lineage and refusal tests | Complete for manual operations |
| Per-file import and flat export | Real persistence plus CSV/JSONL/XLSX serialization tests | Complete for those products only; no restore proof |
| Bulk CSV classification | Direct persistence/event scale tests | Complete primitive |
| Manual create | Strong writer tests | Partial: operator-intent/Censo/jurisdiction/prorrata facade missing |
| Review/list query | Direct filter/projection tests | Partial: sort/group/page/rejection policy remains CLI-owned |
| Composite check/status/history/view/track | Granular backend readers only | Missing canonical composite use cases |
| Classification rules | Functions exist; behavior is primarily CLI-tested | Partial; dry-run engine and direct backend gate missing |
| Directory import | Per-source primitive and untested result aggregator | Missing multi-source use case and direct test |
| Drive evidence ingestion | Secure store/link primitives only | Missing joined backend workflow and behavior test |
| Evidence extraction/review/consent | CRUD/extract/confirm primitives are strong | Partial: consent and review-query composition missing |
| LLM classify/saturate/split/apply | Extensive direct primitive/review-decision tests | Partial: frontend-neutral routing/preview outcome missing |
| Invoice create/import/list | Create/import strongly tested | Partial: list proof and operator orchestration missing |
| Ratios/counterparty/prorrata | Lower-level services have direct tests | Partial: atomic operator use cases/outcomes missing |
| Bienes de inversión | Service accepts a finished record | Missing direct service test and operator-intent facade |
| Review export/Google/restore archive | No Ledger backend symbols | Missing |

Backend status is therefore not green. Direct tests establish reusable foundations, but no CLI refactor step may use primitive presence as proof that the backend gate for the corresponding operator capability is complete.

### Registry, calculation, and filing denominator

The canonical `BindingSourceKind` taxonomy and `LEDGER_BINDING_SOURCE_KINDS` define seven ledger families at `src/cadrumo/core/aggregation.py:233,512`. All seven enroll through selector registration and validator dispatch at `src/cadrumo/domain/calculations/registry/bindings.py:926,1023`, and the application calculation route validates unique total production ownership at `src/cadrumo/application/modelo/calculation_route.py:112,154`. Exact registry census found 546 declarations across the seven families.

| Binding family | Declared consumers | Production proof | Open proof or authority gap |
| --- | --- | --- | --- |
| Ledger IVA | M303/M309/M322/M353/M390 | Strong M303→M390 and deductible-evidence paths | No located live nonzero Ledger calculate proof for M309/M322/M353 |
| Ledger OSS | M369 | Strong calculate→verify/export tests | Uses issued-invoice catalogue rather than transaction catalogue; distinction must remain explicit |
| Renta direct-estimation expenses | M100 | Strong M100 and M130→M100 annual chain | Preserve invoice evidence and deduction-ratio requirements |
| Renta income | M100/M130/M131 | Strong M130/M100 and currency proof | M131 lacks located production work-calculate proof; M130 c06 uses hardcoded application projection outside honest registry targeting |
| M130 fractional-payment expenses | M130 c02 | Strong aggregate/binding and currency tests | No located explicit nonzero production-route c02 assertion |
| Impatriado income | M151 | Repository, registry-binding and currency tests | No located calculate→verify/export proof; savings base remains manual |
| IRNR income | M210 | Strong live calculate, mutation, exclusion and evidence-bundle tests | Preserve explicit M210 classification and mutual-exclusion authority |

Unmatched nonzero observations become persisted `CalculationSourceIssue` values through `src/cadrumo/domain/calculations/registry/ledger_binding_resolution.py:96` and `src/cadrumo/application/modelo/calculation_actions.py:1513`. Verification explicitly blocks the OSS `unrouted_observation`, but no general non-OSS verification gate was found at `src/cadrumo/application/modelo/verification_actions.py:1386`; this is a high-confidence filing-path gap. Ledger drift checking is otherwise strong at `src/cadrumo/application/modelo/ledger_drift_gate.py:70`, but immutable filing evidence carries currency, FX rate, and EUR value without FX source/date at `src/cadrumo/domain/modelos/ledger_filing_snapshot.py:155`.

Focused registry/calculation verification for this census passed 133 tests. Registration/dispatch tests prove enrollment, while the missing per-Modelo live paths above remain unproven rather than being inferred from generic resolver coverage.

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
