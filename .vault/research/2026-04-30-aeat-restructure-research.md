---
tags:
  - '#research'
  - '#aeat-restructure'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-aeat-restructure-adr]]'
---



# `aeat-restructure` research: domain-boundary audit of `src/aeat/`

Rolling, human-driven, module-by-module audit of `src/aeat/`. Each module is
measured against the three conceptual domains the project is meant to honour:

- **financial-input** — incoming financial data ingestion (bank feeds,
  uploads, parsers, normalisers — anything that moves outside data *into* the
  system).
- **local-state** — internal persistence and state management (storage,
  manifests, caches, run history, configuration on disk — anything that
  represents the system's *own* memory).
- **aeat-remote** — interaction with the AEAT portal and any external AEAT
  surface (HTTP clients, transport, auth providers, response parsing,
  certificate handling — anything reaching the *outside world* on the AEAT
  side).

The current flat module structure does not visibly reflect those domains.
Modules are suspected to straddle boundaries (e.g. a single module ingesting
financial data, persisting it, and shipping it to AEAT). This document
inventories the offenders and clean cases so a follow-up ADR can propose a
restructure.

This is a research document, not a decision. It feeds the
`aeat-restructure` ADR.

## Domain map (initial assignment) and destinations

Forced-fit assignment of every Python module under `src/aeat/` into one of
the three project domains, plus a connector bucket for modules that bridge
two or more domains, plus two honesty buckets for modules that do not fit
(cross-cutting infrastructure; empty placeholders).

The assignment is functionality-based and may be wrong in places —
correcting these calls is the point of the per-module audit that follows.
Each row carries a `confidence` flag (`high` / `med` / `low`) so we know
where to look first.

The `Destination` column maps each module onto the proposed restructure
captured in the parallel ADR. The `Rename` column is non-empty only when
the module itself is renamed (not just relocated). Flags are explained
below.

### Flag legend

- `[MONO]` — module ≥ 950 LOC; internal fracture / restructure required
  during or before the move. The audit must propose a split.
- `[CONFLATE]` — module conflates ≥ 2 domain responsibilities under one
  surface; needs split during or before the move.
- `[CONFLATE?]` — suspected conflation, unverified by deep audit.
- `[CORE-LEAK]` — module nests reusable foundational code that should
  bubble up into `core/` rather than stay buried.
- `[CORE-LEAK?]` — suspected, unverified.

The audit must convert every `?` to either confirmed or cleared.

### Heat map

LOC counts exclude colocated `test_*.py` files. `[MONO]` count counts
modules at or above the 950-LOC threshold.

| Bucket | Modules | LOC (~) | `[MONO]` | Largest tenants |
| --- | --- | --- | --- | --- |
| Financial input | 7 | 5,200 | 2 | `sanitizer` (1,774) `[MONO]`, `justificante` (1,292) `[MONO]`, `declaracion` (818) |
| Local state | 15 | ~23,200 (corrected) | 9 | `storage` (7,090 source, **corrected from 11,972** — original inventory's regex missed `_test_*.py` tests; audit 4) `[MONO]` `[CONFLATE]`, `rental` (2,330) `[MONO]` (audit-discovered), `observability` (1,802) `[MONO]`, `schema` (1,774) `[MONO]`, `llm` (1,711) `[MONO]` |
| Remote AEAT | 3 | 4,500 | 3 | `sede` (2,024) `[MONO]`, `submission` (1,264) `[MONO]`, `browser` (1,196) `[MONO]` |
| Connectors | 8 | 18,900 | 6 | `cli` (7,625) `[MONO]`, `auth` (4,782) `[MONO]`, `filing` (4,465) `[MONO]`, `workflow` (2,028) `[MONO]` |
| Cross-cutting infra | 9 | 4,800 | 1 | `errors` (2,945) `[MONO]` `[CONFLATE]` (audit-confirmed), `config.py` (851), `logging.py` (295) |
| Empty placeholders | 4 | 0 | 0 | `corpus`, `history`, `inbox`, `status` |
| **Total** | **39 non-empty** | **~61,500** | **21** | over half the codebase is at or over the 950-LOC threshold |

Observations the user should weigh before picking an audit target:

- **20 of 38 non-empty modules are at or over 950 LOC.** Internal
  fracturing is the rule, not the exception, in this codebase.
- **`storage` (~12k LOC) is the dominant outlier.** It is roughly half
  the local-state bucket on its own.
- **All 3 remote-AEAT modules are monolithic** — small bucket, large
  modules. Internal split candidates each.
- **All connectors except `review` and `verification` are monolithic.**
  This is the heaviest concentration of structural debt.
- **`submission/` is in scope for rename to `export/`** — legal-liability
  framing. Read-only preflight + dry-run preserved.
- **Four empty placeholders** are flagged for `DELETE` unless audit
  finds reason to keep.

### Table 1 — incoming financial data → `adapters/inbound/`

Modules whose primary function is ingesting outside data into the system.

| Module | Functionality (1 line) | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `financial` | Track-B Transaction Data Pipeline (TDP): bank-import providers + transactions + invoices + categories + VAT + aggregation + usage-ratios + attachments — heavily 4-axis conflated across 8 sub-packages. | **11,250** (audit 19 corrected; was 193) | high | **8-destination split per audit 20**: `providers/` → `adapters/inbound/financial/providers/`; `transactions/` → 4-way split; `invoices/` → 3-way split; `categories/` → `domain/categories/`; `vat/` → `domain/vat/` (consider top-level promotion); `aggregation/` → `application/aggregation/`; `usage_ratios/` → 2-way split; `attachments/` → 3-way split. | top-level `_raw_transaction` and `_decimal` retain | `[MONO]` (CONFIRMED — second-largest module). `[CONFLATE]` HEAVILY CONFIRMED. CLI upward-inversion FALSE POSITIVE — corrected. 2 NEW dead-code candidates. |
| `_pdf_import` | Shared primitives for PDF-import families (regex, scrub, errors). | 488 | high | `adapters/inbound/pdf/` | `pdf/` | — |
| `borrador` | Casilla-complete Modelo 100 (IRPF / Renta) PDF parser. | 399 | high | `adapters/inbound/borrador/` | — | — |
| `declaracion` | Casilla-complete declaración PDF parser. | 818 | high | `adapters/inbound/declaracion/` | — | — |
| `justificante` | Parser + encrypted repository + remote AEAT CSV-verify (Playwright browser call to Sede electrónica). | 1,292 | high | **3-destination split per audit 11**: `adapters/inbound/justificante/` (parser pipeline) + `domain/justificante/` (domain record + repository per LAYERING TENSION) + **`adapters/outbound/aeat/verify/`** (NEW sub-cluster — `_verify.py` is a remote AEAT connector, NOT inbound). | — | `[MONO]` (CONFIRMED) `[CONFLATE?]` **CONFIRMED with 3-way split** by audit 11. NEW dead-code candidates: `PYMUPDF` backend (raises on use), `migrate_legacy_justificantes_to_repository`. |
| `identity` | Spanish identity-document parsing + validation (NIF/NIE). User-supplied data. | 212 | med | `adapters/inbound/identity/` | — | — |
| `sanitizer` | PDF sanitisation pipeline (fixture-prep tool): refuse-if-signed → strip dynamic surfaces → token-replace cleartext → scrub metadata → save deterministically. Pure transformation. | 1,774 | high | `adapters/inbound/sanitizer/` (audit 8 recommendation; pragmatic — alternatives: `tools/sanitizer/` or `core/sanitizer/`) | — | `[MONO]` (CONFIRMED — high internal cohesion, no internal split needed) `[CONFLATE?]` **CLEARED** by audit 8 (false alarm — CLI was the import junction, sanitizer source has zero `justificante` imports and only one pure-utility `financial` import). NO dead code. |

### Table 2 — local state → split between `domain/` and `adapters/persistence/`

The "local state" bucket bifurcates in the new layout. Catalogues +
computation engines + profile move to `domain/`. Persistence + run-trace
+ external-service caches move to `adapters/persistence/`. The
`Destination` column is the split decision per module.

| Module | Functionality (1 line) | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `storage` | Governed-persistence substrate: SQL + at-rest encryption + master-key lifecycle + governance policy + secret materialisation (5 distinct cluster responsibilities). | **7,090** (corrected from 11,972 — see audit 4) | high | **7 sub-modules** under `adapters/persistence/storage/` (`sql/`, `crypto/`, `master_key/`, `envelope/`, `blob_store/`, `secret_store/`, `_rotation.py`) **+ 5 promotions** to `core/` (`classification/`, `redaction/`, `corpus_manifest/`, `locks.py`, `path_safety.py`) | — | `[MONO]` (CONFIRMED) `[CONFLATE]` (CONFIRMED — 5-cluster + 1-rotation breakdown by audit 4) `[CORE-LEAK]` (PARTIALLY CONFIRMED — `_path_safety` + `_lock` confirmed; `_crypto` + `_master_key` STAY in storage; NEW CORE-LEAKs: `_classification`, `_redaction`, `_corpus_manifest`) |
| `observability` | Cross-cutting run-trace instrumentation: contextvar-scoped run_id + JSONL sink + persisted traces + corpus/db/cert fingerprinting + CLI replay. | 1,802 (1,657 source) | high | **`core/observability/`** (audit 15 — moved from `adapters/persistence/observability/`; cross-cutting infra, not adapter — analogous to opentelemetry/structlog placement) | — | `[MONO]` (CONFIRMED). 3 NEW dead-code candidates. `_replay.py` → `..cli.app` coupling structural smell. |
| `schema` | BOE-PDF extraction pipeline + typed pydantic IR + runtime evaluation. Two distinct concerns at clean file boundary, unidirectional dep (extraction → IR). | 1,774 | high | **2-destination split per audit 9**: `adapters/inbound/schema/` (extraction: `_fetch.py` + `_boe_extractor.py`, ~860 LOC) + `domain/schema/` (IR + cache + errors + protocols, ~700 LOC) | — | `[MONO]` (CONFIRMED) `[CONFLATE?]` **CONFIRMED** by audit 9, 2026-04-30 — concrete split design produced. NEW dead-code candidates: `Extractor` Protocol (no production callers), 3 reserved SchemaSource enum slots, `_BOE_REF_RE` duplication. |
| `llm` | Async LLM gateway: 4 provider adapters + content-addressed cache + JSONL usage log + translation use case. | 1,615 (audit 7 corrected from 1,711) | high | **`adapters/outbound/llm/`** (audit 7 — moved from persistence to outbound; cold-review R1 #3 upheld). Internal 4-axis structure (outbound + persistence + application + domain) kept cohesive within. | — | `[MONO]` (CONFIRMED) `[CONFLATE?]` partially confirmed — 4-axis conflation real but cohesion holds (single consumer binds to all). 3 new dead-code candidates fed to workstream (`_FakeAdapter` in `__all__`, `ProviderRequest` in `__all__`, stale `_i18n_compat.pyc`). |
| `formulas` | Per-modelo calculation formula engine, ledger, registry. | 1,431 | high | `domain/formulas/` | — | `[MONO]` |
| `manuals` | AEAT *Manual práctico* corpus loader and verification. | 1,371 | high | `domain/manuals/` | — | `[MONO]` |
| `models` | Authoritative AEAT modelo catalogue + metadata + citations. | 1,219 | high | `domain/modelos/` | `modelos/` | `[MONO]` |
| `deadlines` | Filing-deadline computation engine. | 997 | high | `domain/deadlines/` | — | `[MONO]` |
| `portals` | AEAT portal catalogue (URLs, auth methods, stability flags). | 944 | med | `domain/portals/` | — | — |
| `casillas` | Curated AEAT casilla catalogues. | 780 | high | `domain/casillas/` | — | — |
| `normatives` | Spanish tax normatives corpus. | 656 | high | `domain/normatives/` | — | — |
| `testing` | Synthetic filing-history fixtures loader. | 591 | high | `domain/testing/` | — | (open: may move to `core/testing/` if test fixtures are deemed cross-cutting) |
| `profile` | Kent's tax-residence profile (CCAA, foral regime, residence changes). | 365 | high | `domain/profile/` | — | — |
| `i18n` | Translation infrastructure for trilingual (es/en/hu) output. | 169 | high | `core/i18n/` | — | (relocated out of state cluster — translation is cross-cutting) |
| `rental` | Per-property rental register computing M100 Anexo C casillas (0061/0066/0072/0078/0085) under Ley 12/2023 four-tier reducción + LIRPF art. 23.1.f amortisation ledger. Tracks issue #454. **Audit 2 (2026-04-30)**. | 2,330 | high | `domain/rental/` | — | `[MONO]` (size only — internal file structure is already at single-responsibility granularity, no split needed). `[CONFLATE?]` and `[ZERO-IMPORTERS?]` flags **CLEARED** by audit. |

### Table 3 — remote AEAT → `adapters/outbound/`

Direct interaction with the AEAT portal / external AEAT surface.

| Module | Functionality (1 line) | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `sede` | Read-only Playwright driver: 3 sub-surfaces (Expedientes walker + Declarations register + Notifications inbox). | 2,024 | high | `adapters/outbound/aeat/adapters/outbound/aeat/sede/` (stays — single dest, audit 12 — internal sub-packaging optional) | — | `[MONO]` (CONFIRMED). 1 new dead-code candidate (`fetch_justificante_pdf` raises NotImplementedError). |
| `submission` | Two completely independent halves: (A) submission-lifecycle domain (engine + preflight + models + repository) (B) fichero-BOE format library (`_formats/`). | 1,264 (Half A ~700 + Half B ~3,400 — `_formats/` is large) | high | **2-destination split per audit 16**: `adapters/outbound/aeat/export/` (`_formats/` — the actual export functionality) + `domain/submission/` (Half A — lifecycle + preflight + repository). | `export/` for `_formats`; `submission/` (domain) stays | `[MONO]` (CONFIRMED). 4 NEW dead-code candidates (`_submitters/` tombstone directory, `browser_trace_path` field, `IN_PROGRESS`/`PENDING` enum tombstones, possibly the 2025 modelo stubs). `LiveSubmitForbiddenError` relocation (audit 3) NOT yet done. |
| `browser` | Playwright adapter: session/evasion/profile + site-health classification + smoke-health binary. | 1,196 | high | `adapters/outbound/aeat/adapters/outbound/aeat/browser/` (stays — single dest). Audit 17 recommends MOVING `SiteHealthAlert` to `workflow._models` to eliminate circular-dep + model_rebuild ritual. | — | `[MONO]` (CONFIRMED). 3 NEW dead-code candidates (`EvasionStrategy` exported but no external consumers, possibly `health.py` orphan, dead `evaluate_response` re-export). |

### Table 4 — connectors → `application/` (with `cli` routed to `entrypoints/`)

These are the modules to watch. Each was chosen for the connector bucket
because its import surface or stated purpose spans multiple domains.

| Module | Bridges | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `cli` | inbound + state + remote + infra (pure dispatch / presentation layer) | ~16,000 (flat ~4,100 + nested ~10,800; corrected from earlier 7,625) | high | `entrypoints/cli/` with internal reorganisation per audit 6: new `cli/setup/`, `cli/doctor/`, `cli/security/`, `cli/gsuite/` sub-dirs; flat-level financial files migrate INTO existing `cli/financial/`; `_live.py` moves OUT of cli to `tests/_helpers/`. | — | `[MONO]` `[CONFLATE]` (both **CONFIRMED** by audit 6, 2026-04-30; full reorganisation plan — see "Modules audited") `[OUTLIER]`: `doctor.py` (1,140 LOC) needs its own internal split. `[MISPLACEMENT]`: `_live.py` is cross-package test fixture, not CLI. `[INCONSISTENCY]`: 3 financial files at flat level despite `cli/financial/` sub-dir existing. `[INCONSISTENCY]`: test files split between `_test_*.py` and `test_*.py` at flat level — project-wide cleanup. |
| `auth` | 4 conflated concerns (Google + AEAT + gate-policy + dead secret-storage) | 4,782 | high | **5-destination split** (per audit 3): `adapters/outbound/google/` (Google) + `adapters/outbound/aeat/adapters/outbound/aeat/auth/` (concrete AEAT providers) + `application/auth/` (slim — provider-selection only) + `core/access_gate/` (gate + policy errors) + `core/file_permissions.py` (OS primitive). Plus `_secret_adapters.py` deletion candidate. | — | `[MONO]` `[CONFLATE]` (both **CONFIRMED** by audit 3, 2026-04-30; full split design — see "Modules audited") `[CORE-LEAK]` upgraded: `_file_permissions.py` (confirmed) + Browser Playwright protocols (new finding). `[DEAD]`: `_secret_adapters.py` no production callers. |
| `filing` | inbound (justificante) + state (storage, formulas, models, deadlines) + remote (submission, sync) — **plus a misplaced sync-domain repository** | 4,465 | high | **2-domain split + 1 out-of-package move** (per audit 5): `domain/filing/` (records, protocols, builders, validator, reconciliation, repositories — pending layering decision) + `application/filing/` (orchestration, use cases, glue) + `_history_repository.py` MOVES to `aeat.application.sync`. | — | `[MONO]` `[CONFLATE]` (both **CONFIRMED** by audit 5, 2026-04-30 — full split design see "Modules audited") `[MISPLACEMENT]`: `_history_repository.py` persists sync-domain type. `[DEAD]`: 4 candidates (FilingHistoryRepository ext usage, utc_now, duplicate default_schema_provider, 3 migrate helpers). `[LAYERING-TENSION]`: per-domain repositories conflict with ADR's `domain/`-must-not-import-`adapters/` rule — see "Open questions / themes". |
| `workflow` | Single linear preflight orchestrator (sync → next-obligation → inbox → already-filed-probe → build-draft → validate → preflight). Permanently read-only. | 2,028 | high | `application/workflow/` (single — already axis-clean internally) | — | `[MONO]` (CONFIRMED) `[CONFLATE]` **DOWNGRADED to MONO only** by audit 10, 2026-04-30 — the high in-degree is structural (composition root), not multiple use cases. 3 dead-code candidates. Forward-ref circular dep with browser._site_health flagged. |
| `sync` | Live-to-local cross-validation engine: wire schemas + divergence taxonomy + classifier + dispatcher + strategies + repository. 3 internal architectural layers. | 1,499 | high | **2-destination split per audit 13**: `domain/sync/` (taxonomy + classifier ~425 LOC pure domain) + `application/sync/` (everything else). | — | `[MONO]` (CONFIRMED). NOT CONFLATE (single use case, 3 layers). 4 NEW dead-code candidates (4 hollow Protocol stubs on LiveSyncRunner that are stored but never invoked). |
| `setup` | First-run onboarding — collects identity + certificate + prefs, writes env file + encrypted AutonomoProfile, verifies result. | 1,312 | high | `application/setup/` (stays — single use case, clean internal axis split per audit 14) | — | `[MONO]` (CONFIRMED). 3 NEW dead-code candidates (SetupOutcome.SKIPPED, ABORTED_BY_USER, vestigial i18n helper). |
| `review` | inbound (financial) + state (storage) + remote (via sync) | 844 | high | `application/review/` | — | — |
| `verification` | inbound (declaracion) + state (formulas, models) | 361 | high | `application/verification/` | — | (clean small connector — likely a model for what other connectors should look like) |

### Table 5 — cross-cutting infrastructure → `core/` (with `mcp` routed to `entrypoints/`)

Not a domain. These modules are imported by everything and have no
particular allegiance.

| Module | Functionality (1 line) | LOC | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- |
| `errors` | Error identity + rendering pipeline + centralised exception-code catalogue (with 13 of 31 public symbols carrying domain knowledge — see audit 1). | 2,945 | `core/errors/` (registry + rendering + base + firewall) **+ splits into 3 domain `_errors.py` modules** (per audit 1) | — | `[MONO]` `[CONFLATE]` (both **CONFIRMED** by audit 1, 2026-04-30; split design produced — see "Modules audited" section) |
| `config.py` | Settings dataclass; env-var declarations. | 851 | `core/config.py` | — | `[CORE-LEAK?: imports `auth` and `justificante` — possible domain leakage into infra layer]` |
| `logging.py` | Logging configuration, structured logger factory. | 295 | `core/logging.py` | — | — |
| `mcp` | Project-owned MCP launch helpers (Google Workspace). | 286 | `entrypoints/mcp/` | — | (re-classified from infra — MCP is a primary-adapter entrypoint, sibling to CLI) |
| `_json_contract.py` | JSON contract helpers shared across CLI surfaces. | 165 | `core/json_contract.py` | `json_contract.py` | (drop underscore prefix) |
| `env_io.py` | Read/write `.env` files for setup wizard. | 155 | `core/env_io.py` | — | — |
| `_paths.py` | Shared filesystem-path helpers. | 67 | `core/paths.py` | `paths.py` | (drop underscore prefix) |
| `_click_context.py` | CLI/Click context helpers. | 45 | `core/click_context.py` | `click_context.py` | (drop underscore prefix) |
| `__init__.py` | Package init; `__version__`. | 21 | `aeat/__init__.py` | — | — |

### Table 6 — empty placeholders → DELETE

Subpackage directories with no `.py` content. Deletion is the default
outcome unless the audit finds reason to keep.

| Module | Hint at intent | Destination |
| --- | --- | --- |
| `corpus` | Likely shared root for corpus loaders that already live under `manuals` / `normatives` / `casillas`. | DELETE |
| `history` | Likely intended for filing-history surface; `filing/_history_repository.py` shows the home was changed. | DELETE |
| `inbox` | Likely intended for an incoming-document inbox surface; the CLI surface exists as a subcommand only. | DELETE |
| `status` | Likely intended for status surface; the CLI surface exists as a subcommand only. | DELETE |

### Open ambiguities to resolve during audit

These are the calls made under low confidence; resolving them is part of
the audit work. Each ambiguity is also flagged on its row above.

- **`sanitizer`** — **RESOLVED by audit 8 (2026-04-30)**.
  `[CONFLATE?]` flag was a FALSE ALARM (caused by tracing CLI-layer
  imports, not sanitizer source). Sanitizer source has zero
  `justificante` imports and only one pure-utility `financial`
  import (`validate_spanish_tax_id`). Destination:
  `adapters/inbound/sanitizer/` (audit recommendation; pragmatic
  alignment with `_pdf_import` → `pdf/`). Alternatives flagged for
  user judgment: `tools/sanitizer/` (architecturally honest) or
  `core/sanitizer/` (cross-cutting tooling). See "Modules audited"
  for the full audit and methodology lesson.
- **`llm`** — **RESOLVED by audit 7 (2026-04-30)**. Moves from
  `adapters/persistence/llm/` (initial proposal) to
  `adapters/outbound/llm/`. Cold-review R1 #3 upheld. Internal
  4-axis structure (outbound + persistence + application +
  domain-prompt) preserved cohesively within `llm/` because the
  only consumer (CLI) binds to all axes together. See "Modules
  audited" for the full audit + 3 dead-code candidates + 5 hidden-
  coupling findings.
- **`schema`** — **RESOLVED by audit 9 (2026-04-30)**. Splits into
  2 destinations: `adapters/inbound/schema/` (extraction: `_fetch.py`
  + `_boe_extractor.py`, ~860 LOC) + `domain/schema/` (IR + cache
  + errors + protocols, ~700 LOC). Extraction is build-time only
  (single CLI consumer); IR is runtime. Unidirectional dependency
  (extraction → IR) makes the split mechanically simple. See
  "Modules audited" for the full split design and 4 new dead-code
  candidates.
- **`portals`** — `domain/portals/` (current proposed) or `adapters/`-
  adjacent metadata? Same question: does it ever drive live behaviour?
- **`identity`** — `adapters/inbound/identity/` (current proposed) or
  `domain/profile/identity/` (profile-adjacent)?
- **`auth`** — **RESOLVED by audit 3 (2026-04-30)**. Splits into 5
  destinations: `adapters/outbound/google/` (Google auth + service
  builders), `adapters/outbound/aeat/adapters/outbound/aeat/auth/` (concrete AEAT providers
  including cert + Cl@ve Móvil + provider catalogue), `application/auth/`
  (slim — `select_provider` factory + provider-agnostic types only),
  `core/access_gate/` (`AeatAccessGate` + policy errors including the
  relocated `LiveSubmitForbiddenError` from `submission/`), and
  `core/file_permissions.py` (the chmod/icacls primitive). Plus
  `_secret_adapters.py` is a delete candidate (no production callers).
  See "Modules audited" for the full split design and 5 gate
  preservation invariants.
- **`storage`** — **RESOLVED by audit 4 (2026-04-30)**. Splits into
  7 internal sub-modules (`sql/`, `crypto/`, `master_key/`,
  `envelope/`, `blob_store/`, `secret_store/`, `_rotation.py`) under
  `adapters/persistence/storage/` PLUS 5 CORE-LEAK promotions to
  `core/` (`classification/`, `redaction/`, `corpus_manifest/`,
  `locks.py`, `path_safety.py`). The encrypted-record contract
  (10-symbol bundle imported by every per-domain repository) is
  preserved via hard-cutover: all callers updated to new canonical paths in the Step 7 keystone PR. Per-sub-module
  deep audits follow. See "Modules audited" for the full split
  design and 3 boundary-violation findings (NIF canary cross-domain
  leak, rotation private-helper coupling, fsync_parent_dir
  separation).
- **`errors`** — **RESOLVED by audit 1 (2026-04-30)**. Splits into 5
  destinations: pure-infra rendering machinery + base class +
  firewall types + alias notices stay in `core/errors/`; 11 domain-
  specific exception classes redistribute (8 → `domain/formulas/`, 1
  → `entrypoints/mcp/`, 2 → `domain/testing/`). All callers updated to the new canonical paths in the Step 7 keystone PR. See "Modules
  audited" for the full split design.
- **`config.py` imports `auth` + `justificante`** — possible domain
  leakage into the infra layer; verify whether settings genuinely need
  domain types or whether this is a layering violation.
- **`testing` location** — `domain/testing/` (current proposed) or
  `core/testing/` (cross-cutting fixture root)? Decide during audit.
- **`financial` rename** — `adapters/inbound/financial/` (current
  proposed) or `adapters/inbound/transactions/` (Track-B clarity)?
  Decide during audit.
- **Empty placeholders** — proposed `DELETE`. Confirm during audit.

## Per-module audit schema

Each audited module gets one section using this schema. The audit is
**functionality-first, not shape-first**: the primary work is
understanding what the code actually DOES (per-file role, per-symbol
behaviour, data flow, hidden coupling), not just LOC and import
graphs. Shape data confirms or contradicts what the functional
audit reveals.

### Required sections

- **Module**: dotted path (e.g. `aeat.core.errors`).
- **Functional one-liner**: what does this module fundamentally do for
  Kent? Stated in plain English without referring to its current
  shape (e.g. "exposes a registry of every error code the system can
  raise so callers can format human-readable messages and CLI exit
  codes can map deterministically").
- **Per-file functional inventory**: for each source file, a 1–2
  sentence description of WHAT it does (not what it contains) and
  what it exports. Include a verdict per file: `pure-infra` /
  `domain-knowledge` / `mixed` / `dead`.
- **Per-symbol classification** (top-level public surface only):
  for every class / function / constant exported, classify as
  `pure-infra` (would be in `core/` of any project),
  `domain-{name}` (carries knowledge specific to a project domain
  like `submission`, `casillas`, `formulas`), `glue` (wires other
  symbols together), or `dead` (unused). The audit answers: how
  much of this module is actually domain-specific code masquerading
  as infrastructure?
- **Data flow**: 2–4 sentences describing how data moves through the
  module. What comes in, what transformations happen, what goes
  out. Identify whether the module is stateless, holds state, or
  bridges between layers.
- **Inventory (shape — confirmation, not primary)**: file count,
  total LOC, public symbols.
- **Imports IN**: who depends on this module (callers). Note any
  imports that consume only a *subset* of the public surface — those
  are split signals.
- **Imports OUT**: what this module depends on. Flag cross-domain
  imports.
- **Hidden coupling**: pairs of files / classes that look independent
  but share state, threading assumptions, ordering constraints, or
  test-fixture dependencies. Hidden coupling determines fracture
  lines more than file boundaries do.
- **Domain mapping**: which of `inbound` / `domain-model` /
  `persistence` / `outbound` / `application` / `core` does each
  per-symbol classification group belong to? A single module can
  legitimately export symbols belonging to multiple destinations —
  that IS the conflation we are looking for.
- **Destination validation**: confirm or revise the destination in
  the heat-map row. If the module conflates, propose a multi-
  destination split.
- **Flag resolution**: for every `[MONO]` / `[CONFLATE]` /
  `[CONFLATE?]` / `[CORE-LEAK]` / `[CORE-LEAK?]` flag, mark
  confirmed, cleared, or upgraded (`?` → confirmed). Each `?` must
  reach yes/no.
- **Boundary violations**: concrete cross-domain wiring observed at
  the function / class / call-site level.
- **Internal split design** (REQUIRED for `[MONO]` modules):
  proposed sub-modules with their public surface and the FUNCTIONAL
  reason each sub-module is its own unit (not "files that fit
  together by size" — "responsibilities that belong together"). For
  every sub-module: name, fracture line, destination, inherited or
  upgraded flags.
- **Public-API contract impact**: every public symbol consumed
  outside this module — name the consumer and the symbol. Map each
  to: preserved (re-export shim), renamed-with-shim, broken (semver
  bump). Feeds the ADR public-surface table.
- **Naming clarity**: at module name AND symbol-name level. Does
  the module name telegraph its domain? Are public symbol names
  clear in their new home (e.g. a class moved from `errors` to
  `domain/casillas/` may need its prefix changed)?
- **Dead code candidates**: symbols with no callers in source AND no
  test coverage that exercises them as a public-API contract.
- **Open questions surfaced**: any issue that the audit cannot
  resolve without input from another module's audit or the user
  (e.g. "this exception is raised by `submission` and consumed by
  `cli`, but I cannot tell from this module alone whether the
  consumer cares about its identity or only its message").
- **Verdict**: one of `clean` (single-destination, well-named,
  not MONO), `straddling-N` (exports symbols belonging to N
  different destinations — split required, with split design),
  `misplaced` (single-destination but currently in the wrong place),
  `dead` (no callers; deletion candidate), `splits-into-N` (MONO
  with internal split design produced). One-line rationale.

### Why functionality-first

A shape-first audit can tell us `errors/` has 2,945 LOC across 2
files, exports 60 classes, and is imported by 30 modules. It cannot
tell us whether one of those classes is really a `submission`-
specific exception that should ride home when `submission` becomes
`adapters/outbound/export/`. The functional audit answers questions
the shape audit cannot.

## Test-marker realignment (proposed)

Source-of-truth for the marker decision is the parallel ADR. This is a
quick reference for use during per-module audit.

| Old marker | New marker | New home (package) |
| --- | --- | --- |
| `domain_financial_input` | `domain_inbound` | `adapters.inbound.*` |
| `domain_local_state` | `domain_model` (catalogues + computation + profile) | `domain.*` |
| `domain_local_state` | `domain_persistence` (storage + observability + llm) | `adapters.persistence.*` |
| `domain_aeat_remote` | `domain_outbound` | `adapters.outbound.*` |
| `domain_submission` | folded under `domain_outbound` (or sub-marker `domain_export`) | `adapters.outbound.export.*` |
| `domain_mediation` | `domain_application` | `application.*` |
| `domain_infra` | `domain_core` | `core.*` |

Marker rename ships in lockstep with the package move (no in-flight
state where marker name and package name disagree).

## Monolithic split planning

Every `[MONO]` module produces an internal split design as part of its
audit. Output template per module:

- **Current shape**: file list with LOC, current public surface (top-
  level exports).
- **Proposed sub-modules**: name, scope, public surface, internal
  imports.
- **Fracture lines**: which existing files / classes / functions stay
  together, which separate. Justify by cohesion (single responsibility,
  shared state, common dependency).
- **Destination per sub-module**: package path under the new layout.
  Most sub-modules inherit the parent's bucket; `[CORE-LEAK]` findings
  bubble up to `core/`.
- **Public-API impact**: which renames / new module paths consumers
  must adjust to.

Highest-priority targets (per heat map): `storage`, `cli`, `auth`,
`filing`, `errors`, `workflow`, `sede`, `submission` (export), `sync`,
`setup`, `observability`, `schema`, `llm`, `formulas`, `manuals`,
`models`, `deadlines`, `sanitizer`, `justificante`, `browser`.

## Vault-corpus contradictions

Existing `.vault/` documents that reference old module names, old test
markers, or pre-restructure path conventions are slated for supersession
in lockstep with rollout.

A subagent scan produces a contradiction list per document. Each entry
is then classified by the primary contributor:

- **Mark superseded**: document is superseded by this restructure ADR
  or a downstream artefact; add a `superseded_by:` link in frontmatter
  and do not edit the body.
- **Inline-update**: document is still authoritative on its topic but
  contains stale path / marker references; update those references in
  place when the rollout PR lands.
- **Archive**: document is historical (`.vault/exec/` records of
  completed work). Leave as-is; the path references are forensic.

### Contradiction inventory

Subagent scan completed `2026-04-30`. ~30 `.vault/` documents reference
old module names, old test markers, or pre-restructure paths in
structural contexts. Classification below; the highest-impact items are
listed first.

#### Tier 1 — superseded by this restructure (core canonical docs)

These two documents define the current `src/aeat/` layout and naming
conventions. They are SUPERSEDED by this restructure ADR; mark
`superseded_by: 2026-04-30-aeat-restructure-adr` in frontmatter at
rollout. Do not edit body — they are historical anchors.

- `adr/2026-04-12-base-module-structure-adr.md` (Accepted) — the
  canonical "what top-level packages exist" decision; establishes
  `src/aeat/` flat layout, names `models`, `submission`, etc. as
  first-class subpackages. **Directly contradicted by every line of
  the new layout.**
- `reference/2026-04-12-base-module-structure-reference.md` —
  onboarding reference for the old conventions; shows
  `from aeat.domain.modelos import ...` as the canonical import; pre-dates
  the nine-marker taxonomy. Replace with a new reference scaffolded
  from this restructure ADR at rollout.

#### Tier 2 — security-sensitive (path-handling boundary moves)

These audits name `src/aeat/_paths.py` as the path-resolution
**security guardrail**. Moving the file to `core/paths.py` does not
relax the guardrail, but the audit-named boundary path changes.
Required action: inline-update the path reference AND re-run the
guardrail validation against `core/paths.py` before merging the
restructure (no security regression).

- `audit/2026-04-17-path-handling-safety-review-audit.md` — names
  `_paths.py` as the centralised guardrail boundary.
- `audit/2026-04-30-secure-persistence-foundation-final-security-audit.md` —
  names `resolve_record_json_path` in `_paths.py` as the authoritative
  guardrail.

The restructure execution PR MUST cite both audits and confirm the
guardrail behaviour is preserved at the new path.

#### Tier 3 — inline-update needed (authoritative on topic, stale references)

These documents remain authoritative on their stated topic but contain
stale path / marker / module-name references. Update references in
place at rollout; do not re-author.

**Test markers (highest cascade) — `adr/2026-04-17-pytest-markers-adr.md`**: defines
the current six axis-B markers (`domain_aeat_remote`,
`domain_submission`, `domain_financial_input`, `domain_local_state`,
`domain_mediation`, `domain_infra`). The marker taxonomy decision
itself stays valid (axis-B markers are still the right shape); only
the marker names are renamed per the test-marker realignment table.
Companion: `research/2026-04-17-pytest-markers-research.md` and
`plan/2026-04-17-pytest-markers-plan.md`.

**Roadmap snapshot — `reference/2026-04-13-cohesive-project-roadmap-reference.md`**:
current-state subpackage inventory listing `models/`, `submission/`,
etc. and the four `domain:*` issue-label families. Inline-update the
subpackage list AND the issue-label taxonomy.

**Submission cluster (rename to `export`)**:

- `adr/2026-04-12-submission-engine-adr.md` — `aeat.adapters.outbound.aeat.export` engine.
- `adr/2026-04-22-aeat-fichero-boe-export-adr.md` —
  `submission/_formats/` layout block; `_engine.py`, `_models.py` paths.
- `adr/2026-04-18-live-submit-cli-excision-adr.md` — `submission/`
  path references (doctrinally authoritative on the excision policy;
  paths only need inline-update).
- `adr/2026-04-25-workflow-live-flag-excision-adr.md` — `submission/`
  paths in non-modification rules.
- `adr/2026-04-17-aeat-access-gate-adr.md` — `aeat.adapters.outbound.aeat.export` import
  from `aeat.adapters.outbound.aeat.auth`; old marker reference.
- `adr/2026-04-18-auth-protocol-adr.md` — `submission/_protocols.py`.
- `adr/2026-04-18-draft-approval-staleness-adr.md` —
  `submission/_confirm.py`.
- `adr/2026-04-24-aeat-cli-wireframe-adr.md` — `submission/_engine.py`
  test paths AND `domain:aeat-remote, domain:submission` issue-label
  references.
- `reference/2026-04-16-submission-safety-sweep-reference.md` —
  `aeat.adapters.outbound.aeat.export` placement decisions, multiple paths.
- `reference/2026-04-22-submission-pipeline-hardening-reference.md` —
  whole document describes / locks `submission/` structure.

**Models cluster (rename to `modelos`)**:

- `adr/2026-04-13-modelo-inventory-adr.md` — `src/aeat/domain/modelos/`
  multiple paths; canonicalises `models` as the home.
- `adr/2026-04-22-citation-blocklist-adr.md` —
  `src/aeat/domain/modelos/_citation_registry.py`.

**Errors cluster (move to `core/errors/`)**:

- `adr/2026-04-25-error-code-registry-adr.md` — `aeat.core.errors` public
  import contract. Critical: the contract `from aeat.core.errors import ...`
  must keep working through the restructure (hard-cutover: all callers updated to new canonical paths in the Step 7 keystone PR).

**Logging cluster (move to `core/logging.py`)**:

- `adr/2026-04-25-json-output-contract-adr.md` — `src/aeat/logging.py`
  named in implementation block.

**MCP cluster (move to `entrypoints/mcp/`)**:

- `adr/2026-04-16-google-workspace-mcp-auth-adr.md` — `aeat.entrypoints.mcp`
  package placement; `.mcp.json` rewires `python -m aeat.entrypoints.mcp.launch_*`
  (script-entry contract; will break unless inline-updated and
  `.mcp.json` regenerated as part of the rollout PR).

**PDF-import cluster (rename to `adapters/inbound/pdf/`)**:

- `adr/2026-04-21-pdf-taxonomy-adr.md` — multiple `_pdf_import/` paths.
- `adr/2026-04-21-real-pdf-fixture-corpus-adr.md` — `_pdf_import/`
  scrub library placement.
- `adr/2026-04-21-declaracion-extractor-adr.md` — `_pdf_import/_shared`
  reference.

**Subpackage-inventory snapshots**:

- `research/2026-04-17-relative-imports-research.md` — current-state
  subpackage map listing every old name. Inline-update to reflect new
  layout, or mark as historical snapshot.

#### Tier 4 — archive (historical execution records, leave as-is)

These documents are forensic — they record completed work. Path
references are accurate to the time of writing and should not be
edited.

- `audit/2026-04-21-real-pdf-import-execution-wave-1-audit.md` —
  execution audit recording the wave-1 PDF import landing.
- `plan/2026-04-21-auth-cli-plan.md` — execution plan; the
  `_paths.py` references appear to be CLI-internal not top-level
  (verify during inline-update).
- `plan/2026-04-21-real-pdf-fixture-corpus-plan.md` — execution plan.
- `plan/2026-04-21-pdf-taxonomy-plan.md` — execution plan.
- `plan/2026-04-25-mandatory-citations-plan.md` — execution plan;
  contains old marker `domain_submission` at module level.
- `plan/2026-04-25-workflow-live-flag-excision-plan.md` — execution
  plan; `submission/` paths.
- `plan/2026-04-17-export-first-roadmap-plan.md` — issue-label
  references (`domain:aeat-remote, area:submission`,
  `domain:mediation`) and the `aeat.adapters.outbound.aeat.export.live_submit` module
  reference.

#### Cross-cutting load-bearing constraints surfaced by the audit

- **Public-import contracts must survive the move.** At minimum
  `aeat.core.errors` (per `error-code-registry-adr`) is documented as a
  stable public surface; relocating to `aeat.core.errors` is handled
  via hard-cutover: all callers updated to new canonical paths in the
  Step 7 keystone PR.
- **Issue-label taxonomy mirrors the markers.** `domain:aeat-remote`,
  `domain:submission`, `domain:local-state`, `domain:mediation`,
  `domain:financial-input` are referenced in multiple ADRs and plans
  as GitHub-issue labels. The label rename ships in lockstep with the
  marker rename, with the same naming.
- **`.mcp.json` is a runtime-config contract**: the script-entry
  string `uv run python -m aeat.entrypoints.mcp.launch_google_workspace` will
  break when `mcp/` moves; the file is regenerated as part of the
  rollout PR.
- **Security audits anchor `_paths.py`** — the path-resolution
  guardrail is a named boundary in two security audits. The
  restructure cannot silently move it; the rollout PR must validate
  the guardrail at `core/paths.py` and update both audit references
  in place.

## External cold-eyes review (2026-04-30)

Two sonnet subagents were given the ADR text only — no codebase access,
no research-doc access, no other vault entries — and asked one specific
question each. The output below captures their verdicts and the per-
finding triage that feeds back into the next ADR refinement.

### Methodology

- Each reviewer received a fresh task with hard tool restrictions:
  read only the ADR file; no other reads, searches, or web access.
- One reviewer answered: "what is the strongest argument AGAINST this
  restructure that a senior engineer would make in a code review?"
- One reviewer answered: "what did the author miss? what is NOT in
  this ADR that should be?"
- Each was capped at ~800 words and asked to flag when a concern would
  require codebase access to validate.

The point of cold-eyes review is to test the *shape* of the proposal,
not the *fit*. Cold reviewers cannot validate destination assignments
against actual code (e.g. they cannot confirm or refute "auth conflates
Google + AEAT"). They can validate that the ADR is internally
coherent, complete, and approval-ready by industry standards.

### Reviewer 1 — strongest objection

**Headline**: "This ADR conflates a destination-layout decision with
an in-flight refactor of 20 unresolved monoliths, meaning it is asking
for approval of an architecture that does not yet exist."

Key findings:

- **Approving a placeholder is not a decision** — the WIP banner is
  honest but the destination tree is drawn against post-split shapes
  that haven't been produced. (Shape objection.)
- **`application/auth/` violates the hexagonal model the ADR cites** —
  Cosmic Python and AWS hexagonal both place auth in `adapters/`, not
  in the service / application layer. The ADR defers the split that
  would resolve this. (Shape objection — partial fit dependency.)
- **`adapters/persistence/llm/` has no coherent home in hexagonal** —
  LLM is either an outbound adapter (calls a remote service) or a
  domain-layer concern, not persistence. (Fit objection.)
- **Marker bifurcation mechanic is under-specified at scale** — "no
  in-flight state where marker name and package name disagree" is a
  promise without a stated mechanism for the per-test reclassification.
  (Shape objection.)
- **`submission` → `export` rename is framed as a safety change but is
  cosmetic** — the actual mitigation is the four-factor gate; the
  rename is a clarity decision. Overstating safety obscures real
  defenses. (Shape objection.)
- **Vault-corpus supersession has no owner or completion gate** —
  acknowledged as parallel calendar time, but no blocking relationship
  to execution. Scope-leak risk. (Shape objection.)

Persuasion path proposed: narrow the ADR to the genuinely-stable
top-level layout + non-contingent renames; mark contingent
destinations as TBD; require top-5 monolith split designs signed off
before approval can advance from `wip` to `accepted`.

### Reviewer 2 — what's missing

**Headline**: "The ADR describes *what* the new layout is and *why*,
but says almost nothing about *how* to validate it worked, *when* to
abort, or *what external surfaces it breaks* — the operational
contract is absent."

Key gaps:

- **No rollback / abort criteria** — under what conditions does the
  team halt or wind back? Phased delivery without abort triggers is a
  scope-creep risk.
- **No definition of done / acceptance criteria** — how does the team
  know the restructure succeeded? "Consequences" is not acceptance
  criteria.
- **Import-boundary enforcement is left to "visual obviousness"** —
  no static-enforcement tool named (`import-linter`, `tach`, etc.).
  Restructures relying on code-review discipline degrade within
  months. (Codebase access needed to audit existing lint
  infrastructure.)
- **Public / external API surface not enumerated** — even an internal
  package can have scripts, notebooks, configs that import directly.
  Semver impact unaddressed.
- **Tooling / IDE / type-checker config impacts not addressed** —
  `mypy`, `pyright`, `pytest.testpaths`, coverage `source` paths,
  pre-commit configs commonly hardcode subpackage paths. CI silently
  goes wrong.
- **`domain_submission` marker successor is openly deferred** — and
  it is **load-bearing for live-write collection-ban**. Window where
  collection enforcement could miss tests is a safety regression risk.
- **Contributor / parallel-agent impact not acknowledged** — the
  project runs up to 6 parallel slots; pre-move branches will produce
  merge conflicts and reintroduce old paths after the layout PR
  lands.

Top 3 additions required before approval:

1. Abort / rollback criteria with explicit halt triggers.
2. Acceptance criteria / definition of done as a verifiable checklist.
3. External surface audit with explicit semver statement.

### Triage and proposed ADR refinements

Both reviewers raised distinct, substantive concerns. None are
generic noise. Triage below uses three buckets:

- **ACCEPT** — the concern is valid, ADR amendment proposed.
- **ACCEPT (clarify)** — the concern is valid but the ADR has partial
  coverage; refinement needed.
- **DISPUTE** — the concern is a misreading; document a counter in
  the ADR so future reviewers don't re-raise.

| # | Source | Finding | Triage | Action |
| --- | --- | --- | --- | --- |
| 1 | R1 / R2 | ADR is a placeholder; needs explicit approval gate | ACCEPT | Add: "ADR advances from `wip` to `accepted` only when top-5 monoliths (`storage`, `cli`, `auth`, `filing`, `errors`) have signed-off split designs folded in." |
| 2 | R1 | `auth` placement in `application/` violates hexagonal canon | ACCEPT (clarify) | The auth audit must propose the split BEFORE the move. Mechanisms (cert, claves, OAuth) are adapters; provider-selection is application. Pre-split `auth/` lands in a temporary home or stays put until split is done. |
| 3 | R1 | `llm` placement in `adapters/persistence/` is wrong | ACCEPT | Move proposed destination to `adapters/outbound/llm/`. The LLM client is outbound; cache + usage tracking are collateral that ride with the adapter. Update heat map. |
| 4 | R1 | Per-test marker bifurcation mechanic missing | ACCEPT | Add to test-marker realignment: "Mechanical mapping — every test marked `domain_local_state` is reclassified by its package location at move time. Modules under new `domain/` get `domain_model`; modules under `adapters/persistence/` get `domain_persistence`. Manual override only when location is ambiguous." |
| 5 | R1 | `submission` → `export` rename safety claim is overstated | ACCEPT | Soften: rename is a CLARITY measure that supports safety by removing a known ambiguity that contributed to past incidents; the actual mitigation is the four-factor gate. |
| 6 | R1 / R2 | Vault-supersession has no owner / completion gate | ACCEPT | Define per-tier gating: T1 superseded markers ship in the layout-move PR; T2 security audits ship before; T3 inline-updates ship in the same milestone; T4 archive does not gate. |
| 7 | R2 | No rollback / abort criteria | ACCEPT | Add abort triggers: (a) post-move CI failure rate > X% across 3 consecutive runs, (b) unresolvable circular import surfaces, (c) marker-realignment leaves any test in a state where collection-ban could mis-fire. Action: revert the layout PR; the rename PRs are decoupled. |
| 8 | R2 | No definition of done / acceptance criteria | ACCEPT | Add checklist: imports resolve under new layout; coverage floor (60% per project mandate) maintained; import-boundary rule shipped (or named follow-up issue); vault contradiction list fully resolved per tier; all marker renames complete; security-audit guardrails validated at new locations. |
| 9 | R2 | Import-boundary enforcement deferred to visual review | ACCEPT (clarify) | Name the tool decision explicitly. Default candidate: `import-linter` (lightweight, contract-driven). The choice itself can be deferred to an execution decision but the requirement to ship a static enforcement is a hard constraint. |
| 10 | R2 | Public / external API surface not enumerated | ACCEPT | Add a "Public surface" subsection: minimum, `aeat.core.errors` (per `error-code-registry-adr`); confirm whether anything else is documented as public. Resolution (post-execution): hard-cutover model adopted — all callers updated in the same change-set as every rename; minor semver bump. |
| 11 | R2 | Tooling / IDE / type-checker config impacts | ACCEPT | Add a "Configuration files affected" subsection enumerating: `pyproject.toml` (`tool.coverage.run.source`, `tool.mypy.exclude`, `tool.pytest.ini_options.testpaths`, `tool.pyright.include`); pre-commit configs; `.mcp.json`; `justfile` / `Makefile` paths. |
| 12 | R2 | `domain_submission` successor decision is deferred and load-bearing | **HARD ACCEPT** — safety regression risk. ADR must REMOVE the deferral. Decide before the move: either (a) `domain_outbound` carries the live-write collection-ban semantics with no finer grain, OR (b) `domain_export` is created as a sub-marker. The four-factor gate is defense-in-depth but the marker is the first line. No deferral. |
| 13 | R2 | Parallel agent slot / pre-move branch impact | ACCEPT | Add a "Transition mechanic" subsection: layout PR lands in a coordinated freeze window (no new branches off pre-move main during the freeze); existing pre-move branches receive a one-shot mechanical rebase that rewrites import paths; agent-slot orchestration pauses for the freeze duration. |

### Convergent themes (both reviewers)

- **The ADR is over-confident relative to its own WIP status** — both
  found this independently. The fix is a concrete approval gate, not
  more disclaimer prose.
- **Live-write safety mechanics need more rigor than the rename
  provides** — Reviewer 1 challenged the rename's safety claim;
  Reviewer 2 found the marker-deferral safety regression risk. Both
  point at the same underlying issue: the ADR treats safety
  guarantees as if they were already preserved when in fact one is
  cosmetic and the other is openly deferred.

### Items NOT raised by cold review (worth noting)

These are constraints the cold reviewers could not see — preserved
here as a check that we haven't lost them in our own framing:

- The Spanish AEAT vocabulary preservation is a project-specific
  constraint neither reviewer pushed back on. Either they accepted it
  silently or they didn't see why it matters; in our context it
  remains correct.
- The vault-corpus contradiction list (now ~30 documents) is a real
  cost the cold reviewers could not estimate. Reviewer 1 flagged it
  abstractly (no completion gate); the actual size is bigger than
  either reviewer could see.
- The security audits anchored on `_paths.py` are non-negotiable to
  validate at the new location; cold reviewers had no way to see this
  but our internal corpus scan surfaced it. Already in the
  cross-cutting constraints section.

### Net verdict

Cold-eyes review was high-value. Two reviewers, both responses
substantive, no generic noise, multiple safety-relevant findings.
Estimated 12 ADR amendments; one (#12, marker deferral) is a hard
safety constraint that must be resolved before any approval; the rest
are quality-of-decision improvements that should land before the ADR
status advances from `wip` to `accepted`.

Recommended next step: a focused ADR-refinement pass that applies
amendments 1, 7, 8, 10, 11, 12, 13 (the operational-contract gaps
which are amendment-shaped, not audit-dependent), and parks
amendments 2 and 3 (auth, llm) for the per-module audit (their
resolution depends on actual code).

## Modules audited

> Appended one at a time. Each entry follows the per-module audit
> schema (functionality-first).

### `aeat.core.errors` (audit 1, 2026-04-30)

#### Functional one-liner

`aeat.core.errors` is the system-wide error identity and rendering layer.
It does three things as a single unit: it defines the `AeatError` base
class that every subpackage's exceptions must inherit from; it
maintains the authoritative compile-time table
(`_DECLARED_ERROR_CODES`, ~2,500 lines) of trilingual metadata for
every concrete exception in the entire codebase; and it exposes the
rendering pipeline that turns any `AeatError` into a deterministic
JSON envelope or human-readable stderr line. It is also explicitly
used as a circular-import firewall — `SiteHealthError` and
`AeatObservabilityError` are declared here so `browser`, `workflow`,
and `observability` can reference common types without importing each
other.

#### Per-file functional inventory

- `__init__.py` (233 LOC) — declares `AeatError` (with the
  `__init_subclass__` auto-bind hook), the cross-package firewall
  exceptions, two CLI-alias notice exceptions, two testing-support
  exceptions, the `McpLaunchError`, and the entire `formulas` error
  hierarchy (8 classes). Re-exports `_registry` symbols at the
  bottom. Verdict: **mixed** — pure-infra base + domain-specific
  exception trees colocated by policy.
- `_registry.py` (2,795 LOC) — `ErrorCode` / `ErrorEnvelope` Pydantic
  schemas, `ErrorCategory` StrEnum, the registry mutable dict +
  immutable proxy, the rendering / lookup functions, AND the 2,468-
  line `_DECLARED_ERROR_CODES` tuple cataloguing every concrete
  exception in the codebase by qualname. Verdict: **mixed** — the
  rendering machinery is pure-infra; the catalogue table is a
  centralised manifest of domain knowledge from 30+ subpackages.

#### Per-symbol classification

(31 public symbols total; full table in audit notes — summary by
classification:)

- **pure-infra** (12): `AeatError`, `WorkspaceLockedError`,
  `DeprecatedAliasError`, `MovedAliasError`, `ErrorCategory`,
  `ErrorCode`, `ErrorEnvelope`, `ERROR_REGISTRY`, `register`,
  `bind_error_code`, `get_registered_error_code`,
  `build_error_envelope`, `render_error_text`, `render_error_json`,
  `get_error_exit_code`, `resolve_error_message`,
  `scrub_error_context` (17 — recount).
- **glue** (1): `resolve_output_language` (bridges `aeat.core.config`
  into the rendering pipeline).
- **domain-formulas** (8): `FormulasError`, `RulesetValidationError`,
  `FormulaCycleError`, `CasillaNotDefinedError`,
  `AmbiguousPeriodError`, `MissingRulesetError`, `EvaluationError`,
  `AuditDiscrepancyError`. **Tight cluster — imported as a unit by
  `aeat.domain.formulas.__init__`.**
- **domain-browser** (1): `SiteHealthError` — held here as firewall.
- **domain-observability** (1): `AeatObservabilityError` — firewall.
- **domain-mcp** (1): `McpLaunchError`.
- **domain-testing** (2): `FilingFixtureError`,
  `FixtureProvisioningError`.

**Conclusion**: 13 of 31 public symbols (42%) carry domain-specific
knowledge. The audit confirms `[CONFLATE]` (was `[CONFLATE?]`) — this
module is conflating pure infrastructure with domain exception trees
that were colocated by policy, not necessity.

#### Data flow

Partially stateful at import time. `_DECLARED_ERROR_CODES` is iterated
into `_ERROR_REGISTRY_MUTABLE` when `_registry.py` first imports;
`ERROR_REGISTRY` wraps that as a `MappingProxyType`. Whenever any
`AeatError` subclass is defined anywhere, `__init_subclass__` calls
`bind_error_code`, which looks up the qualname in
`_DECLARED_CODE_BY_QUALNAME` and writes to `_CLASS_CODE_REGISTRY` and
the class's `code` ClassVar. There is a **hard ordering constraint**:
the declarations table must be fully populated before any subclass
binds. Rendering functions are stateless given a populated registry.

#### Inventory (shape)

- 2 source files; 3,028 LOC total.
- 31 public symbols across 17 exceptions, 3 classes, 10 functions, 1
  constant.
- 4 test files, 427 LOC.

#### Imports IN (consumers)

Consumer cluster signals (load-bearing for split design):

- **`aeat.domain.formulas.__init__`** imports the 8 formulas exceptions as a
  single tight cluster — strong signal these symbols belong with
  `aeat.domain.formulas`, not with `aeat.core.errors`.
- **`aeat.entrypoints.cli._errors`** imports the rendering pipeline as a single
  tight cluster (`AeatError`, `build_error_envelope`,
  `get_error_exit_code`, `get_registered_error_code`,
  `render_error_json`, `render_error_text`) — strong signal these
  must move together.
- **`aeat.adapters.outbound.aeat.browser.session`** + **`aeat.application.workflow._engine`** both
  import `SiteHealthError` — confirms firewall reason.
- **`aeat.core.observability._errors`** imports `AeatObservabilityError`
  — confirms firewall reason.
- ~25 leaf `_errors.py` modules import `AeatError` only — base-class
  contract.
- `aeat.domain.profile.test_errors` imports `ErrorCategory` +
  `get_registered_error_code` — infra-only.

#### Imports OUT

- `__init__.py`: TYPE_CHECKING imports of `SiteHealthStatus` (from
  `aeat.adapters.outbound.aeat.browser._site_health`) and `Translatable` (from
  `aeat.core.i18n`); deferred runtime import of `bind_error_code` from
  `_registry`.
- `_registry.py`: deferred runtime imports of `aeat.core.config` and
  `aeat.core.i18n` inside functions (wrapped in try/except —
  `resolve_output_language` swallows ALL exceptions silently and
  falls back to `es`, which is a quiet failure mode worth noting).

No genuine cross-domain imports — the `browser` reference is
TYPE_CHECKING-only and the `config`/`i18n` are infrastructure
dependencies.

#### Hidden coupling

1. **Bootstrap cycle** between `__init__.py` and `_registry.py`.
   `AeatError`'s `__init_subclass__` defers `from ._registry import
   bind_error_code` because `_registry` is imported at the bottom of
   `__init__.py`. **Splitting the files requires preserving this
   ordering carefully.**
2. **Ordering constraint** on `_DECLARED_ERROR_CODES` — must be fully
   populated before any `AeatError` subclass binds. Currently
   guaranteed because both registries are built before
   `__init__.py` finishes executing.
3. **Full-codebase coupling** via `test_registry_enforcement.py`,
   which calls `pkgutil.walk_packages` over all of `aeat`, imports
   every non-test module, and asserts every `AeatError` subclass has
   a registry entry and every entry maps to exactly one class. This
   is a **structural lock**: any new `AeatError` subclass anywhere
   must have a corresponding `_DECLARED_ERROR_CODES` entry. The lock
   is intentional and load-bearing.
4. **`SiteHealthError.__init__` holds a `SiteHealthStatus`** reference
   from `aeat.adapters.outbound.aeat.browser`. The private `_merge_error_context` and
   `scrub_error_context` in `_registry.py` are implicitly coupled
   to this attribute shape.

#### Domain mapping

Conflates THREE destinations:

- **`core/errors/`** — pure-infra: rendering pipeline, registry,
  scrubbing, exit codes, the catalogue table itself, `AeatError`
  base class, alias notice exceptions, `WorkspaceLockedError`.
- **`core/errors/` as firewall declarations** — `SiteHealthError`,
  `AeatObservabilityError` (declared here for circular-import
  reasons, even though semantically they belong to their domains).
- **Per-domain `_errors.py` modules** — the 8 formulas exceptions
  belong with `aeat.domain.formulas`; `McpLaunchError` belongs with
  `entrypoints/mcp/`; `FilingFixtureError` /
  `FixtureProvisioningError` belong with `domain/testing/`;
  `DeprecatedAliasError` / `MovedAliasError` arguably belong with
  `entrypoints/cli/`.

#### Destination validation

- Original heat-map destination: `core/errors/` (single).
- **Audit revises**: `core/errors/` for the registry + rendering
  machinery + base class + firewall types, with domain-specific
  exception classes redistributing to their domains' `_errors.py`.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (3,028 LOC, fracturable along
  infra/domain split).
- `[CONFLATE?]` — **CONFIRMED → upgraded to `[CONFLATE]`**. Specific
  conflation: pure-infra rendering machinery + catalogue table mixed
  with 13 domain-specific exception classes that ride on the
  `AeatError` base class but encode knowledge of the formulas /
  testing / mcp / cli domains.

#### Boundary violations

- The 8 formulas exceptions are **declared in `errors/__init__.py`
  but raised in `aeat.domain.formulas/_engine`, `_registry`, `_ruleset`,
  `_casilla`, `_ledger`** — and re-exported from
  `aeat.domain.formulas.__init__`. The exceptions themselves live in the
  wrong package; they're imported back into formulas where they're
  raised.
- `McpLaunchError` declared in `errors/__init__.py` and re-imported
  by `aeat.entrypoints.mcp._errors` — same pattern, smaller scale.
- `FilingFixtureError` declared in `errors/__init__.py` and consumed
  back by `aeat.domain.testing.__init__` and `aeat.domain.testing._loader`.

#### Internal split design

`aeat.core.errors` splits into 5 destinations:

| Sub-module | Contents | Destination | Functional reason |
| --- | --- | --- | --- |
| `core/errors/_registry.py` | `ErrorCode`, `ErrorEnvelope`, `ErrorCategory`, `ERROR_REGISTRY`, registry functions, rendering pipeline (`build_error_envelope`, `render_*`), context scrubbing, exit-code mapping. **Plus** the `_DECLARED_ERROR_CODES` table (kept centralised; see open question). | `core/errors/` | Pure infrastructure; one cohesive responsibility (error identity + rendering). |
| `core/errors/__init__.py` | `AeatError` base class with `__init_subclass__` hook; firewall exceptions (`SiteHealthError`, `AeatObservabilityError`); generic infra exceptions (`WorkspaceLockedError`, `DeprecatedAliasError`, `MovedAliasError`). Retained at canonical path; callers updated to new destination paths in the keystone PR. | `core/errors/` | Base class + firewall + generic infra exceptions; ~80 LOC. |
| Move 1 | `FormulasError`, `RulesetValidationError`, `FormulaCycleError`, `CasillaNotDefinedError`, `AmbiguousPeriodError`, `MissingRulesetError`, `EvaluationError`, `AuditDiscrepancyError`. | `domain/formulas/_errors.py` | Already imported as a tight cluster by `aeat.domain.formulas.__init__`; ride home with the domain. |
| Move 2 | `McpLaunchError`. | `entrypoints/mcp/_errors.py` | Already re-imported by `aeat.entrypoints.mcp._errors`. |
| Move 3 | `FilingFixtureError`, `FixtureProvisioningError`. | `domain/testing/_errors.py` | Raised exclusively from `aeat.domain.testing` (and provisioning scripts under `scripts/`). |

**Open**: `DeprecatedAliasError` / `MovedAliasError` placement —
either stay in `core/errors/` (CLI infrastructure) or move to
`entrypoints/cli/_errors.py`. Audit recommendation: **stay in
`core/errors/`** because they're consumed by `aeat.entrypoints.cli._errors`'s
rendering chain alongside `AeatError`, and they don't carry a
business domain payload.

**Net effect on `core/errors/`**: ~570 LOC drops to the domain
modules (the formulas hierarchy alone is ~120 LOC declared in
`__init__.py`); the rest of the size is the catalogue table.

#### Public-API contract impact

Per the existing `error-code-registry-adr`,
`from aeat.core.errors import ...` is a documented public surface.
Treatment:

- **Hard-cutover**: all callers at old `aeat.core.errors` paths updated to
  new canonical homes in the Step 7 keystone PR. No backward-compat
  re-export layer introduced.
- The 8 formulas exceptions ALREADY have a canonical alternative
  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.

Feeds the ADR public-surface table:
- `from aeat.core.errors import AeatError` — hard-cutover to `aeat.core.errors`.
- `from aeat.core.errors import FormulasError` (and the other 7) —
  hard-cutover; canonical home becomes `aeat.domain.formulas`.
- `from aeat.core.errors import McpLaunchError` — hard-cutover;
  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).
- `from aeat.core.errors import FilingFixtureError` — hard-cutover;
  canonical home becomes `aeat.domain.testing`.
- `from aeat.core.errors import (rendering pipeline)` — direct, no
  rename.

#### Naming clarity

- Module name `errors` is **clear** — no rename needed.
- Symbol names are **clear** at module level (`FormulasError`,
  `McpLaunchError`, etc. read well).
- One naming concern: after the move, `from aeat.domain.formulas._errors
  import FormulasError` is a slight misnomer — the file is `_errors`
  but the class IS the formulas error base. Consider renaming the
  destination file to `_exceptions.py` or just folding them into
  `aeat.domain.formulas/__init__.py` (already there as re-exports).

#### Dead code candidates

- **`WorkspaceLockedError`** — appears in 4 test files but no
  production raise sites in the import grep. Either it is raised
  via dynamic mechanism not caught by grep, or it is genuinely
  unused. **Open question** — needs follow-up before deletion.

#### Open questions surfaced

- **`_DECLARED_ERROR_CODES` distribution**: should the catalogue
  table stay centralised in `core/errors/_registry.py` (current
  proposal) or distribute, with each domain's `_errors.py`
  registering its own codes via the `register()` API? Centralised
  is lower-risk and matches the existing
  `test_registry_enforcement.py` structural lock; distributed is
  more decentralised and makes the per-domain modules self-
  contained. **Recommendation: centralised** — distributing is a
  bigger change for marginal benefit; the table is read-only and
  the import-time bootstrap already works.
- **`WorkspaceLockedError` may be dead** — verify with a wider grep
  including dynamic raise sites before declaring it for removal.
- **`resolve_output_language` swallowing all exceptions silently**
  is a quiet failure mode (any config/i18n misconfiguration falls
  back to Spanish with no observability signal). Out of scope for
  this restructure but worth tracking.

#### Verdict

`splits-into-5` (all callers updated to new paths in the keystone PR).

**Rationale**: the audit confirms `[MONO]` and `[CONFLATE]` and
produces a concrete 5-destination split. The pure-infra rendering
machinery + catalogue table + base class + firewall declarations
stay in `core/errors/` (~2,400 LOC). 11 domain-specific exception
classes redistribute to 3 domain `_errors.py` files (~120 LOC). A
hard-cutover: all callers updated to new canonical paths; the `aeat.core.errors` public-API contract is satisfied by the module remaining at its canonical dotted path.

#### Inventory drift discovered

The `_DECLARED_ERROR_CODES` table includes entries for an
`aeat.domain.rental` subpackage with 6 exception classes. This subpackage
**was missing from the original heat-map inventory** — flagged for
follow-up audit (audit 2, below).

### `aeat.domain.rental` (audit 2, 2026-04-30)

#### Functional one-liner

`aeat.domain.rental` is a per-property rental register that computes the
five M100 Anexo C casillas (0061 gross rent, 0066 deductible
expenses, 0072 building amortisation, 0078 reducción, 0085 imputed
income) Kent must file as a Spanish autónomo landlord under IRPF.
It applies the Ley 12/2023 four-tier reducción auto-resolver (90 / 70
/ 60 / 50 percent priority ladder with LAU 17.6 forfeit) and the
LIRPF art. 23.1.f 3 % multi-year amortisation ledger with cost-basis
cap. Implementation tracks issue #454.

#### Per-file functional inventory

10 source files (`__init__.py`, `_enums.py`, `_errors.py`,
`_models.py`, `_tier_resolver.py`, `_amortization_ledger.py`,
`_expense_rollup.py`, `_repository.py`, `_anexo_c_aggregator.py`,
`anexo_c_provider.py`). 5 test files using project-canonical
`_test_*.py` naming (see "Project conventions surfaced" below).
Functional roles:

- **Pure-domain knowledge**: `_enums`, `_errors`, `_models`,
  `_tier_resolver`, `_amortization_ledger`, `_expense_rollup` (5 BOE-
  citation-carrying domain primitives).
- **Persistence**: `_repository.py` — 5 SQLAlchemy session-scoped
  repository classes wrapping `aeat.adapters.persistence.storage._orm` rows.
- **Mixed (orchestrator + integration)**: `_anexo_c_aggregator.py`
  reads from all 5 repositories, dispatches to the 3 pure
  computation functions, returns aggregates with full audit
  attribution; `anexo_c_provider.py` is a backwards-compat shim that
  bridges the rental register to the existing M100 ruleset.

#### Per-symbol classification

37 public symbols total:

- **domain-rental** (24): `UseType`, `ExpenseCategory`,
  `ReduccionTier`, all 6 exception classes, all 5 Pydantic record
  models, `TierResolution`, `resolve_reduccion`,
  `AmortizationComputation`, `compute_amortization_for_year`,
  `GastosForYear`, `CarryForwardEntry`, `compute_gastos_for_year`,
  `AnexoCAggregates`, `FincaAttribution`, `ContractTierAttribution`,
  `compute_anexo_c_aggregates`, plus 6 BOE-derived constants
  (`ART_23_1_F_RATE`, `CAPPED_CATEGORIES`, `CARRY_FORWARD_MAX_YEARS`,
  `DEFAULT_EJERCICIO_AMENDMENT_YEAR`, `LEY_12_2023_IN_FORCE_DATE`,
  `ANEXO_C_CASILLAS`).
- **persistence** (5): the 5 repository classes
  (`RentalFincaRepository`, `RentalContractRepository`,
  `RentalIncomeRepository`, `RentalExpenseRepository`,
  `RentalAmortizationLedgerRepository`).
- **glue** (2): `computation_to_ledger_entry` (computation →
  persistable record), `compute_or_passthrough` + `AnexoCMergeReport`
  (rental register → M100 ruleset bridge).
- **pure-infra** (0): none. Every public symbol is either domain or
  persistence or domain↔persistence/integration glue.

**Conclusion**: this is a clean domain-rental subpackage with a
persistence-side repository module and two integration glues.
NOT conflated; the persistence module is a layer-mate, not a
hidden domain. Domain repositories living next to the domain matches
the project's existing pattern (`filing/_repository.py`,
`filing/_history_repository.py`, etc.).

#### Data flow

Hybrid pipeline:

1. CLI `aeat rental finca/contract/income/expense add|record|...` →
   repository CRUD → SQLite via `aeat.adapters.persistence.storage._orm`.
2. CLI `aeat rental anexo-c compute --year YYYY` →
   `compute_anexo_c_aggregates` reads all 5 tables → calls 3 pure
   computation functions → returns `AnexoCAggregates` with full
   audit attribution.
3. M100 ruleset integration: `compute_or_passthrough` merges
   aggregates into the existing M100 casilla surface, returning
   `AnexoCMergeReport`.

The 3 pure computation modules (`_tier_resolver`,
`_amortization_ledger`, `_expense_rollup`) are stateless. Carry-
forward state for expense rollup is **not yet persisted** — the
aggregator's `_existing_carry_forward()` is a documented stub
returning `()`. Multi-year carry-forward silently resets each run.

#### Inventory (shape)

- 10 source files; 2,330 LOC total.
- 5 test files; 1,416 LOC.
- 37 public symbols (16 classes / 6 functions / 3 enums / 6
  exceptions / 6 constants).

#### Imports IN (consumers)

Initial inventory grep (`from ..rental | from .rental | from
aeat.domain.rental`) returned EMPTY — that was a methodology miss. The
audit ran a broader scan and found the imports are all at 3-dot
depth (`from ...rental`) navigating from `cli/rental/<file>.py` up
to `rental/`. Actual consumers:

- **`cli/__init__.py`** — registers the `rental` typer sub-app
  (5 sub-groups: `finca`, `contract`, `income`, `expense`,
  `anexo-c`).
- **`cli/rental/finca.py`**, **`contract.py`**, **`income.py`**,
  **`expense.py`**, **`anexo_c.py`** — 5 CLI sub-modules consume
  the rental public surface.
- **`errors/_registry.py`** — 6 error-code registrations at
  lines 2489–2565.

**`workflow/` has ZERO rental references.** The `compute_or_passthrough`
shim was built to be called from the M100 workflow but the wiring
hasn't landed.

#### Imports OUT

- `..errors.AeatError` (base class, in `_errors.py`).
- `..logging.get_logger` (in `_repository.py`,
  `_anexo_c_aggregator.py`, `anexo_c_provider.py`).
- `..storage._orm` row types (TYPE_CHECKING + deferred runtime
  imports inside method bodies — to keep Alembic out of CLI
  startup).
- `..storage.errors.RepositoryError`.

No imports from any other domain (no `aeat.adapters.inbound.declaracion`,
`aeat.domain.modelos`, `aeat.domain.formulas`, etc.).

#### Hidden coupling

1. **`_repository.py` ↔ `aeat.adapters.persistence.storage._orm`**: 5 ORM row types must
   exist in `_orm.py` with matching column names; runtime breakage
   only (no compile-time check beyond TYPE_CHECKING stubs). Tightest
   coupling in the subpackage.
2. **Carry-forward stub at `_anexo_c_aggregator.py:324-332`**:
   `_existing_carry_forward()` always returns `()`, silently
   discarding the per-year carry-forward state that
   `_expense_rollup.GastosForYear.carry_forward_after` correctly
   computes. Casilla 0066 will be understated for any finca whose
   capped categories exceed gross rent in the prior year.
3. **`_anexo_c_aggregator._compute_finca_amortization` synthetic
   `RentalIncomeRecord`**: passes `contract_id=finca.id` to satisfy
   `compute_amortization_for_year`'s signature — semantic mismatch
   (`contract_id` is a FK to `rental_contracts`, not `rental_fincas`).
4. **Error-code registry coupling**: every `_errors.py` class must
   appear in `errors/_registry._DECLARED_ERROR_CODES` (it does, lines
   2489–2565). New rental exceptions require coordinated edits in a
   distant 2,500-line file.

#### Domain mapping

Single destination: **`domain/rental/`** for the entire subpackage.

The presence of `_repository.py` does NOT split the destination
because per-domain repositories living next to their domain matches
the project's existing pattern (`filing/_repository.py`,
`filing/_history_repository.py`, `filing/_complementaria_repository.py`,
`justificante/_repository.py`, etc.). The `adapters/persistence/storage/`
destination holds the ORM and blob layer; per-domain repositories ride
home with their domain and import from storage.

#### Destination validation

- Original heat-map destination: `domain/rental/` (proposed, low
  confidence).
- **Audit confirms**: `domain/rental/` for the entire subpackage.
  Confidence upgraded to **high**.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (2,330 LOC source). Internal split design
  is implicit in the file structure: each computation module
  (`_tier_resolver`, `_amortization_ledger`, `_expense_rollup`) is
  already a single-responsibility unit. **No split needed** — the
  module is composed of cohesive single-purpose files. The MONO flag
  reflects total LOC, not internal cohesion debt.
- `[CONFLATE?: _repository.py is persistence]` — **CLEARED**.
  Repository belongs with its domain per project pattern.
- `[ZERO-IMPORTERS?]` — **CLEARED**. Audit found 7 importers
  (`cli/__init__.py`, 5 CLI sub-modules, `errors/_registry.py`).
  Initial grep miss; methodology lesson recorded below.

#### Public-API contract impact

The `aeat.domain.rental` import is consumed only by `aeat.entrypoints.cli.rental.*`
modules. No external (non-CLI, non-error-registry) consumers exist
in source. The move to `aeat.domain.rental` updates 5 CLI files'
relative imports — mechanical. No re-export shim required (no
documented public-API contract on `aeat.domain.rental` itself).

#### Naming clarity

- Module name `rental` is **clear** — telegraphs domain.
- Symbol names mostly clear, with two AEAT-specific terms preserved
  per the Spanish-canonical vocabulary policy (`reducción`,
  `casilla`).

#### Dead code candidates

None obvious. The `_existing_carry_forward()` stub is intentional
(not dead, just unimplemented), with a documented future-PR note.

#### Open questions surfaced

- **Workflow integration gap**: rental computes its 5 casillas but
  the M100 workflow does NOT call `compute_or_passthrough`. Kent
  using `aeat workflow run` for M100 will not have his rental data
  applied. Out of scope for the restructure but a real Kent-
  capability gap. Worth flagging for the project board (issue may
  exist under #454).
- **Carry-forward persistence**: the stub at
  `_anexo_c_aggregator.py:324` silently undercounts casilla 0066 in
  multi-year scenarios. Out of scope for restructure.
- **`_test_repository.py` marker accuracy**: marked `unit` + the old
  `domain_local_state` but requires live SQLite. Marker is mis-
  applied (integration in unit's clothing). Out of scope for
  restructure but a marker-realignment phase concern.

#### Verdict

`clean-MONO`. Single-destination, well-named, internally cohesive,
fully wired (CLI), no conflation. The MONO flag reflects size only;
the file structure is already at single-responsibility granularity
and no internal split is needed. Destination: `domain/rental/`.

#### Methodology lesson

The initial inventory grep used `from .rental | from ..rental |
from aeat.domain.rental` which missed the 3-dot relative imports
(`from ...rental`) used by CLI sub-package consumers. The lesson is
recorded for future audits: **subpackages with consumers nested 2
levels deep (e.g. `cli/<sub>/<file>.py`) need a depth-aware grep
including `from ...<name>` patterns.** The original inventory's
"zero-importers" flag was a methodology miss, not a real orphan.

### `aeat.adapters.outbound.aeat.auth` (audit 3, 2026-04-30)

#### Functional one-liner

`aeat.adapters.outbound.aeat.auth` is a multi-domain authentication umbrella serving FOUR
distinct concerns under one home: (1) Google OAuth + service-account
auth for Drive / Sheets / GCP API access, (2) AEAT Sede Electrónica
auth via X.509 PKCS#12 certificate (mTLS + Playwright) and Cl@ve Móvil
(phone-push), (3) the live-access policy gate that enforces the
project's "no live AEAT writes ever" rule, and (4) a (currently dead)
secret-storage migration adapter for moving legacy credential files
into a typed secret store. Initial inventory's `[CONFLATE]` flag is
**confirmed and upgraded** — this is one of the most conflated
modules in the codebase.

#### Per-file functional inventory

| File | LOC | Verdict |
| --- | --- | --- |
| `__init__.py` | 507 | **mixed** — entire Google-auth machinery defined inline; AEAT symbols re-exported from private modules |
| `_authenticator.py` | 1,235 | `domain-aeat` (cert path: TLS handshake, Playwright session, persist/resume) |
| `_clave_movil.py` | 962 | `domain-aeat` (Cl@ve Móvil QR + phone-push) |
| `certificate.py` | 822 | `domain-aeat` — but contains misplaced `AeatLiveReadNotEnabledError` |
| `_providers.py` | 356 | `domain-aeat` (provider contracts + `select_provider` factory) |
| `_secret_adapters.py` | 278 | `domain-secret-storage` — **NO PRODUCTION CALLERS** (dead in production; only `_test_*.py` consumes it) |
| `_google_paths.py` | 231 | `domain-google` (auth path inspection without browser flow) |
| `_gate.py` | 115 | `gate-policy` (the four-factor live-access gate) |
| `_file_permissions.py` | 111 | `pure-infra` (cross-platform chmod 0o600 / icacls) |
| `_certificate_backends/` | ~150 | `domain-aeat` (Playwright cert-context kwarg builder; httpx fallback) |
| **Total source** | **4,617** | |

#### Per-symbol classification (98 public symbols, summarised)

- **google-auth** (~24): all OAuth scope constants (`DRIVE_SCOPE`,
  `SHEETS_SCOPE`, `CLOUD_PLATFORM_SCOPE`, etc.), `get_oauth_credentials`,
  `get_service_account_credentials`, `get_credentials`,
  `get_credentials_for_scopes`, `get_adc_credentials_with_scopes`,
  `assert_credentials_have_scopes`, all `build_*_service` /
  `build_*_client` factories, `format_scope_csv`, `GoogleAuthPath`,
  `GoogleAuthInspection`, `inspect_google_auth`,
  `inspect_oauth_token_cache`, `normalize_google_auth_path`,
  `adc_well_known_path`.
- **aeat-auth** (~50): `AeatAuthenticator`, `AeatSession`,
  `AeatLoginAssertion`, `AEAT_SESSION_IDLE_TTL`, all 5 Browser
  Playwright protocols, `ClaveMovilAuthProvider` and its 2 errors,
  `AuthProviderKind`, `AuthProvider`, `AuthProviderDescription`, all
  4 session-detail variants, all 4 login-assertion-detail variants,
  `BrowserContextProvisioner`, `CertificateContextProvisioner`,
  `select_provider`, `describe_provider_operator_impact`,
  `CERTIFICATE_CONTEXT_MARKER`, all certificate-domain records and
  errors, `load_certificate`, `evaluate_loaded_certificate_health`,
  `extract_nif_from_subject`, `preload_into_browser_context`,
  `verify_handshake`, `build_client_certificates_kwarg`.
- **gate-policy** (2): `AeatAccessGate`, `AeatGateEnvSnapshot`.
- **secret-storage** (~13): all `KEY_*` constants and `load_*` /
  `migrate_*` helpers — **dead in production**.
- **pure-infra** (1): `restrict_file_permissions`.

**Conclusion**: the symbol breakdown matches three independent
domains (google, aeat, secret-storage) plus one cross-cutting policy
(gate) plus one OS primitive (file-permissions). Of 98 public
symbols, ZERO carry knowledge of more than one of these axes. The
conflation is purely physical — separate concerns sharing one
package because of historical co-location.

#### Data flow (4 independent flows)

- **Google flow**: Settings → `GoogleAuthPath` dispatch →
  `get_credentials()` → `BaseCredentials` → `build_*_service()` →
  Google API client. Token cache as plain JSON file on disk.
- **AEAT certificate flow**: Settings → `AeatAuthenticator` →
  PKCS#12 load → httpx mTLS handshake → Playwright `client_certificates`
  context kwarg → AEAT verify URL navigation → `AeatSession` +
  storage_state sidecar.
- **AEAT Cl@ve Móvil flow**: Settings → `ClaveMovilAuthProvider` →
  Playwright headed window → QR/DNI input → phone-push polling →
  storage_state sidecar → `AeatSession` (provider_kind=CLAVE_MOVIL).
- **Gate flow**: `AeatAccessGate(settings).require_live_read()` reads
  `AEAT_LIVE_TESTS_ENABLED` fresh from `os.environ` every call;
  `require_live_write()` always raises.

The four flows share no runtime state.

#### External consumers (imports IN)

Per-axis consumer breakdown:

- **Google-auth axis** (10 consumers): `cli/drive.py`,
  `cli/sheets.py`, `cli/docs.py`, `cli/cloud.py`,
  `cli/bootstrap.py`, `cli/_live.py`, `cli/auth/__init__.py`,
  `cli/doctor.py` (mixed), `mcp/launch_google_workspace.py`,
  `config.py` (just `GoogleAuthPath`).
- **AEAT-auth axis** (~14 consumers): `browser/session.py`,
  `browser/_factory.py`, `workflow/_engine.py`,
  `workflow/_adapters.py`, `submission/_protocols.py`,
  `submission/_preflight.py`, `setup/_wizard.py`, `setup/_models.py`,
  `cli/auth/_paths.py`, `cli/auth/_registry.py`,
  `cli/auth/_render.py`, `cli/auth/_session.py`,
  `cli/filing/_reconcile.py`, `cli/sede/__init__.py`,
  `sede/_walker.py`, `sede/_notifications.py`,
  `sede/_declarations.py`, `errors/test_registry.py`,
  `cli/test_error_decorator.py`, `config.py` (`AuthProviderKind`,
  `CertificateBackend`).
- **Gate-policy axis** (2): `cli/doctor.py`,
  `submission/test_live_submit_permanently_forbidden.py`.
- **Secret-storage axis** (0 production consumers): only
  `_test_secret_adapters.py`.

**Critical observation**: every consumer imports symbols from EXACTLY
ONE axis. No consumer imports both Google and AEAT symbols (except
`config.py` which imports the enum types only). This is the
strongest possible signal that the two axes belong in different
homes — the consumer graph is already bifurcated; only the source
package conflates them.

#### Imports OUT (cross-domain)

Most outbound imports are `..config` (TYPE_CHECKING), `..logging`,
`..errors`, `..storage`. Plus one **load-bearing cross-domain
import**:

- `_gate.py:100` (deferred): `from ..submission import
  LiveSubmitForbiddenError`. The gate depends on an exception class
  from the `submission` package. Under the new layout (`gate` →
  `core/`, `submission` → `adapters/outbound/.../export/`), this
  becomes a `core/` → `adapters/` import which **violates the
  layered import-boundary contract** in the ADR. **Resolution
  required**: move `LiveSubmitForbiddenError` to live with the gate
  in `core/access_gate/_errors.py`, since it's a policy error, not a
  submission-flow error.

#### Hidden coupling

- **Google ↔ AEAT genuinely independent** at runtime. They share
  nothing.
- **`_authenticator` ↔ `_clave_movil`**: share session envelope
  types (`AeatSession` is provider-agnostic with discriminator).
  Both call `restrict_file_permissions` and `fsync_parent_dir`.
- **`_secret_adapters.py` is unwired in production**. Wave-2
  migration helpers exist but no production caller.
- **`_authenticator._write_json_atomic` and
  `_clave_movil._write_json_atomic` are duplicated implementations**,
  not shared. Both apply the same chmod + fsync pattern. Genuine
  duplication.
- **`AeatLiveReadNotEnabledError` is misplaced** in
  `certificate.py` despite having no certificate relevance. Belongs
  with the gate.
- **`BrowserPageLike` / `BrowserResponseLike` / `BrowserContextLike`
  / `BrowserSessionLike` defined in `_authenticator.py`** — these
  are pure Playwright structural protocols used by `aeat.adapters.outbound.aeat.browser`.
  CORE-LEAK candidate.

#### Gate-policy preservation invariants (5)

The audit identified 5 invariants the restructure must preserve:

1. `AeatAccessGate` must NEVER be passed as a constructor parameter
   or stored on an engine — module docstring names this the "anti-
   injection" property (R5).
2. `require_live_read()` must read `os.environ` fresh at call time
   (not cached at `__init__`).
3. `require_live_write()` must always raise
   `LiveSubmitForbiddenError` with no conditional path.
4. The `_gate.py` → `LiveSubmitForbiddenError` import must be
   preserved (or `LiveSubmitForbiddenError` must move to a shared
   location accessible from gate without crossing the layered-
   import boundary).
5. `AeatGateEnvSnapshot.model_config` must remain `frozen=True` and
   `extra="forbid"`.

#### Domain mapping (5 destinations confirmed)

The audit confirms — and the cold reviewer R1's objection that auth
should not live in `application/` is **upheld**. The split:

| Sub-cluster | Symbols | Destination |
| --- | --- | --- |
| Google OAuth + GCP service builders | All `__init__.py` Google content + `_google_paths.py` | `adapters/outbound/google/` |
| AEAT auth providers (cert + Cl@ve) | `_authenticator.py`, `_clave_movil.py`, `_providers.py`, `certificate.py`, `_certificate_backends/` | `adapters/outbound/aeat/adapters/outbound/aeat/auth/` (new sub-cluster) |
| Live-access gate + policy errors | `_gate.py` + `AeatLiveReadNotEnabledError` (moved from `certificate.py`) + `LiveSubmitForbiddenError` (moved from `submission/`) | `core/access_gate/` |
| File-permission primitive | `_file_permissions.py` | `core/file_permissions.py` |
| Browser Playwright protocols | `BrowserContextLike`, `BrowserPageLike`, `BrowserResponseLike`, `BrowserSessionLike`, `BrowserSessionFactory` | `adapters/outbound/browser/_protocols.py` (CORE-LEAK upgrade — these belong to browser, not auth) |
| Secret-storage adapters (dead) | `_secret_adapters.py` | **DELETE** (no production callers) — verify with one-more-grep before final deletion |

The new layout introduces a sub-cluster `adapters/outbound/aeat/`
that groups all AEAT-portal-side outbound adapters as siblings:
`auth/`, `sede/`, `browser/`, `export/` (the renamed submission). This
mirrors `adapters/outbound/google/` for Google-side adapters. The
restructure ADR layout block needs updating to add this nesting.

#### Destination validation

- Original heat-map destination: `application/auth/` (single,
  flagged for split-design audit).
- **Audit revises**: 5 destinations as above. Original placement
  was wrong — this confirms cold-reviewer objection #2 from the
  external review section.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (4,617 LOC source).
- `[CONFLATE]` — **CONFIRMED with 4-way breakdown** (Google, AEAT,
  gate, dead secret-storage).
- `[CORE-LEAK?: _secret_adapters, _file_permissions]` —
  **PARTIALLY CONFIRMED**:
  - `_file_permissions.py` IS a CORE-LEAK — moves to `core/`.
  - `_secret_adapters.py` is dead, not a leak; deletion candidate.
  - **NEW CORE-LEAK discovered**: the 5 Browser Playwright
    protocols defined in `_authenticator.py` belong to
    `adapters/outbound/browser/`.

#### Public-API contract impact

- The `aeat.adapters.outbound.aeat.auth` import surface is **massive** (~98 symbols).
- **Per-axis hard-cutover** is the pattern applied: `aeat.adapters.outbound.aeat.auth`
  becomes a split across 5 new homes; all callers updated to the new canonical paths.
- Most consumers import a single-axis tight cluster — verified by
  the consumer breakdown. Each consumer's imports rewrite to a
  single new home (Google → `aeat.adapters.outbound.google`, AEAT →
  `aeat.adapters.outbound.aeat.auth`, etc.).
- The hard-cutover adds no per-symbol cost; each caller imports from exactly one new home.

Feeds the ADR public-surface table.

#### Naming clarity

- The module name `auth` is **misleading** at the current scope —
  it telegraphs "authentication" but the package also holds the
  live-access gate (a policy concern) and dead secret-storage code.
  After the split, no single destination is called `auth/`; the
  AEAT auth provider cluster lives at
  `adapters/outbound/aeat/adapters/outbound/aeat/auth/` (clear from path), and Google auth
  at `adapters/outbound/google/`.
- `select_provider` and `AuthProvider` are clear. The provider
  protocols (`BrowserContextProvisioner`, `CertificateContextProvisioner`)
  read clearly.

#### Dead code candidates

- **`_secret_adapters.py` entire module (278 LOC)** — no production
  callers. Wave-2 migration helpers exist but have not been wired.
  Verify with one more grep before deletion.
- **`describe_certificate_provider`** (in `_providers.py`,
  exported from `_providers.__all__` but NOT from `auth.__init__`)
  — possibly internal-only; verify before keeping.

#### Open questions surfaced

- **`LiveSubmitForbiddenError` relocation**: must move from
  `submission/` to `core/access_gate/_errors.py` to keep the gate
  layered correctly. This is a coordinated change with the
  submission → export rename.
- **`adapters/outbound/aeat/` sub-cluster**: the new layout
  introduces an `aeat/` parent under `outbound/` that groups
  AEAT-portal adapters (auth, sede, browser, export). The ADR
  layout block needs this nesting added. Decide: is this nesting
  worth adding (telegraphs the AEAT vs Google distinction
  explicitly) or does it add ceremony for marginal value?
- **`adapters/outbound/google/` is genuinely an outbound adapter**
  (calls Google APIs) — confirmed not domain-state.
- **`select_provider` and the provider-agnostic types
  (`AuthProviderKind`, `AuthProvider`, all 4 session-detail
  variants)**: these are the "use case" layer (selection logic)
  while the concrete `AeatAuthenticator` / `ClaveMovilAuthProvider`
  are adapter implementations. Could split provider-selection into
  `application/auth/` (slim, just the selection logic) with
  concrete providers in `adapters/outbound/aeat/adapters/outbound/aeat/auth/`. Keeps
  hexagonal clean. **Recommendation**: yes, split provider-selection
  to application; keeps the layered model honest.

#### Verdict

`splits-into-5-plus-1-delete`.

**Rationale**: 4,617 LOC across 4 conflated concerns + 1 dead module
+ 1 misplaced primitive. The audit produced concrete destinations
for every public symbol, with consumer-graph evidence supporting
each split call. The split also resolves cold-reviewer R1's
objection #2 (auth in `application/` violates hexagonal) and
surfaces a layered-import-boundary issue around
`LiveSubmitForbiddenError` that must be coordinated with the
submission → export rename.

### `aeat.adapters.persistence.storage` (audit 4, 2026-04-30) — structural-survey pass

#### Functional one-liner

`aeat.adapters.persistence.storage` is the monolithic governed-persistence substrate for
the entire system. It bundles five distinct concerns under one
package: SQL persistence (SQLAlchemy ORM + engine + session +
repositories + Alembic migrations), at-rest encryption (AES-256-GCM
primitives + transparent column encryption + file-backed cipher
envelopes + classification-gated blob store + secret store),
master-key lifecycle (3 provider implementations + KDF migration +
BIP-39 recovery wrapping + atexit zeroise + master-key rotation
across all ciphertext consumers), data-governance primitives (9-
class sensitivity taxonomy + redaction strategies + path-containment
guards + corpus-integrity manifests + file locking), and secret
materialisation (process-singleton SecretStore + tempfile bridge to
file-path-demanding APIs).

#### Inventory correction

The initial heat-map recorded `storage` as 11,972 LOC of non-test
source. Deep audit shows actual source is **7,090 LOC** across 21
files; tests are 5,316 LOC across 23 `_test_*.py` files. The
original inventory's test-file regex matched only `test_*.py` and
missed the `_test_*.py` colocated convention, mis-counting ~5k LOC
of tests as source. **Methodology lesson**: audits using both
patterns are more accurate. Other affected subpackages may need
re-counting.

#### Functional clusters (6 identified)

1. **SQL substrate** (~989 LOC): `_orm`, `engine`, `session`,
   `repository`, `records`, `migrations_api`. Only cluster with
   SQLAlchemy / Alembic dependencies.
2. **Crypto + column encryption** (~505 LOC): `_crypto`,
   `_encrypted_columns`. Foundational AEAD + transparent column
   encryption.
3. **Master-key + recovery** (~1,535 LOC): `_master_key` (1,234
   LOC, the single largest file), `_recovery`. Key lifecycle +
   BIP-39 mnemonic wrapping.
4. **File persistence** (~1,916 LOC): `_envelope` (560), `_blob_store`
   (529), `_secret_store` (411), `_materialisation` (217), `_lock`
   (199).
5. **Governance policy** (~1,119 LOC): `_classification` (309),
   `_redaction` (256), `_path_safety` (126), `_corpus_manifest`
   (428).
6. **Rotation** (~514 LOC): `_rotation` — single file, **crosses
   clusters** (imports private `_envelope` internals + delegates to
   `_blob_store`).

#### External-consumer cluster signals

The consumer graph confirms cluster boundaries:

- **SQL substrate** imported as a tight cluster by `rental._repository`
  (ORM rows + session + engine) and `cli/rental/_helpers.py`.
- **File persistence + governance** imported as a multi-cluster
  bundle by every per-domain repository (`filing`, `financial.*`,
  `submission`, `sync`, `workflow`, `justificante`). The bundle is
  consistently: `Envelope`, `CipherEnvelope`,
  `save_encrypted_envelope`, `load_encrypted_envelope`,
  `SensitivityClass`, `exclusive_file_lock`, `PathContainmentError`,
  `_resolve_master_key_provider`, `ClassificationError`,
  `EnvelopeVersionError`. **This is the encrypted-record contract**
  every per-domain repository binds to.
- **Master-key + rotation** imported as a unit by `cli/security.py`
  (~25 symbols).
- **Redaction + classification** imported cross-domain by
  `observability` and `llm`.
- **`fsync_parent_dir`** imported cross-domain by `auth/_authenticator`,
  `auth/_clave_movil`, `env_io`, `financial/invoices/_service`,
  `financial/attachments/_store`, `llm/_cache`.

#### Hidden coupling (5 critical)

1. **`_rotation.py` imports private `_envelope.py` internals**
   (`_build_aad`, `_derive_envelope_key` via `# type: ignore`).
   Cannot separate without promoting the privates to a contract.
2. **`_encrypted_columns._resolve_master_key_provider`** is `_`-
   prefixed but used by 12+ external consumers — de-facto public.
3. **`_master_key.py:907` deferred import from
   `aeat.domain.financial.invoices._validators`** (NIF canary). Storage
   has an upward dependency on financial — cross-domain leak.
4. **`fsync_parent_dir` lives in `_lock.py`** but used cross-domain
   beyond locking. Logical home is durable-write utility.
5. **3 shared mutable globals** — `_encrypted_columns._provider_override`,
   `_materialisation._singleton_store`, `engine._engines` — test
   teardown must reset all three together.

#### Domain mapping (dual-axis split)

The audit produces a dual-axis split: most clusters stay in storage
but governance + locking + path-safety bubble up to `core/`.

**Sub-modules under `adapters/persistence/storage/` (7)**:

| Sub-module | Files | LOC |
| --- | --- | --- |
| `sql/` | `_orm`, `engine`, `session`, `repository`, `records`, `migrations_api` | ~989 |
| `crypto/` | `_crypto`, `_encrypted_columns` | ~505 |
| `master_key/` | `_master_key`, `_recovery` | ~1,535 |
| `envelope/` | `_envelope` | ~560 |
| `blob_store/` | `_blob_store` | ~529 |
| `secret_store/` | `_secret_store`, `_materialisation` | ~628 |
| `_rotation.py` (single file, crosses clusters) | `_rotation` | ~514 |

Plus `errors.py` (shared error hierarchy) + `__init__.py` (public-surface re-exports).

**CORE-LEAK promotions to `core/` (5 modules)**:

| Promoted module | Source | Reason |
| --- | --- | --- |
| `core/classification/` | `_classification.py` | Used by observability, llm, all encrypted repositories |
| `core/redaction/` | `_redaction.py` | Cross-cutting PII redaction (observability, llm) |
| `core/corpus_manifest/` | `_corpus_manifest.py` | Self-attesting integrity primitive, not storage-specific |
| `core/locks.py` | `_lock.py` | OS-level file locking + `fsync_parent_dir`, used cross-domain |
| `core/path_safety.py` | `_path_safety.py` | Already a thin wrapper over `aeat.core.paths` (which becomes `core/paths.py`) — fold into or sibling of `core/paths.py` |

#### Destination validation

- Original heat-map: `adapters/persistence/storage/` (single,
  internal split deferred).
- **Audit revises**: 7 sub-modules under `adapters/persistence/storage/`
  + 5 module promotions to `core/`.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (7,090 LOC, still well over threshold).
- `[CONFLATE]` — **CONFIRMED with 5-cluster + 1-rotation breakdown**.
- `[CORE-LEAK?]` — **PARTIALLY CONFIRMED**. `_path_safety` and
  `_lock` confirmed CORE-LEAK; `_crypto` and `_master_key` STAY
  in storage (only consumed inside storage). **NEW CORE-LEAK**:
  `_classification`, `_redaction`, `_corpus_manifest` (cross-domain
  consumers identified).

#### Boundary violations

- **`_master_key.py:907` cross-domain leak** to
  `aeat.domain.financial.invoices`. Resolution candidates: (a) move
  `validate_spanish_tax_id` to `core/identity/`, (b) inject the
  validator as a callback into the master-key provider, or (c)
  inline a copy. **Recommendation**: (a) or (b); inlining
  duplicates rules.
- **`_orm.py` carries rental-domain ORM tables** (5 tables, ~200
  LOC). Pragmatic Alembic constraint (one `Base` for autogenerate);
  rental REPOSITORY lives correctly in `domain/rental/`. The ORM
  bifurcation is acceptable — known Alembic limitation, not a
  cohesion bug.

#### Public-API contract impact

- `aeat.adapters.persistence.storage.__init__.__all__` re-exports 130 symbols.
- After split: all callers updated to new canonical paths in the Step 7 keystone PR;
  hard-cutover model — no re-export layer at old `aeat.adapters.persistence.storage`.
- 5 CORE-LEAK promotions create new `aeat.core.*` public surfaces;
  all consumers at old paths updated in the same change-set.
- `_resolve_master_key_provider` is de-facto public (12+ external
  consumers). **Recommendation**: rename to
  `resolve_master_key_provider` (drop underscore) at move time.
- `Base`, `KEYRING_SERVICE`, `KEYRING_USERNAME` preserved at canonical paths via hard-cutover.

Feeds the ADR public-surface table.

#### Naming clarity

- `storage` is **clear** — persistence substrate.
- Internal sub-module names (`sql/`, `crypto/`, `master_key/`,
  `envelope/`, `blob_store/`, `secret_store/`) read clearly.
- `_resolve_master_key_provider` is misleading (`_` prefix on a
  publicly-used symbol) — rename during move.

#### Open questions surfaced

- **NIF canary cross-domain leak** — three resolution options
  listed; pick during execution.
- **`_rotation.py` private-helper coupling** — promote
  `_build_aad` and `_derive_envelope_key` to a contracted surface
  pre-split.
- **`fsync_parent_dir` separation** — extract from `_lock.py` into
  `core/fsync.py` or fold into `core/paths.py`.
- **Per-sub-module deep audits required** — survey identified
  clusters; per-symbol classification within each cluster is
  follow-up work. Highest priority: `master_key/` (1,535 LOC, the
  single largest cluster).
- **Schema versioning lives in Alembic** at repo root
  (`migrations/versions/`); 3 migrations to date. Restructure must
  preserve Alembic targets and the `engine.get_engine` auto-
  migration path.

#### Verdict

`splits-into-7-internal-plus-5-core-promotions`.

**Rationale**: 7,090 LOC of conflated persistence stack with 6
distinct cluster boundaries (1 cross-cluster). The split is
concrete and consumer-graph-validated. Per-sub-module deep audits
follow.

### `aeat.application.filing` (audit 5, 2026-04-30)

#### Functional one-liner

`filing/` is the project's **draft-production engine**: it turns a
taxpayer profile, a period, and raw casilla inputs into a typed,
validated, locally-approved `FilingDraft` — the single record the
rest of the system treats as "what Kent actually files." It also
covers the full lifecycle of that record: amendment
(complementaria/sustitutiva), import-from-justificante, approval-
staleness detection, post-submission reconciliation against AEAT's
authoritative PDF, and encrypted persistence of drafts, amendments,
and remote filing-history blobs.

#### Per-file functional inventory (24 files including subdirectories)

| File | LOC | Tag |
| --- | --- | --- |
| `__init__.py` | 366 | orchestration façade (`build_draft`, `validate_draft`) |
| `_schema.py` | 195 | domain records (`FilingDraft`, `FilingValue`, `FilingValidationFinding`, `FilingApprovalBasis`, etc.) |
| `_protocols.py` | 132 | runtime-checkable Protocols |
| `_builder.py` | 51 | abstract base class `FilingBuilder` |
| `_validator.py` | 417 | validation rules + 390↔303 reconciliation |
| `_review.py` | 448 | approval lifecycle — **deepest cross-domain importer** (financial + formulas + models) |
| `_complementaria.py` | 367 | amendment models + orchestration (mixed) |
| `_import.py` | 244 | justificante → FilingDraft glue |
| `_errors.py` | 42 | exception hierarchy |
| `runtime.py` | 127 | profile + schema-provider wiring (glue) |
| `testing.py` | 93 | test-double helpers |
| `_repository.py` | 299 | `FilingDraftRepository` — FINANCIAL-class encrypted store |
| `_complementaria_repository.py` | 270 | `FilingAmendmentRepository` — AUDIT-class store |
| `_history_repository.py` | 282 | `FilingHistoryRepository` — **misplaced**: persists `WireFilingHistory` (owned by `aeat.application.sync`) |
| `_builders/__init__.py` | 51 | builder registry + dispatcher |
| `_builders/modelo_130.py` | 296 | M130 IRPF advance-payment builder |
| `_builders/modelo_303.py` | 308 | M303 IVA quarterly builder |
| `_builders/modelo_390.py` | 449 | M390 IVA annual + quarterly-sum builder |
| `_builders/_modelo_130_schema.py` | 267 | **Mislocated** — defines `StaticCasillaSchema`, `StaticCasillaCollection`, `StaticCasillaSchemaProvider`, `CasillaSource` used by `runtime.py`, `testing.py`, AND all three builders |
| `_builders/_modelo_303_schema.py` | 136 | M303 static casilla corpus |
| `_builders/_modelo_390_schema.py` | 88 | M390 static casilla corpus |
| `reconciliation/__init__.py` | 48 | reconciliation public API re-exports |
| `reconciliation/_kind.py` | 42 | `FilingDivergenceKind` enum |
| `reconciliation/_schema.py` | 124 | `ReconciliationReport`, `ReconciliationStatus`, `FieldMismatch` records |
| `reconciliation/_reconcile.py` | 255 | pure compare function — **structurally independent**, zero persistence |

#### Per-symbol classification (summary)

- **domain-filing** (~22 symbols): `FilingDraft`, `FilingDraftStatus`,
  `FilingValue`, `FilingValueKind`, `FilingValidationFinding`,
  `FilingFindingSeverity`, `FilingApprovalBasis`, `compute_draft_id`,
  `FilingBuilder`, `FilingAmendment`, `AmendmentKind`,
  `CasillaChange`, `FilingApprovalStaleReason`, `FilingDraftError`
  hierarchy, all reconciliation records, `FilingDivergenceKind`,
  `ReconciliationReport`, `ReconciliationStatus`, `FieldMismatch`.
- **validation** (~3): `FilingValidator`, `apply_validation`,
  `derive_validation_status`.
- **orchestration** (~9): `build_draft`, `validate_draft`,
  `approve_draft`, `unapprove_draft`, `refresh_review_status`,
  `approval_stale_reasons`, `compute_current_approval_basis`,
  `compute_review_checksum`, `build_complementaria`.
- **glue** (~6): `import_filing_from_justificante`,
  `JustificanteImportResult`, `FilingOperatorProfile`,
  `build_runtime_schema_provider`, `filing_profile_from_autonomo`,
  `load_default_filing_profile`.
- **persistence** (3): `FilingDraftRepository`,
  `FilingAmendmentRepository`, `FilingHistoryRepository`.
- **dead/dormant** (4 candidates): `FilingHistoryRepository` (no
  production consumers outside filing/), `utc_now()` (escaped test
  helper), `default_schema_provider` in `_builders/_modelo_130_schema.py`
  (duplicate of `testing.py` version), 3 `migrate_legacy_*_to_repository`
  one-shot helpers.

#### Internal subpackage analysis

**`_builders/`** is partially separated already — per-modelo builders
+ static schemas live here. Two cohesive sub-groups: (a) builder
implementations, (b) static casilla schema corpus. The schema corpus
is **mislocated** — `_modelo_130_schema.py` defines
`StaticCasillaSchema`, `StaticCasillaCollection`,
`StaticCasillaSchemaProvider`, `CasillaSource` that `runtime.py` and
`testing.py` import directly. They're not 130-specific; they're the
project's runtime schema-provider implementation. Until the real
casilla DB lands (#23), these classes function as the project's
canonical schema implementation.

**`reconciliation/`** is the most cohesive part of the package —
zero persistence, zero orchestration, only TYPE_CHECKING imports of
filing's own records and `aeat.domain.justificante`. Its subdirectory
status indicates filing already started lifting it out of the main
namespace.

#### Data flow (8-stage pipeline)

1. Schema resolution — `CasillaSchemaProvider.get_collection(modelo)`
2. Draft construction — per-modelo `FilingBuilder.build()`
3. Validation — `FilingValidator.validate()` + 5 rules
4. Approval — `approve_draft()` snapshots 5 fingerprints
5. Persistence — `FilingDraftRepository.save()` (FINANCIAL envelope)
6. Amendment — `build_complementaria()` (separate AUDIT envelope)
7. Reconciliation — `reconcile(draft, justificante)` (pure compare)
8. History — `FilingHistoryRepository` stores `WireFilingHistory`
   (sync-domain data — see misplacement)

#### External consumers (imports IN)

- `cli/filing/*` — orchestration façade (build_draft, validate,
  approve, complementaria, import).
- `cli/review/*` — approve_draft, unapprove_draft, validate_draft,
  compute_review_checksum.
- `cli/submission/_helpers.py` — refresh_review_status.
- `workflow/_adapters.py` — build_draft, FilingDraft, FilingProfile,
  CasillaSchemaProvider.
- `review/_adapters.py` + `review/_models.py` — FilingDraft,
  FilingValidationFinding (read-only domain records).
- `testing/_synthesize.py` — FilingDraft + value records (synthetic
  fixtures).

`FilingDraftRepository` is consumed by deferred (in-function) imports
from `cli/`, `workflow/`, `review/` — **not re-exported via filing's
public `__init__.py`**.

#### Imports OUT (cross-domain)

Filing imports from EVERY other domain in the project. Specifically:

- `..storage` — Envelope, SensitivityClass, save_encrypted_envelope,
  load_encrypted_envelope, exclusive_file_lock, safe_repository_id,
  PathContainmentError, plus `_resolve_master_key_provider` (the
  de-facto-public underscore-prefixed function).
- `..financial.categories` (CategoryProfile, SpendingCategory,
  CATEGORY_PROFILES_2025) — consumed in `_review.py`.
- `..financial.transactions` (Transaction, TransactionCatalogue) —
  in `_review.py`.
- `..financial.transactions._repository.TransactionCatalogueRepository`
  — **subpackage-private import** in `_review.py`. Boundary
  violation.
- `..formulas` (FiscalPeriod, MissingRulesetError, Quarter,
  get_registry) — in `_review.py`.
- `..models.ModeloCode` — in `_review.py`.
- `..deadlines` (AutonomoProfile, applies_to) — in `runtime.py`.
- `..config.load_settings` — multiple files.
- `..sync.WireFilingHistory` — in `_history_repository.py`. **The
  data type owned by sync, persisted by a filing repository.**
- `..justificante` (Justificante, parse_justificante) — `_import.py`,
  `_complementaria.py`.
- `..submission._models` (SubmittedFiling, SubmissionAttempt,
  SubmissionStatus) — `_import.py` (deferred).
- `..setup._env_writer.load_profile_envelope` — `runtime.py`
  (deferred).
- `.._paths.resolve_record_json_path` — `_complementaria.py`.

`_review.py` is the deepest cross-domain consumer (financial +
formulas + models simultaneously). This concentrates the cross-
domain orchestration in one file.

#### Hidden coupling (5 critical)

1. **`FilingHistoryRepository` persists a sync-domain type** —
   misplacement (see Section 9-equivalent below).
2. **Static schema corpus is shared kernel** —
   `_builders/_modelo_130_schema.py` is the canonical location for
   `StaticCasillaSchema` and friends, used by `runtime.py`,
   `testing.py`, AND the other two builders.
3. **`_review.py` lru_cache on transaction catalogue** — process-
   level cache keyed on file mtime; tests must invalidate by file
   touch.
4. **All 3 repositories import `_resolve_master_key_provider`
   privately** from `aeat.adapters.persistence.storage._encrypted_columns` — known de-
   facto public per audit 4; renamed during storage move.
5. **Deferred-import cycle pattern** between `__init__.py`,
   `_import.py`, `_complementaria.py`. Intentional but ordering-
   sensitive.

#### Repository placement findings

**`FilingDraftRepository`**: persists `FilingDraft` (filing-owned
type). Stays with filing. ✓
**`FilingAmendmentRepository`**: persists `FilingAmendment` (filing-
owned type). Stays with filing. ✓
**`FilingHistoryRepository`**: persists `WireFilingHistory` — type
owned by `aeat.application.sync`. **Should move to `aeat.application.sync`**.

#### Domain mapping (multi-destination split)

The audit produces a 4-destination split (within filing) plus one
out-of-package move:

| Sub-cluster | Files / symbols | Destination |
| --- | --- | --- |
| Filing domain records | `_schema.py`, `_protocols.py`, `_builder.py`, `_errors.py`, the 3 amendment data models from `_complementaria.py`, plus `reconciliation/` (independent subpackage) | `domain/filing/` |
| Per-modelo builders + static schema corpus | `_builders/` (the entire subdirectory) — but the shared `StaticCasillaSchema` / `CasillaSource` machinery promotes to `domain/filing/_schemas.py` (or kept inside builders/ with documented public role) | `domain/filing/builders/` |
| Validation rules | `_validator.py` | `domain/filing/_validator.py` (or fold into core domain) |
| Filing repositories | `_repository.py`, `_complementaria_repository.py` | **See layering tension below** |
| Orchestration / use cases | `__init__.py` orchestration content, `_review.py`, orchestration parts of `_complementaria.py`, `_import.py`, `runtime.py`, `testing.py` | `application/filing/` |
| **Out-of-package move** | `_history_repository.py` | `application/sync/_history_repository.py` (or `domain/sync/_history_repository.py` per project pattern). Misplacement fix. |

#### Destination validation

- Original heat-map destination: `application/filing/` (single).
- **Audit revises**: split between `domain/filing/` (records,
  protocols, builders, validator, reconciliation, repositories) and
  `application/filing/` (orchestration, use cases, glue) — plus
  the out-of-package move of `_history_repository.py` to sync.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (4,465 LOC).
- `[CONFLATE]` — **CONFIRMED**: bundles domain records + per-modelo
  builders + validation + orchestration + glue + 3 repositories
  (one of which is misplaced). The `_review.py` cross-domain
  concentration (financial + formulas + models) is the most acute
  conflation site.

#### Layering tension surfaced (project-wide question)

**This is a load-bearing finding.** The project has an established
pattern (audit 2 surfaced) that per-domain `_repository.py` lives
WITH its domain. But:

- The ADR's import-boundary contract says `domain/` must NOT import
  from `adapters/`.
- Filing's `_repository.py`, `_complementaria_repository.py` import
  heavily from `aeat.adapters.persistence.storage` (envelope I/O, encrypted columns,
  errors, lock).
- Placing them in `domain/filing/` violates the layered contract.
- Placing them in `adapters/persistence/filing/` breaks the project
  pattern and changes how every domain-with-repository is laid out.

Three options:

- **(A) Loosen domain rules**: permit `domain/` to import from
  `adapters/persistence/storage/` (treat persistence as quasi-
  foundational, similar to how `core/` is). Honest about the
  current pattern.
- **(B) Strict hexagonal split**: define repository protocols in
  `domain/<name>/_protocols.py`, place implementations in
  `adapters/persistence/<name>/`. Bigger refactor; affects every
  domain (rental, filing, justificante, sync, submission,
  workflow).
- **(C) Repositories as application-layer**: move all per-domain
  repositories to `application/<name>/_repository.py`. Less
  conventional but compatible with the ADR's import rules.

**Audit recommendation**: Option (A). Reasons: the project pattern
is established and consistent; the layering compromise is
documented and limited to repository files; (B) is a substantial
refactor that would require new protocol definitions for every
domain; (C) makes repositories cohabit with use cases which is
awkward when use cases come and go but persistence is durable.

**Affects**: audit 2 (rental) project-convention claim needs an
update. Audit 4 (storage) claim about repositories living in
domain needs the same caveat.

#### Boundary violations

- **`_review.py` imports `TransactionCatalogueRepository` from
  `aeat.domain.financial.transactions._repository`** — subpackage-private
  import, not via the public `__init__.py`. Boundary violation;
  fix during the financial.transactions audit.
- **`FilingHistoryRepository` lives in filing but persists sync-
  domain type**. Misplacement.

#### Public-API contract impact

- `aeat.application.filing` re-exports a substantial public surface (~25
  symbols); all callers updated to new canonical paths in the Step 7 keystone PR.
- `FilingDraftRepository`, `FilingAmendmentRepository` — currently
  consumed via deferred imports from outside; not in `__init__.py`
  `__all__`. After move, the public-import path becomes
  `aeat.domain.filing.FilingDraftRepository` (or whatever
  destination wins per layering tension).
- `FilingHistoryRepository` — moves to `aeat.application.sync`; consumers (only
  tests today) update accordingly.

Feeds the ADR public-surface table.

#### Naming clarity

- `filing` is **clear**.
- `_complementaria.py` mixes data models + orchestration —
  filename does not indicate the duality. After split: data models
  → `domain/filing/_schema.py` (merged in or separate); orchestration
  → `application/filing/_complementaria.py`.
- `_modelo_130_schema.py` housing project-wide schema-provider
  classes is misleading. Rename or relocate the shared kernel.

#### Dead code candidates (4)

- `FilingHistoryRepository` — no production consumers outside
  `filing/` (tests only).
- `utc_now()` in `__init__.py` — escaped test helper exported in
  `__all__`; no external consumers.
- `_builders/_modelo_130_schema.py:default_schema_provider` —
  duplicate of `testing.py` version; appears unused.
- 3 `migrate_legacy_*_to_repository` functions — one-shot migration
  helpers with no CLI exposure.

Verify each before removal during execution.

#### Open questions surfaced

- **Layering tension** (per-domain repositories) — load-bearing
  decision; affects every audit so far. Pick (A), (B), or (C).
- **Static schema corpus relocation** — the canonical schema-
  provider implementation lives in
  `_builders/_modelo_130_schema.py`. Promote to a top-level
  domain module or accept the misnomer until the real casilla DB
  (#23) lands.
- **`_history_repository.py` move target** — `aeat.application.sync` is the
  correct domain, but does the move happen now or in a follow-up?
  Recommendation: in this restructure, since it's a 282-LOC file
  consumed only by tests.

#### Verdict

`splits-into-2-domains-plus-1-out-of-package-move`.

**Rationale**: clean split between `domain/filing/` (records,
protocols, builders, validator, reconciliation, repositories) and
`application/filing/` (orchestration, use cases, glue). Plus the
misplacement fix moving `_history_repository.py` to sync.
Surfaces a project-wide layering tension that affects multiple
prior audits and needs a single decision before execution.

### `aeat.entrypoints.cli` (audit 6, 2026-04-30) — structural-survey pass

#### Functional one-liner

`cli/` is the single user-facing command-line surface for the
entire `aeat` package: it composes every sub-domain's Typer app
into one root `app` object, enforces shared transport conventions
(JSON output contract, log-level routing, exit codes, TTY
detection, error decoration), and wires the entry point
`aeat = "aeat.entrypoints.cli:app"` declared in `pyproject.toml`. It is a
pure dispatch / presentation layer with no business logic of its
own; all logic lives in domain packages.

#### Composition (root app)

The root `app` in `cli/__init__.py` (252 LOC) registers:

- **2 direct commands**: `doctor`, `bootstrap` (inconsistent with
  every other module which uses `app.add_typer`).
- **34 sub-typers + 1 hidden audit app**: covering every domain in
  the project (auth, browser, casillas, deadlines, filing,
  financial, formulas, justificante, llm, manual, modelos,
  normatives, oauth, portals, profile, review, rental, run,
  sanitize, schema, secrets, security, sede, setup, sheets,
  submission, sync, vat, workflow, audit, docs, drive, cloud,
  attachments, categories).

#### Inventory shape

- **57 flat `.py` files** at top of `cli/`: 1 `__init__.py` + 19
  source entry-points + 9 private helpers + 1 cross-package test
  fixture (`_live.py`) + 27 test files.
- **21 sub-directories** under `cli/`:
  - 19 with content (auth, browser, deadlines, filing, financial,
    justificante, llm, modelos (shim), portals (shim), profile,
    rental, review, run, sanitize, sede, submission, sync,
    workflow, audit).
  - 2 empty (inbox, status — already on the DELETE list).

Top-level source LOC is ~5,200 (flat) + ~10,800 (nested) ≈ 16,000
LOC total. Flat-level total source files (excluding tests) totals
~4,100 LOC of entry-points + ~700 LOC of private helpers.

#### Cohesion clusters identified at flat top level

1. **Setup / Provisioning / Infrastructure** (~3,013 LOC):
   `bootstrap.py` (194), `oauth.py` (148), `setup.py` (225),
   `doctor.py` (1,140), `cloud.py` (164), `secrets.py` (205),
   `security.py` (937). **No nested sub-directory exists** for
   this cluster. Largest cluster by LOC.
2. **Google Workspace / GSuite helpers** (~952 LOC): `drive.py`,
   `sheets.py`, `docs.py`, `cloud.py` (overlap), plus 3 `_*_helpers.py`.
   **No nested sub-directory** exists.
3. **Financial / Taxonomy** (~464 LOC): `attachments.py`,
   `categories.py`, `vat.py`. **`cli/financial/` sub-dir DOES
   exist** (1,598 LOC). The 3 flat files are inconsistent with the
   sub-dir's organisation — partial-migration smell.
4. **Corpus / Reference Data / Verify** (~655 LOC): `manual.py`,
   `normatives.py`, `casillas.py`, `schema.py`, `formulas.py`.
   `formulas.py` is an 11-LOC shim. `modelos/` and `portals/`
   (sub-dirs) are similar shims.
5. **Cross-CLI Shared Infrastructure** (private, ~856 LOC):
   `_errors.py`, `_exit_codes.py`, `_log_levels.py`, `_schemas.py`,
   `_tty.py`, `_context.py`, `_observability.py`, `_live.py`.
   Genuine cross-CLI primitives.

#### Outlier files

- **`doctor.py` (1,140 LOC)** — the LARGEST flat-level source file,
  2.5× larger than next largest (`security.py` at 937). Implements
  health-check logic inline rather than delegating to a
  `cli/doctor/` sub-package.
- **`security.py` (937 LOC)** — second largest. Master-key
  rotation, corpus integrity manifest, KDF migration. No nested
  `cli/security/` sub-dir exists.
- **`_live.py` (147 LOC)** — cross-package test fixture imported by
  6 test files OUTSIDE `cli/` (in browser, casillas, financial,
  justificante, sede, workflow tests). Behaves like a conftest
  helper, not a CLI module. Misplaced.

#### Test-naming inconsistency at flat top level

Two patterns coexist:

- `_test_*.py` (13 files) — underscore-prefixed, shadows source
  basename.
- `test_*.py` (14 files) — pytest-canonical, names after the area
  under test.

Both are collected (per `pyproject.toml` `python_files = ["test_*.py",
"_test_*.py"]` — confirmed by audit 2). No apparent rule governs
which pattern is applied. The `_test_*` pattern appears older;
`test_*` files are more recent additions. **Not a project
restructure decision** — but worth flagging in project-conventions
section as a inconsistency to either standardise or document.

#### Direct-command vs sub-typer registration

`doctor` and `bootstrap` are registered as direct commands on the
root app. Every other module uses `app.add_typer(name=...)` even
when the sub-app has only one command (e.g. `attachments`,
`oauth`, `manual`). This is an inconsistency in the registration
mechanic. Resolution at restructure time: either convert all to
`add_typer` (uniform) or document the direct-command pattern as
intentional for "operator-utility" commands.

#### Dead code / placeholder candidates

- **`inbox/` and `status/` empty sub-directories** — confirmed
  empty (no `.py` files). Already flagged for `DELETE`.
- **`_live.py` misplacement** — file is fine, location is wrong;
  move to `tests/_helpers/live.py` or merged into a top-level
  `conftest.py` mechanism. Not dead, but architecturally
  misplaced.

#### External consumers

CLI is consumed by:

- `aeat.core.observability._replay.py` — `from ..cli import app`
  (deferred); the only production consumer of the root app outside
  cli.
- ~15 test files across multiple sub-packages — most pull
  `_live.py` symbols (cross-package test fixture) or use
  `cli.<sub>.app` for end-to-end tests.

CLI is otherwise self-contained — no domain module imports from
cli. The dispatch direction is one-way: cli → domains.

#### Imports OUT

Reaches across every first-level domain: `auth`, `config`,
`financial`, `casillas`, `normatives`, `manuals`, `schema`,
`models`, `formulas`, `setup`, `observability`, `storage`,
`security`, `env_io`, `i18n`, `errors`. This is correct for an
entry-points layer.

#### Domain mapping — internal cli reorganisation

The audit produces a flat-level reorganisation plan. CLI itself
moves to `entrypoints/cli/` (per ADR). Within `cli/`:

| Current flat file/cluster | Proposed home | Rationale |
| --- | --- | --- |
| `bootstrap.py`, `oauth.py`, `setup.py` | New `cli/setup/` sub-dir | Group setup-cluster commands; mirror the existing pattern. |
| `doctor.py` (1,140 LOC) | New `cli/doctor/` sub-dir | Split the 1,140-LOC monolith into per-check sub-modules. |
| `secrets.py`, `security.py` | New `cli/security/` sub-dir (with `secrets.py` as its own file inside) | Group security-cluster; split `security.py` per command (rotate, manifest, kdf-migrate). |
| `cloud.py` | Either `cli/setup/` (as a setup helper) OR new `cli/gsuite/` (if grouping GSuite) | Judgment call; cloud has setup-flavoured semantics. |
| `drive.py`, `sheets.py`, `docs.py`, plus `_drive_helpers.py`, `_sheets_helpers.py`, `_docs_helpers.py` | New `cli/gsuite/` sub-dir | Group all Google Workspace API helpers; helpers ride along. |
| `attachments.py`, `categories.py`, `vat.py` | Move INTO existing `cli/financial/` sub-dir | Consistent with where `cli/financial/` already lives. Resolves the partial-migration smell. |
| `formulas.py` (11-LOC shim) | Convert to `cli/formulas/__init__.py` (1-file sub-dir) | Match the `modelos/` and `portals/` shim-subdir pattern. |
| `manual.py`, `normatives.py`, `casillas.py`, `schema.py` | Stay flat OR new `cli/reference/` sub-dir | Judgment call. They're all reference-data CLIs. |
| `_errors.py`, `_exit_codes.py`, `_log_levels.py`, `_schemas.py`, `_tty.py`, `_context.py`, `_observability.py` | Stay flat (project shared infra) OR move to `cli/_infra/` sub-dir | The `_` prefix already marks them private; flat is fine. Subdir would tidy. |
| `_live.py` (147 LOC) | Move OUT of `cli/` to `tests/_helpers/` or a `conftest.py` mechanism | Not CLI code; cross-package test fixture. |
| `inbox/`, `status/` empty subdirs | DELETE | Empty placeholders. |

#### Destination validation

- Original heat-map destination: `entrypoints/cli/` (single).
- **Audit revises**: `entrypoints/cli/` with internal sub-
  reorganisation. The top-level `cli/` itself stays as `entrypoints/cli/`.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (~16,000 LOC total, ~4,100 of which is
  flat-level). Internal split designed.
- `[CONFLATE]` — **CONFIRMED**: 5 cohesion clusters at flat top
  level, plus the partial-migration smell (financial files split
  between flat and nested).

#### Public-API contract impact

`aeat.entrypoints.cli:app` is the single public entry point per `pyproject.toml`.
Internal reorganisation does NOT change this — the `app` symbol
keeps its location at `aeat.entrypoints.cli:app`. Internal moves change only
how `__init__.py` composes the sub-apps, not the public surface.

`_live.py` move OUT of cli/ would require updating ~6 test files
across packages. Routine. Recommend doing as part of the rollout.

#### Naming clarity

- `cli` is **clear**.
- `doctor.py` is clear but the file is too large for a single
  surface; sub-directory will telegraph the split.
- `_live.py` is unclear — name doesn't telegraph "test fixture for
  live tests". Rename during move.

#### Dead code candidates

- **`inbox/` and `status/`** — already flagged for DELETE.
- **`_live.py` location** — not dead, but architecturally
  misplaced. Move out of cli.

#### Open questions surfaced

- **Where does `cloud.py` belong?** GSuite cluster or setup
  cluster? Has setup-flavoured semantics but uses the same auth
  primitives as drive/sheets/docs. **Recommendation**: GSuite
  cluster — keeps Google-API-touching files together.
- **`_live.py` destination outside cli/** — `tests/_helpers/` or
  some other location? Project's test-infrastructure home isn't
  defined in the ADR yet. **Recommendation**: put under a project-
  level `tests/_helpers/` or `tests/conftest_helpers/` directory.
- **Test-naming inconsistency** — `_test_*.py` vs `test_*.py` at
  flat level. Standardise OR document. Not a restructure decision
  but a project-conventions cleanup.
- **Direct-command vs sub-typer registration inconsistency** —
  cosmetic but worth resolving during the cli reorganisation.

#### Verdict

`splits-into-N-internal-sub-dirs-plus-1-out-of-package-move`.

**Rationale**: the cli/ split is largely about *consolidating* the
flat top level into existing or new sub-directories matching the
already-established sub-dir pattern. The reorganisation is
mechanical — most files have an obvious destination. The two
genuinely-architectural decisions are (a) where `cloud.py` fits and
(b) what to do about `_live.py`. The 1,140-LOC `doctor.py` needs
its own internal split design as part of the move. Empty
placeholders confirmed for DELETE. Project-conventions issues
(test naming, registration mechanic) flagged separately.

### `aeat.adapters.outbound.llm` (audit 7, 2026-04-30)

#### Functional one-liner

`llm/` is a self-contained async LLM gateway: it dispatches prompts
to external provider APIs (Anthropic, OpenAI, Gemini, local
Ollama), caches responses on disk in a content-addressed store,
logs usage to daily JSONL files, and packages a higher-level
translation use case on top of that gateway.

#### Per-file functional inventory (16 files, ~1,615 LOC)

| File | LOC | Verdict |
| --- | --- | --- |
| `_models.py` | 271 | mixed — DTOs for all 4 axes (outbound + persistence + domain-prompt + application) |
| `_cache.py` | 249 | persistence-cache |
| `_client.py` | 178 | outbound-client (composition root) |
| `_translator.py` | 174 | application-translator |
| `_usage.py` | 138 | persistence-cache |
| `_providers/anthropic.py` | 78 | outbound-client |
| `_providers/openai.py` | 83 | outbound-client |
| `_providers/gemini.py` | 88 | outbound-client |
| `_providers/local.py` | 69 | outbound-client |
| `_providers/base.py` | 63 | outbound-client (protocol + DTOs) |
| `_providers/fake.py` | 45 | infra (test fixture) |
| `_providers/__init__.py` | 19 | glue |
| `__init__.py` | 73 | glue (public-surface re-exports) |
| `_pricing.py` | 35 | infra |
| `_errors.py` | 34 | infra |
| `_prompts.py` | 18 | domain-prompt |

#### Per-axis breakdown

- **outbound-llm** (~620 LOC): all `_providers/`, `LLMClient`,
  `LLMRequest`, `LLMResponse`, all exceptions, `LLMProvider` enum.
- **persistence-cache** (~440 LOC): `LLMCache`, `CachedEntry`,
  `CacheKey`, `CacheStats`, `UsageRecorder`, `UsageRecord`,
  `UsageSummary`.
- **application-translator** (~210 LOC): `Translator`,
  `BulkTranslator`, `Translation`.
- **domain-prompt** (~50 LOC): `PromptRegistry`, `PromptDefinition`,
  `render_prompt`.
- **infra** (~70 LOC): `estimate_cost_usd`, exception base,
  `_FakeAdapter`.

#### Placement question (R1 #3 cold-review) — RESOLVED

Cold-reviewer R1 #3 argued: "`adapters/persistence/llm/` has no
coherent home in hexagonal architecture — LLM is either an outbound
adapter (calls a remote service) or a domain-layer concern, not
persistence."

**Audit verdict — R1 was right**:

- The 4 provider adapters + `LLMClient` are unambiguously outbound.
- The `LLMCache` + `UsageRecorder` are persistence-side adjuncts
  that *support* the outbound concern, not a primary persistence
  responsibility.
- The architectural identity of the module is "the gateway that
  calls external LLM services" — outbound.

**Decision**: `llm/` moves from `adapters/persistence/llm/`
(initial heat-map proposal) to `adapters/outbound/llm/`. The cache
and usage modules ride along inside `llm/` as internal sub-modules
(`adapters/outbound/llm/_cache.py`, `adapters/outbound/llm/_usage.py`)
even though they're persistence-shaped — the cohesion is within
`llm/`, and the only consumer (CLI) binds to all four axes
together.

#### Storage cross-domain coupling (acknowledged)

`_cache.py` and `_usage.py` import `..storage` symbols
(`SensitivityClass`, `redact_structured`, `default_rules_for_class`,
`exclusive_file_lock`, `fsync_parent_dir`) via deferred imports
inside method bodies. The deferral is justified in inline comments
as avoiding Alembic plugin-discovery on import. This is an
**acknowledged cross-domain coupling** — `llm/` is an outbound
adapter that uses the storage layer's redaction and locking
primitives. After audit 4's CORE-LEAK promotions, several of these
imports become `from ..core.redaction import ...` and
`from ..core.locks import ...` (cleaner, less Alembic-coupled).

#### External consumers (imports IN)

**Single external consumer**: `cli/llm/__init__.py` — imports
`LLMCache`, `LLMClient`, `LLMRequest`, `PromptRegistry`,
`Translator`, `UsageRecorder`. Binds to ALL four axes
simultaneously. No other module in `src/aeat/` imports from
`aeat.adapters.outbound.llm`.

This is a key signal: **no consumer pulls the outbound side
without the cache/usage side or vice versa**. The CLI is the only
caller and it uses everything together. The 4-axis split is
internal cohesion, not external surface separation.

#### Hidden coupling (5)

1. **`LLMClient` ↔ `LLMCache` ↔ `UsageRecorder` lifecycle** —
   client always writes both stores; not independently switchable
   at the call site.
2. **`PromptRegistry.seeded()` hard-codes "translation_v1"
   reference in `Translator`** — silent `KeyError` if seed key
   changes.
3. **`BulkTranslator` reaches into `client.settings`** — fragile
   two-level traversal; breaks if `Translator` uses an
   `LLMClient` implementation without `.settings`.
4. **`UsageRecorder` raises `LLMCacheError` for I/O failures** —
   semantic mismatch (usage append failure ≠ cache failure). Hint
   that the error hierarchy needs an `LLMUsageError`.
5. **`_pricing.py` rate table ↔ `_client._default_model()`
   identifier coupling** — tables must stay in sync; no
   compile-time link.

#### Domain mapping

- **Single destination, internally rich**: `adapters/outbound/llm/`
  with internal sub-modules. The 4-axis split is INTERNAL to
  `llm/`, not split across destinations.
- Pragmatic rationale: the CLI is the only consumer and binds to
  all axes; cross-destination surfaces would force the CLI to
  import from 4 places. Internal cohesion preserves the gateway-
  pattern shape.

#### Destination validation

- Original heat-map destination: `adapters/persistence/llm/` (low
  confidence; flagged for audit per R1 #3).
- **Audit revises**: `adapters/outbound/llm/` (single, internally
  organised by axis).

#### Flag resolution

- `[MONO]` — **CONFIRMED** (1,615 LOC source).
- `[CONFLATE?: external client + local cache + usage tracking;
  client is not really persistence]` — **PARTIALLY CONFIRMED**:
  the conflation IS real (4 axes) BUT the cohesion holds because
  the only consumer (CLI) uses all axes together. Resolution: keep
  together; clarify destination from persistence to outbound.

#### Public-API contract impact

- `aeat.adapters.outbound.llm` `__all__` exports 23 symbols. Hard-cutover:
  all callers updated to new canonical paths in the Step 7 keystone PR.
- The single consumer (`cli/llm/__init__.py`) updates its relative
  imports from `..llm` to `..adapters.outbound.llm` — mechanical.

Feeds the ADR public-surface table (no externally-documented
public contract beyond what cli consumes).

#### Dead code candidates (3 new from this audit)

- **`_FakeAdapter` published in `__all__`**: leading underscore
  signals private, but it's in `__init__.py` `__all__`. Test
  fixture leak onto public surface. Same pattern as
  `auth._providers.describe_certificate_provider` (audit 3) and
  `WorkspaceLockedError` test-only usage (audit 1).
  **Recommendation**: remove from `__all__`; keep as private test
  helper.
- **`ProviderRequest` in `__all__` but no external consumers**:
  internal wire type for provider adapters; the CLI doesn't
  import it. Either keep public for future direct-adapter use or
  remove from `__all__`. Remove for now.
- **Stale `__pycache__/_i18n_compat.cpython-*.pyc`**: source file
  removed but `.pyc` lingers. Build artefact, not real dead code;
  cleared on next clean build.

These feed the dead-code workstream Phase 1.

#### Open questions surfaced

- **Internal axis split inside `llm/`**: should `_cache.py` and
  `_usage.py` move to `_persistence/_cache.py` and
  `_persistence/_usage.py` sub-package within `llm/`? Adds clarity;
  costs one nesting level. Recommendation: yes, internal sub-
  packaging by axis (`_outbound/`, `_persistence/`,
  `_application/`, `_domain/`). Optional refinement.
- **`_models.py` conflates DTOs for all 4 axes**: 271 LOC mixing
  outbound DTOs, persistence DTOs, prompt DTOs, translation DTOs.
  Could split into per-axis model files, but the current
  flatness is small enough that the cost-benefit is low.
- **`PromptRegistry.seeded()` placeholder prompts**:
  `casilla_extract_v1` and `manual_rule_extract_v1` are seeded but
  unreachable until issues #23/#25 land. Not dead, just dormant —
  flag for the project board.
- **`UsageRecorder` raising `LLMCacheError`**: semantic mismatch.
  Add `LLMUsageError` to the exception hierarchy at restructure
  time; out of scope otherwise.

#### Verdict

`single-destination-internal-cohesion-confirmed`.

**Rationale**: cold-review R1 #3 is upheld in spirit — `llm/`
moves to `adapters/outbound/llm/`, NOT `adapters/persistence/llm/`.
Internal 4-axis structure is preserved as cohesive sub-modules
because the only consumer binds to all axes together. 3 dead-code
candidates surfaced. 5 hidden-coupling findings logged for future
deep audit.

### `aeat.adapters.inbound.sanitizer` (audit 8, 2026-04-30)

#### Functional one-liner

`sanitizer/` takes a raw AEAT justificante PDF, strips every PII-
bearing surface (dynamic, metadata, struct-tree, thumbnails),
token-replaces cleartext PII in content streams against an
operator-supplied `TokenMap`, and writes out a byte-stable
sanitised PDF that can be committed as a regression-test fixture
without affecting the text layout the deep-extractor parses
against. It is a **fixture-preparation tool**, not part of
runtime data flow.

#### Per-file functional inventory (10 source files, 1,774 LOC)

| File | LOC | Verdict |
| --- | --- | --- |
| `_records.py` | 434 | pure-redaction (record layer) — frozen pydantic records for input + output + per-category replacement validators |
| `_streams.py` | 318 | pure-redaction (text-show operand rewriter) |
| `_dynamic.py` | 250 | pure-redaction (per-surface dynamic-PII scrubbers) |
| `_pipeline.py` | 246 | pure-redaction (8-step orchestration: refuse-if-signed, strip dynamic, rewrite streams, scrub metadata, save deterministically) |
| `_metadata.py` | 168 | pure-redaction (DocInfo + XMP scrubbing) |
| `__init__.py` | 78 | glue (public-surface re-exports) |
| `fixtures.py` | 79 | infra (compile-time SHA-256 allowlist of committed sanitised fixtures) |
| `_errors.py` | 75 | infra (exception hierarchy) |
| `_determinism.py` | 73 | infra (byte-stable save flags) |
| `_structtree.py` | 53 | pure-redaction (drop StructTreeRoot + MarkInfo) |

#### Per-symbol classification (high-level)

- **pure-redaction** (~17 symbols): `sanitize_pdf`,
  `apply_token_map_to_pdf`, all 8 `strip_*` functions, 2 `scrub_*`
  functions, `drop_struct_tree`, `SanitizationResult`, `Replacement`,
  `ScrubbedSurface`, `SanitizationWarning`, `DeterminismFlags`.
- **incoming-data-handling** (~10 symbols): `TokenMap` and 9
  `*Replacement` subtypes. These define operator-supplied input
  shape; "incoming" is the operator's PII data, not external-
  service data.
- **infra** (~6 symbols): `SANITIZER_VERSION`, `SANITIZED_SHAS`,
  exception hierarchy, save-flag helpers.
- **dead** (0): none — every public symbol is consumed by the CLI.

#### Data flow

Pure transformation. Input: `bytes | Path` + `TokenMap`. Output:
`SanitizationResult` (sanitised bytes + SHA-256s + audit log).
No filesystem I/O inside `sanitize_pdf` itself (CLI wrapper writes
the file). 8-step in-process pipeline: hash-source → refuse-if-
signed → strip-dynamic → drop-thumbnails/outlines/struct-tree →
rewrite-streams → scrub-metadata → save-deterministically →
return-result. Stateless, no network, no DB.

#### `[CONFLATE?]` FLAG IS A FALSE ALARM — CLEARED

**Initial heat-map flag**: "imports `financial` AND `justificante`
— might be a hidden connector".

**Audit verdict**: NO. The flag traced the wrong layer. The audit
confirms:

- `sanitizer/` **does NOT import `aeat.domain.justificante` anywhere in
  source**. Zero source-file references. The flag was tripped
  because the CLI layer (`aeat.entrypoints.cli.sanitize`) imports both
  `aeat.adapters.inbound.sanitizer` AND `aeat.domain.justificante` — which is correct CLI
  behaviour (CLI orchestrates the two).
- `sanitizer/` **DOES import `aeat.domain.financial.invoices._validators
  .validate_spanish_tax_id`** (single function, used by
  `NifReplacement._validate_synthetic_nif` to enforce the same
  checksum rule as production parsers). This is **utility reuse**,
  not connector orchestration.

The sanitizer is a pure PDF transformation module. It needs the
shape of `TokenMap` (its own record) and reuses one Spanish tax-
ID checksum validator. It is NOT aware of justificante records or
any financial domain logic.

**Lesson for the audit methodology**: the `[CONFLATE?]` flag from
import-graph analysis can fire on the WRONG layer when a CLI
sub-module imports two domain modules. Future audits using
import-graph signals to flag CONFLATE? must verify which layer
holds the cross-import.

#### Destination question (architectural)

The heat-map proposed `adapters/inbound/sanitizer/`. Audit
challenges this:

**Argument that sanitizer is NOT inbound**:
- Inbound adapters translate external data sources into domain
  models. Sanitizer does NOT produce a domain model — it produces
  sanitised PDF bytes for fixture use.
- Sanitizer's primary purpose is fixture preparation for
  regression testing — not consumption of external data.
- The data flow is bytes-in → bytes-out with an audit record;
  this is a TRANSFORMATION TOOL, not a data adapter.

**Argument that sanitizer IS reasonably placed in inbound**:
- It operates on incoming PDFs (raw → sanitised).
- The user-facing CLI surface is `aeat sanitize ...` — Kent or
  developer can run it on uploaded PDFs.
- Functionally adjacent to `_pdf_import` (also under `inbound/`).

**Audit recommendation**: KEEP at `adapters/inbound/sanitizer/`
for pragmatic alignment with `_pdf_import` (`adapters/inbound/pdf/`
under the new layout). The "tool, not adapter" purist argument is
correct in DDD vocabulary but creates a `tools/` bucket that
nothing else needs. The trade-off is a slight stretch of "inbound"
to mean "incoming-PDF tooling" rather than "external-data
adapter".

This is a **judgment call** — the user may prefer to:
- (A) accept the inbound placement (audit recommendation; lowest
  restructure cost),
- (B) introduce a `tools/` or `devtools/` top-level bucket (more
  architecturally honest; opens question of what else belongs
  there — sanitizer alone may be insufficient justification),
- (C) place under `core/sanitizer/` as cross-cutting infrastructure
  (the redaction primitives ARE related to `core/redaction/` from
  audit 4 — possibly the right home).

#### External consumers (imports IN)

**Single external consumer**: `cli/sanitize/__init__.py` imports
14 sanitizer symbols (the entire CLI-facing surface). No other
consumers. Test files inside the package import internal symbols.

#### Imports OUT (cross-domain — 3 imports total)

| Import | Source file | Purpose |
| --- | --- | --- |
| `..financial.invoices._validators.validate_spanish_tax_id` | `_records.py:18` | Pure NIF checksum validator (utility reuse) |
| `..errors.AeatError` | `_errors.py` | Standard error base |
| `..logging.get_logger` | `_pipeline.py` | Standard logging |

`validate_spanish_tax_id` is the SECOND audit-finding identifying
this same import as a cross-domain leak (audit 4 found
`_master_key.py` doing the same thing). Reinforces the
recommendation to relocate `validate_spanish_tax_id` to
`core/identity/` or similar shared location.

#### Hidden coupling

- `_records.py` is the dependency hub — every private module
  imports from it; it has zero intra-package imports (other than
  the cross-domain validator).
- `_pipeline.py` imports `fixtures` as `_fixtures` (private
  alias) — tests mocking `SANITIZED_SHAS` must patch
  `_pipeline._fixtures.SANITIZED_SHAS` not `fixtures.SANITIZED_SHAS`.

#### Domain mapping

- **Single destination** (per audit recommendation):
  `adapters/inbound/sanitizer/`. Internal cohesion is high; no
  internal split needed beyond what already exists.

#### Destination validation

- Original heat-map destination: `adapters/inbound/sanitizer/`
  with `[CONFLATE?]` flag.
- **Audit revises**: `adapters/inbound/sanitizer/` (recommended;
  user may override per (B)/(C) options above). `[CONFLATE?]` flag
  CLEARED (false alarm).

#### Flag resolution

- `[MONO]` — **CONFIRMED** (1,774 LOC source). Internal cohesion
  is high; no internal split required.
- `[CONFLATE?: imports `financial` and `justificante`]` —
  **CLEARED**. False alarm; sanitizer does not import
  `justificante` and the `financial` import is a single-function
  utility reuse.

#### Public-API contract impact

- `aeat.adapters.inbound.sanitizer` `__all__` exports 22 symbols.
- Single consumer (`cli/sanitize`) updates relative imports —
  mechanical.
- No documented public-API contract beyond what CLI consumes.

#### Naming clarity

- Module name `sanitizer` is **clear** at module level.
- Symbol names clear (`TokenMap`, `NifReplacement`, etc.).

#### Dead code candidates

**None**. Every public symbol is imported by the CLI; every
private function is called by `_pipeline.py`. This is one of the
cleanest modules audited so far.

#### Open questions surfaced

- **`validate_spanish_tax_id` placement** (cross-cutting utility,
  imported by both `aeat.adapters.persistence.storage._master_key` and
  `aeat.adapters.inbound.sanitizer._records`): move to `core/identity/` or similar.
  Already flagged in audit 4; this audit reinforces.
- **Destination question** (sanitizer as inbound vs tool vs
  core): user judgment call between pragmatic alignment and
  architectural honesty.
- **`fixtures.SANITIZED_SHAS` registry mechanism**: currently a
  Python literal frozenset. If fixture count grows large, switch
  to a JSON sidecar or filesystem-walk approach. Out of scope for
  restructure.

#### Verdict

`single-destination-clean-no-split-needed`.

**Rationale**: this is one of the cleanest modules audited so
far. No internal conflation, no dead code, single external
consumer, single destination. The `[CONFLATE?]` flag was a false
alarm caused by tracing the wrong layer. The destination question
is a stylistic judgment (inbound vs tool); recommendation is to
keep at `adapters/inbound/sanitizer/` for pragmatic alignment.

#### Methodology lesson

The `[CONFLATE?]` flag fired because the initial inventory's
import-graph heuristic counted `aeat.entrypoints.cli.sanitize.__init__.py`'s
imports of both `aeat.adapters.inbound.sanitizer` AND `aeat.domain.justificante` as a
sanitizer-side conflation. Future inventories using import-graph
signals to flag CONFLATE must verify the import lives in the
flagged module, not in a downstream consumer.

### `aeat.domain.schema` (audit 9, 2026-04-30)

#### Functional one-liner

`schema/` owns the end-to-end pipeline that fetches BOE Orden
ministerial PDFs, parses their annex into typed pydantic IR
records (`Casilla`, `Modelo`), persists those records as diff-
friendly JSON, and provides runtime formula evaluation and period
validation over the same IR — all from a single subpackage
surface.

#### Per-file functional inventory (8 source files + testing.py, ~1,774 LOC)

| File | LOC | Verdict |
| --- | --- | --- |
| `_boe_extractor.py` | 488 | extraction (PDF parser, regex heuristics, IR factory) |
| `_models.py` | 481 | domain-ir (frozen pydantic IR, formula AST, validation rules, `evaluate`, `validate_period_for_modelo`) |
| `_fetch.py` | 372 | extraction (httpx streaming + SHA-256 + host allowlist + `BOE_ORDEN_SOURCES` table) |
| `_cache.py` | 121 | infra (atomic JSON persistence) |
| `__init__.py` | 104 | glue (public-surface re-exports) |
| `testing.py` | 70 | infra (reportlab fake PDF builder; test-only) |
| `_enums.py` | 63 | domain-ir (4 closed StrEnums) |
| `_errors.py` | 48 | infra (exception hierarchy) |
| `_extractor.py` | 27 | glue (`Extractor` Protocol — possibly dead, no production callers) |

#### CONFLATE FLAG CONFIRMED — clean unidirectional split

Two distinct concerns separable at file-level boundary:

- **Extraction** (~860 LOC): `_fetch.py` (372) + `_boe_extractor.py`
  (488). Inbound from BOE; build-time / operator-triggered only.
- **Domain IR** (~544 LOC): `_models.py` (481) + `_enums.py` (63).
  Pure typed records + runtime evaluation; no I/O.

Plus shared infra (`_cache.py`, `_errors.py`, `_extractor.py`,
`__init__.py`).

**Critical finding**: extraction is invoked ONLY by
`cli/schema.py`'s `refresh` and `show` commands. Runtime consumers
(sync layer's `SchemaLoader` protocol) consume IR-only via cache
reads — they never invoke the extractor. **Extraction is a build-
time concern; IR is a runtime concern.**

The dependency direction is unidirectional: extraction → IR. The
IR does not call the extractor. This means the split is
mechanically clean.

#### Coupling to resolve at split

1. `_boe_extractor.py` imports private `_collect_refs` from
   `_models.py` — promote to a shared module-private utility or
   keep the cross-file private import (acceptable given
   unidirectional dep).
2. `FetchedSchemaSource` (in `_fetch.py`) inherits from
   `_StrictFrozenModel` (a private pydantic base in `_models.py`)
   — promote to a shared `_base.py` OR duplicate the config dict
   (cheap; pydantic config dicts are small).
3. `_BOE_REF_RE` regex is duplicated between `_cache.py` and
   `_fetch.py` (documented intentional dedup) — could be
   consolidated to `core/identity/` or `domain/schema/_patterns.py`.

#### External consumers (imports IN)

- **`cli/schema.py`** — full pipeline (extraction + IR + cache).
  10 symbols imported.
- **`sync/_protocols.py`** — `SchemaLoader` is a STRUCTURAL
  protocol with NO hard schema import; consumes IR-compatible
  shape via `load_modelo_from_cache`. Read-only.
- No other consumers.

The consumer graph confirms the split: the only consumer that
needs extraction is the operator-CLI `refresh` command. Every
other consumer reads the IR cache.

#### Imports OUT (cross-domain)

- `..errors.AeatError` (standard)
- `..i18n` (Translatable, TranslationError, require_authoritative)
- `..models` (ModeloCadence, ModeloCode, get_modelo) — domain
  upward dep
- `..portals` (Portal, get_portal) — domain upward dep
- `..config` (PROJECT_ROOT, Settings, load_settings)
- `..logging`
- third-party: `pdfplumber` (lazy-imported inside method),
  `httpx`, `reportlab` (testing only), `pydantic`

No dependencies on `aeat.domain.casillas`, `aeat.domain.financial`,
`aeat.domain.justificante`, etc. Cleanly upward-only.

#### Domain mapping (split into 2 destinations + infra)

| Sub-cluster | Files | Destination |
| --- | --- | --- |
| Extraction | `_fetch.py`, `_boe_extractor.py` | `adapters/inbound/schema/` |
| Domain IR | `_models.py`, `_enums.py` | `domain/schema/` |
| Cache (infra) | `_cache.py` | `domain/schema/_cache.py` (cache reads are runtime — go with IR) OR shared `domain/schema/` |
| Errors | `_errors.py` | `domain/schema/_errors.py` (per project pattern: per-domain `_errors.py` rides with the domain) |
| `Extractor` protocol | `_extractor.py` | `domain/schema/_protocols.py` if kept; possibly DELETE (no production callers) |
| `testing.py` | `testing.py` | `domain/schema/testing.py` (test-only fixture builder) |

The split honours the audit-7-confirmed pattern: when extraction
is a build-time concern and IR is a runtime concern, extraction
goes to inbound and IR goes to domain.

#### Destination validation

- Original heat-map destination: `domain/schema/` (single, with
  `[CONFLATE?]` flag).
- **Audit revises**: 2-destination split — extraction to
  `adapters/inbound/schema/`, IR + cache + errors to
  `domain/schema/`.

#### Flag resolution

- `[MONO]` — **CONFIRMED** (1,774 LOC source).
- `[CONFLATE?: extraction is inbound, IR is domain — possible
  split into `adapters/inbound/schema-extraction/` +
  `domain/schema/`]` — **CONFIRMED with concrete split design
  produced**.

#### Public-API contract impact

- `aeat.domain.schema` `__all__` exports 33 symbols.
- After split: all callers of `aeat.domain.schema` updated to the new canonical paths; the module
  extraction symbols from `aeat.adapters.inbound.schema` and IR
  symbols from `aeat.domain.schema`.
- Single CLI consumer updates relative imports — mechanical.
- `sync/_protocols.py` SchemaLoader is structural; no rewrite.

Feeds the ADR public-surface table.

#### Naming clarity

- Module name `schema` is **clear**.
- `BoeOrdenExtractor` clear (BOE = Boletín Oficial del Estado).
- `Modelo`, `Casilla` use AEAT-canonical Spanish; consistent with
  rename rationale.

#### Dead code candidates (4 new from this audit)

- **`Extractor` Protocol (`_extractor.py`, 27 LOC)** — exported in
  `__all__` but zero production callers. Either keep as forward-
  looking abstraction (planned for non-BOE backends) or delete.
  **Recommendation**: keep IF the project plans non-BOE
  extractors; otherwise inline + delete.
- **3 reserved `SchemaSource` enum slots**: `PORTAL_HTML_PROBE`,
  `MANUAL_LLM_DRAFT`, `XSD_WIRE`. `SchemaProvenance` validator
  actively rejects them. Placeholders for future backends.
  **Recommendation**: keep — they're placeholder enum values, not
  dead code in the conventional sense; deletion would require
  alignment on which non-BOE backends will land.
- **`_BOE_REF_RE` regex duplication** between `_cache.py` and
  `_fetch.py` — not dead but a maintenance hazard. Consolidate
  during split.
- **`validate_period_for_modelo` `AD_HOC == ANNUAL` branch
  collision** — not dead but a latent correctness issue. Out of
  scope for restructure; flag for project board.

These feed the dead-code workstream Phase 2 (rides with the
schema split).

#### Open questions surfaced

- **`Extractor` Protocol fate** — keep (forward-looking) or delete
  (currently dead). Project decision.
- **Reserved SchemaSource enum slots** — same question.
- **`SchemaProvenance._reject_unimplemented_sources` validator**
  encodes extraction-backend completeness inside the IR. Either
  the IR knows about backends (current design) or extraction
  registers itself (cleaner separation but more machinery).
- **Cache placement** — `domain/schema/_cache.py` (audit
  recommendation; cache is read at runtime) vs
  `adapters/persistence/schema/` (more architecturally honest if
  cache writes are persistence). Audit recommends domain because
  cache READS dominate; cache WRITES are extraction-side and
  could go in `adapters/inbound/schema/_cache_writer.py`.

#### Verdict

`splits-into-2-clean`.

**Rationale**: extraction (build-time, 1 consumer) and IR
(runtime, structural-protocol consumers) are separable at clean
file boundaries with unidirectional dependency. Split is
mechanically simple — move 2 files to inbound, keep 4 in domain,
update `__init__.py` public exports. The CONFLATE? flag is
RESOLVED with concrete split design.

### `aeat.application.workflow` (audit 10, 2026-04-30)

**One-liner**: single linear orchestrator driving Kent's end-to-end
preflight pipeline (sync → next-obligation → inbox → already-filed-
probe → build-draft → validate → preflight). Permanently read-only.

**Verdict**: `[CONFLATE]` flag **DOWNGRADED to `[MONO]` only**.
The audit confirms this is ONE use case, not multiple. The high
cross-domain in-degree is structural (composition root). The 7
stages share state and produce one `WorkflowResult`. Already
internally axis-clean: domain (`_models.py`) / application
(`_engine.py`, `_protocols.py`) / persistence (`_persistence.py`) /
glue (`_adapters.py`). Stays at `application/workflow/` (single
destination).

**Significant findings**:

- **Forward-ref circular dep**: `__init__.py` does monkey-patch +
  `model_rebuild()` at import time to break a cycle between
  `workflow._models.WorkflowStage` and `browser._site_health.SiteHealthAlert`.
  Proper resolution: pick a domain owner for `SiteHealthAlert`
  (either it stays in browser and embeds `WorkflowStage` via
  TYPE_CHECKING, or it moves to workflow). Fragile import-order
  contract.
- **Concurrency hazard**: `WorkflowEngine` holds 5 mutable run-
  context fields (`_run_tax_id`, `_run_started_at`, etc.) set on
  entry, cleared on exit. Currently safe (CLI uses one engine per
  command) but races if engine is ever shared across asyncio
  tasks.
- **Hidden cast violation**: `FilingDraftBuilderAdapter` casts
  `AutonomoProfile` → `FilingProfile` and `FilingDraft` →
  `FilingDraftLike` — silent structural-coupling failure if
  fields ever diverge.
- **`_default_financial_inputs_provider` filesystem probe**:
  reads `transactions.envelope.json` existence at `default_engine()`
  call time → conditional lazy import. Hidden side effect.

**Dead-code candidates (3 new)**:

- `WorkflowResult.submission_id` — tombstone field, engine always
  writes `None`. Schema-migration compatibility only.
- `SubmissionPreflightError` re-export inconsistency — listed in
  `_adapters.__all__` but NOT in `__init__.__all__`. Effectively
  unreachable from `aeat.application.workflow.<symbol>`.
- `_FinancialInputsProvider` Protocol inside `_adapters.py` —
  internal-only; could be inlined or moved to `_protocols.py` for
  consistency.

**Open questions**:

- `SiteHealthAlert` ownership (workflow or browser)?
- `WorkflowEngine` concurrency contract — single-instance-only or
  thread/task-safe?
- `submission_id` tombstone retention window?
- `FinancialThenJsonInputsProvider` placement — workflow adapter
  or filing/financial-side?

### `aeat.domain.justificante` (audit 11, 2026-04-30)

**One-liner**: parses AEAT justificante PDFs into a frozen domain
record, persists records in an encrypted store, and makes one
outbound browser call to AEAT's Sede electrónica to verify a CSV.

**Verdict**: `[CONFLATE]` (was `[CONFLATE?]`) **CONFIRMED — three
distinct architectural concerns bundled**.

**Three concerns**:

1. **Inbound parser** (~640 LOC): `_parser.py`, `_extract.py`
   (436), `_parsers/` backends (78), `_schema.py` (79).
2. **Outbound encrypted persistence** (~263 LOC): `_repository.py`.
3. **Outbound remote AEAT connector** (~155 LOC): `_verify.py` —
   Playwright browser automation against
   `sede.agenciatributaria.gob.es` for live CSV verification.

**Split design** (3 destinations + 1 domain):

| Sub-cluster | Destination |
| --- | --- |
| Parser pipeline (`_parser`, `_extract`, `_parsers/`) | `adapters/inbound/justificante/` |
| Domain record + errors (`Justificante`, `JustificanteParserBackend`, error hierarchy) | `domain/justificante/` (or stay with parser per layering decision) |
| Encrypted persistence (`_repository.py`) | `domain/justificante/_repository.py` per project pattern (or `adapters/persistence/justificante/` per strict hexagonal — same layering tension) |
| Remote AEAT verification (`_verify.py`) | **`adapters/outbound/aeat/verify/`** (new sub-cluster) — sibling to `auth/`, `browser/`, `sede/`, `export/` |

**Significant findings**:

- **`_verify.py` is a remote-AEAT connector mistakenly housed in an
  inbound subpackage**. It does a live Playwright call to AEAT's
  Sede electrónica — structurally equivalent to a status-check or
  sede-walker connector. Should join the `outbound/aeat/` cluster.
- **`_resolve_master_key_provider` private import** — same
  pattern as audits 4/5. De-facto public API.
- **`JustificanteRepository` is not in public `__all__`** but is
  imported via the private path
  `aeat.domain.justificante._repository.JustificanteRepository` by
  `filing._test_integration_wave4`. Public-API contract leak.
- **Deferred `load_settings` import in `_parser.py`** is motivated
  by a circular import (`aeat.core.config` imports
  `JustificanteParserBackend`). The domain record is entangled
  with config at package boundary.
- **`PYMUPDF` backend is a stub that raises** — listed in public
  enum, raises unconditionally when invoked.

**Dead-code candidates (2 new)**:

- `JustificanteParserBackend.PYMUPDF` — exported, but raises on
  any call. Either implement or remove from public API.
- `migrate_legacy_justificantes_to_repository` — one-shot helper,
  no production callers (matches the 3 filing migration helpers
  pattern from audit 5).

**Open questions**:

- Where does `_verify.py` go? Recommendation:
  `adapters/outbound/aeat/verify/` (new sibling). Alternative:
  fold into `sede/`.
- The `domain/justificante/` placement vs persistence depends on
  the LAYERING TENSION decision (audit 5).

### `aeat.adapters.outbound.aeat.sede` (audit 12, 2026-04-30)

**One-liner**: read-only Playwright driver for the authenticated
AEAT sede; walks two filing-listing surfaces (Mis Expedientes tree
+ Consultar declaraciones presentadas register), reads
notifications inbox, parses HTML to typed records, downloads
justificante PDFs.

**Verdict**: `[MONO]` confirmed. **3 internally-independent sub-
surfaces** (Expedientes ~777 LOC, Declarations 667 LOC,
Notifications 425 LOC) sharing only `_errors.py` and 2 schema
types. No internal split required NOW (all 3 surfaces under 700
LOC); future-readiness sub-packaging if surfaces grow:
`sede/expedientes/`, `sede/declarations/`, `sede/notifications/`.

**Findings**:
- `_declarations.py` (667 LOC) and `_notifications.py` (425 LOC)
  EACH conflate schema + parse + walker in one file (the
  expedientes surface already split these via `_walker` + `_parse`
  + `_schema`). Pre-emptive consistency split optional.
- `_STRICT_FROZEN` config dict duplicated 3x; `_SEDE_BASE` URL
  triplicated. Consolidate.
- `shared_playwright` lives in `_declarations.py` but is a cross-
  surface concern.

**Destination**: `adapters/outbound/aeat/adapters/outbound/aeat/sede/` (stays).

**Dead-code candidates (1 new)**:
- `_walker.fetch_justificante_pdf` — listed in `__all__` but
  unconditionally raises `NotImplementedError`. Superseded by
  `capture_justificante`.

**Open**: timezone correctness (`_parse_presented_at` documents
AEAT timestamps are Europe/Madrid but tags them UTC verbatim).

### `aeat.application.sync` (audit 13, 2026-04-30)

**One-liner**: live-to-local cross-validation engine — fetches AEAT
browser payloads, validates against pydantic wire schemas,
classifies semantic deltas into typed divergence taxonomy, routes
through bounded auto-heal policy.

**Verdict**: `[MONO]` confirmed. **NOT `[CONFLATE]`** — single use
case, but 3 architectural layers (wire / domain / application) in
one flat package. Split warranted:
- `_divergence.py` (221) + `_classifier.py` (204) = 425 LOC of
  pure domain → promote to **`domain/sync/`** (or `domain/divergence/`).
- Everything else stays at `application/sync/` (orchestration +
  boundary).

**Findings**:
- `aeat.application.filing._history_repository` imports `WireFilingHistory`
  from `aeat.application.sync` (audit 5's misplacement). Coordinate when
  `_history_repository.py` moves to sync.
- `BenignRecordStrategy` sets `resolution_state=AUTO_HEALED` on
  BENIGN records despite using `StrategyAction.RECORDED` — naming
  mismatch worth verifying.

**Destination**: split — `domain/sync/` (taxonomy + classifier) +
`application/sync/` (everything else).

**Dead-code candidates (4 new)**:
- `LLMClient` + `LLMRequest` Protocols on `LiveSyncRunner.__init__`
  — stored as `self._llm` but NEVER invoked. Forward-compat.
- `ManualRulesLoader` + `SchemaLoader` Protocols — same pattern;
  4 hollow constructor arguments total.
- `_path_for()` alias in `JsonFileDivergenceRepository` — exists
  for one test only.
- `DivergenceClassificationError` — defined + exported, NEVER
  RAISED.

**Open**: 4 hollow Protocol stubs (LLMClient + 3 others) —
intentional forward-compat or wiring oversight?

### `aeat.application.setup` (audit 14, 2026-04-30)

**One-liner**: tightly-scoped first-run onboarding pipeline —
collects identity + certificate + filesystem preferences, writes
`env/.env` and AES-encrypted `AutonomoProfile` envelope, verifies
result.

**Verdict**: `[MONO]` (size only — 1,312 LOC across 7 files).
**Single use case**, clean internal axis split (domain models /
domain logic / orchestration / infra / IO adapters / ports).
Stays at `application/setup/` (single destination).

**Findings**:
- Boundary leak: `cli/deadlines/_helpers.py` imports
  `..setup._env_writer` privately, bypassing public `__init__.py`.
- `_setup_text()` localises only 1 of 20 prompts — incomplete
  i18n infra at larger scale than current usage.

**Dead-code candidates (3 new)**:
- `SetupOutcome.SKIPPED` — enum value never produced.
- `SetupOutcome.ABORTED_BY_USER` — enum value never emitted by
  wizard (no abort path); only exercised by tests.
- `_setup_text()` + `_t()` — vestigial i18n helper used only for
  one prompt.

### `aeat.core.observability` (audit 15, 2026-04-30)

**One-liner**: cross-cutting run-trace instrumentation — mints
contextvar-scoped `run_id`, emits typed JSONL events via logging
sink, persists redacted traces/events, fingerprints corpus/db/cert
for drift detection, replays recorded CLI invocations.

**Verdict**: `[MONO]` (1,657 LOC source). Single concern, high
cohesion, clean dependency DAG. **DESTINATION CORRECTION**:
the heat map placed observability at `adapters/persistence/observability/`.
The audit recommends **`core/observability/`** (NOT persistence).

**Rationale for `core/`**:
- Consumed by `cli`, `workflow`, `logging`, AND `errors` — not by
  a single adapter; it's cross-cutting infrastructure.
- Mounts on `logging.Handler`, reads `contextvars`, gates CLI
  replay. None are persistence-layer adapter concerns.
- `_store.py` has filesystem I/O but it's storing OWN artefacts
  (not adapting to external persistence).
- Closest analogy: structured-logging middleware (opentelemetry,
  structlog) — typically lives in `core/` in hexagonal layouts.

**Findings**:
- `_replay.py` imports `..cli.app` (deferred) — structural smell.
  Suggests injection point at app startup rather than direct
  cross-layer import.
- `_diagnostic_rules()` is duplicated verbatim in `_sink.py` and
  `_store.py` — extract to `_redaction_rules.py`.

**Dead-code candidates (3 new)**:
- `_test_sink_redaction.py` (underscore-prefixed) — not
  collected by pytest default; coverage duplicates existing
  tests. Likely vestige of a renaming.
- `save_events_append` (public export) — only used by tests; no
  production caller outside the observability package. Demote to
  package-private.
- `_REMOVED_WRITE_FLAG_NAMES` / `_argument_uses_removed_write_flag`
  in `_replay.py` — guards against the removed `no-dry-run` CLI
  flag; becomes unreachable once pre-removal traces age out of
  `var/runs/`.

**Open**: `_replay.py` → `..cli.app` coupling (DI seam vs deferred
import); thread-safety of `run_context` (contextvars don't
propagate across `threading.Thread`).

### `aeat.adapters.outbound.aeat.export` (audit 16, 2026-04-30)

**One-liner**: post-excision read-only audit-record store +
preflight gate + fichero-BOE format library. Two completely
independent halves co-located historically.

**Verdict**: `[MONO]` confirmed. **WEAK COHESION — splits into 2**:

- **Half A** (~700 LOC): `_engine.py`, `_preflight.py`, `_models.py`,
  `_protocols.py`, `_errors.py`, `_repository.py` — submission-
  lifecycle domain (preflight gating, historical record I/O,
  errors, encrypted persistence).
- **Half B** (~3,400 LOC): `_formats/` subtree (19 files) —
  fichero-BOE fixed-width serialiser/deserialiser. Completely
  independent of Half A; shares no imports either way.

**The rename `submission/` → `export/` serves Half B**; Half A
needs its own home.

**Destination split**:
- `_formats/` → `adapters/outbound/aeat/export/` (the actual
  export functionality)
- Half A → `domain/submission/` (submission-lifecycle domain
  records + preflight + repository, per layering-tension pattern)

**Findings**:
- `LiveSubmitForbiddenError` relocation (audit 3 planned to move
  to `core/access_gate/_errors.py`) **NOT yet done** —
  `aeat.adapters.outbound.aeat.auth._gate` still imports it lazily from `aeat.adapters.outbound.aeat.export`.
  The relocation must be coordinated with the rename.
- `SubmissionEngine` still uses legacy `glob("*.json")` reader
  instead of `SubmissionRepository` — two active read paths.
  CLI consumers (`show.py`, `list.py`) bind to the legacy path.
- `_submitters/` is a TOMBSTONE — empty `__init__.py`, asserted
  by `test_submitter_modules_are_absent`. Source files
  (`_contract`, `modelo130`) are confirmed absent; only stale
  `.pyc` artifacts remain. Delete entire directory.

**Dead-code candidates (4 new)**:
- `_submitters/` tombstone directory.
- `SubmissionAttempt.browser_trace_path` field (live-write era;
  no post-excision write path uses it).
- `SubmissionStatus.IN_PROGRESS` + `PENDING` enum values
  (post-excision tombstones; comment "retained for historical
  records" but no current setter).
- `_formats/modelo_130_2025.py` (48 LOC) and
  `_formats/modelo_303_2025.py` (38 LOC) — both stubs delegating
  to 2024 layouts; verify before treating as "complete".

**Open**:
- `_formats/_generate.py` and `_formats/_ingest.py` are tooling
  (DR-spec code generation from BOE PDFs), not runtime — could go
  to a `tools/` subtree.
- `SubmissionEngine` legacy reader vs `SubmissionRepository` —
  which survives the move? Migration wiring missing.

### `aeat.adapters.outbound.aeat.browser` (audit 17, 2026-04-30)

**One-liner**: AEAT Playwright adapter — session/evasion/profile +
site-health classification + smoke-health binary entry point.

**Verdict**: `[MONO]` confirmed. Single Playwright adapter with 3
tightly-coupled concerns. **No urgent split needed** but
`_site_health_parsers.py` (405 LOC, pure Python no-Playwright) is
extractable.

**Findings**:
- **Circular-dep with workflow CONFIRMED** (audit 10). Resolution:
  **move `SiteHealthAlert` from `_site_health.py` to
  `aeat.application.workflow._models`**. The class carries `run_id` and
  `stage: WorkflowStage` fields — semantically a workflow type
  that incidentally references browser-detected health. The
  `model_rebuild()` ritual in `aeat.application.workflow.__init__` is then
  unnecessary.
- After SiteHealthAlert relocates, the `_site_health*` trio
  (`_site_health.py`, `_site_health_parsers.py`,
  `_site_health_probe.py`) is purely HTTP/HTML analysis — could
  promote to `domain/site_health/` if growth justifies.
- `evaluate_response` re-exported from `__init__` but external
  consumers bypass it and import directly from
  `_site_health_parsers`.

**Destination**: `adapters/outbound/aeat/adapters/outbound/aeat/browser/` (stays).
Internal optional sub-packaging deferred.

**Dead-code candidates (3 new)**:
- `EvasionStrategy` Protocol + `PlaywrightStealthEvasion` exported
  in `__init__` but ZERO external consumers. `session.py`
  instantiates `PlaywrightStealthEvasion` internally only. Either
  unexport or keep as forward-looking extension point.
- `run_health_check` / `health.py` (smoke-test binary) — if
  `pyproject.toml` `[project.scripts]` has no entry pointing at
  `health.main`, the file is a maintenance orphan.
- The `evaluate_response` re-export from `__init__` is unused
  (bypassed by direct import from `_site_health_parsers`).

**Open**:
- Move `SiteHealthAlert` to workflow → eliminates the bidirectional
  cycle and the model_rebuild ritual entirely. Decision needed.

### Survey batch (audit 18, 2026-04-30) — remaining 22 modules verified

Compact verification pass over all remaining modules. Each
confirmed at proposed destination unless flagged below.

#### Inventory correction — initial heat map was systematically undercounting

The initial heat-map inventory used a non-recursive file count
that **missed nested subdirectories** within each subpackage.
Several modules are much larger than the heat map showed:

| Module | Heat-map LOC | Actual LOC (survey) | Note |
| --- | --- | --- | --- |
| `formulas` | 1,431 | ~12,500 (84 files) | Per-modelo rulesets in nested subdirs |
| `financial` | 193 | ~11,250 (59 files) | Track-B subdirs (transactions, invoices, attachments, categories, vat, aggregation, usage_ratios, etc.) |
| `declaracion` | 818 | ~3,330 (35 files) | Per-modelo extractor subdirs |
| `models` | 1,219 | ~2,660 (33 files) | Per-modelo metadata files |
| `portals` | 944 | ~2,230 (51 files) | Per-portal entries |
| `profile` | 365 | ~1,614 (top-level + assets + inventory subpackages) | Sizeable subpackages |
| `borrador` | 399 | ~613 (11 files) | mild undercount |

**Total `src/aeat/` source code** is closer to **~100,000+ LOC**
(vs the heat-map estimate of ~61,500). Proportional bucket
distribution unchanged; restructure scope is bigger absolutely
but destination choices unaffected.

**Methodology lesson**: future inventories must recurse all
subdirs and count `_test_*.py` AND `test_*.py` patterns. Current
heat-map LOC values are LOWER BOUNDS, not exact.

#### LAYERED-ARCHITECTURE VIOLATIONS surfaced (3 new)

These are upward dependencies that violate the ADR's import-
boundary contract. They must be untangled before the layout move:

1. **`casillas` → `aeat.entrypoints.cli`** — domain module imports from CLI
   entrypoint layer. Inversion.
2. **`financial` → `aeat.entrypoints.cli`** — same pattern.
3. **`profile.assets` and `profile.inventory` → private internals
   of `formulas._rulesets.modelo_100`** (`_amortization`,
   `_inventario`, `_ccaa`). Cross-domain import of PRIVATE
   submodules. Resolution: extract a public API in
   `domain/formulas/` for amortization tables and CCAA registry;
   profile imports the public surface.

These join already-flagged violations (audit 4, 5, 8). **Total: 6
layered-architecture violations** flagged across audits.

#### Per-module survey results

**Domain cluster** — all destination-confirmed:

- `formulas` (84 files, ~12,500 LOC) — domain catalogue. **Audit 19**: stays at `domain/formulas/`. 2 NEW layered violations (verification + cli/filing private bypass to 4-level deep). 4 dead-code candidates (modelo_202_2025 partial, modelo_200_corporate_tax unregistered, modelo_200_2026 placeholder, modelo_100_summary_2025 partial coverage).
- `manuals` (7 files, ~1,370 LOC) — no surprises.
- `models` (33 files, ~2,660 LOC) — rename `models` → `modelos`.
- `deadlines` (7 files, 997 LOC) — self-contained.
- `casillas` (4 files, ~494 LOC, smaller than heat-map). **Surprise**:
  imports `aeat.entrypoints.cli` (upward inversion).
- `normatives` (7 files, 656 LOC) — no surprises.
- `portals` (51 files, ~2,230 LOC).
- `profile` (~1,614 LOC). **Surprise**: assets/inventory import
  private formulas internals.
- `testing` (4 files, 591 LOC) — synthetic fixtures.

**Inbound cluster** — all destination-confirmed:

- `_pdf_import` (5 files, 488 LOC) → `pdf/` rename.
- `borrador` (11 files, 613 LOC).
- `declaracion` (35 files, ~3,330 LOC).
- `identity` (2 files, 212 LOC).
- `financial` (59 files, ~11,250 LOC). **Surprise**: ~58× larger
  than initial heat-map estimate. **AUDIT 20 CORRECTION**: the
  reported `aeat.entrypoints.cli` upward-inversion was a FALSE POSITIVE —
  exhaustive grep finds no such import in current source.

**Connectors** — all destination-confirmed:

- `review` (7 files, 844 LOC).
- `verification` (4 files, 361 LOC).

**Entrypoints**:

- `mcp` (3 files, 298 LOC) — destination confirmed.

**Core**:

- `i18n` (1 file, 169 LOC). Project-wide.
- `config.py` (856 LOC). Project-wide.
- `logging.py` (295 LOC). **Note**: deferred `config` import
  breaks a `config → auth → logging` cycle — must preserve.
- `env_io.py` (167 LOC).
- `_paths.py` → `core/paths.py` (67 LOC).
- `_json_contract.py` → `core/json_contract.py` (165 LOC).
- `_click_context.py` → `core/click_context.py` (45 LOC).

#### Survey verdict

All 22 modules **destination-confirmed**. 3 NEW layered-
architecture violations. 1 inventory-correction finding. No new
dead-code candidates. No new misplacement candidates.

### `aeat.domain.formulas` (audit 19, 2026-04-30) — deep structural-survey

**One-liner**: sandboxed deterministic formula-evaluation engine
holding official AEAT casilla arithmetic for 11 modelos × 2024–2026.
The largest module in the codebase: 12,515 LOC across 84 files.

**Verdict**: `[MONO]` confirmed. **NOT `[CONFLATE]`**. Single
coherent domain catalogue — all 11 modelos share the same
`Ruleset` / `Engine` / `RulesetRegistry` machinery. Stays at
`domain/formulas/` (single destination); internal split is
optional. The `_rulesets/modelo_100/` subpackage (64 files,
~10k LOC) is the natural seam if internal split ever happens.

**Findings**:
- Single architectural violation already known (audit 18):
  `_rulesets/modelo_100/anexo_d_ledgers.py` imports `profile.assets`
  + `profile.inventory`. Resolution: extract public surface in
  `domain/formulas/` for amortization tables + CCAA registry; or
  relocate the bridge file to `profile/`.
- **2 NEW layered-architecture violations** discovered:
  - `verification/_verify.py` imports `formulas._ledger.Discrepancy`
    + `formulas._ruleset.Ruleset` (private bypass).
  - `cli/filing/__init__.py` imports `formulas._period`,
    `formulas._registry`, `formulas._rulesets` (private subpackage),
    AND `formulas._rulesets.modelo_100._ccaa.compute_cuota_autonomica_general`
    (4-level deep private bypass).
- Total **layered violations now 8** across all audits.

**Dead-code candidates (4 new)**:
- `modelo_202_2025.py` — partial scope (only 2025; no 2024 / 2026
  equivalents). Intentional gap per docstring (#305 sub-EPIC).
  Not dead, just incomplete coverage.
- `modelo_200_corporate_tax.py` — unregistered helper, not in
  `__all__`, only consumed by `modelo_200_*` files. Effectively
  internal but invisible to registry.
- `modelo_200_2026.py` — placeholder cloned from 2024; 2026 BOE
  not yet published. Not dead but speculative.
- `modelo_100_summary_2025.py` (244 LOC) — registered as
  `MODELO_100_SUMMARY_2025`, consumed by `cli.filing` directly,
  but no 2024 or 2026 equivalents.

**Open**:
- `_rulesets/__init__` eager-loads all 32 rulesets at import — lazy
  registration could improve startup.
- `compute_cuota_autonomica_general` should be promoted to public
  `formulas` surface to eliminate the 4-level deep CLI bypass.
- `anexo_d_ledgers.py` relocation to `profile/` or a `bridges/`
  layer.

### `aeat.domain.financial` (audit 20, 2026-04-30) — deep structural-survey

**One-liner**: Track-B Transaction Data Pipeline (TDP) — ingests
bank exports, normalises to `RawTransaction`, classifies (rule-
based + LLM subprocess), maps to AEAT casillas via spending
categories + VAT rules, aggregates into Modelo inputs, persists
all artefacts encrypted. **Second-largest module: 11,250 LOC,
59 files**.

**Verdict**: `[MONO]` confirmed. **HEAVILY `[CONFLATE]`** — 8
sub-packages each conflate 2–4 layers (domain + persistence +
application + outbound). The audit-18 single-destination
classification is **wrong**.

**THREE major findings**:

1. **`aeat.entrypoints.cli` upward-inversion was a FALSE POSITIVE** — audit
   18 reported it but exhaustive grep finds no such import.
   The `cli` direction is correct (`cli` imports `financial`,
   not the reverse). Possibly a stale-source artefact at audit-18
   time. Removing this from the layered-violations list — total
   drops to 7.
2. **Financial requires 8-destination split** (massive
   restructure of this subpackage):

| Sub-package | LOC | Destination |
| --- | --- | --- |
| `providers/` (CSV/OFX/XLSX/PDF parsers) | 1,356 | `adapters/inbound/financial/providers/` |
| `transactions/` (4-axis conflation) | 1,944 | **4-way split**: models → `domain/transactions/`; `_repository` → `domain/transactions/_repository.py` (per layering carve-out); `_service` → `application/transactions/`; `_llm` → `adapters/outbound/llm/` (joins existing LLM cluster) |
| `invoices/` (3-axis conflation) | 1,307 | **3-way split**: models + `_validators` → `domain/invoices/`; repository → `domain/invoices/_repository.py`; service → `application/invoices/` |
| `categories/` (pure domain knowledge) | 1,251 | `domain/categories/` |
| `vat/` (largest sub-package; pure regulatory catalogue) | 3,243 | `domain/vat/` (and consider promoting to top-level `aeat.vat` since it has zero coupling to the TDP pipeline) |
| `aggregation/` (application service) | 641 | `application/aggregation/` |
| `usage_ratios/` (model + persistence) | 301 | **2-way split**: model → `domain/usage_ratios/`; service → `domain/usage_ratios/_service.py` (per carve-out) |
| `attachments/` (3-axis conflation) | 1,012 | **3-way split**: models → `domain/attachments/`; `_store` → `domain/attachments/_repository.py`; `_service` → `application/attachments/` |

3. **`transactions/_llm.py` is an outbound adapter embedded in
   a domain-adjacent module** — calls `subprocess.run` on
   `claude`, `gemini`, `codex` CLIs. Belongs in
   `adapters/outbound/llm/` next to the existing LLM module.

**Findings**:
- `validate_spanish_tax_id` cross-domain leak (already known from
  audits 4, 8) — moves to `core/identity/` per decision-grounding
  audit.
- `providers/_base.py` + `_csv.py` import `aeat.core.config.load_settings`
  at module level — couples inbound adapter to application config.
  Better: inject settings at call time.
- `categories/_corpus.py` imports `aeat.domain.manuals` (PDF loader) —
  runtime I/O dependency in domain module. Should separate.
- 4 sub-packages independently implement encrypted-storage pattern
  (transactions, invoices, attachments, usage_ratios). Possible
  shared base.

**Dead-code candidates (2 new)**:
- `transactions/_llm.py:build_prompt()` — explicitly marked "kept
  for backward-compatible imports from earlier drafts/tests"; no
  non-test callers.
- `invoices/_stubs.py` — filename suggests stub. Verify before
  delete.

**Open questions**:
- **`vat/` promotion to top-level `aeat.vat`?** It's 3,243 LOC of
  pure VAT regulatory catalogue with zero coupling to transactions.
  Promoting frees consumers from importing `from financial import vat`
  when they only need VAT rules.
- LLM classifier `subprocess(claude/gemini/codex)` → migrate to
  Anthropic SDK changes adapter boundary.
- Encrypted-storage pattern duplication across 4 sub-packages —
  consolidate?

## Online research validation (audit 21, 2026-04-30)

Validates 4 post-audit decisions against industry-canonical
sources. **All 4 decisions confirmed industry-canonical**, with
varying caveats.

### Decision A — Observability in `core/` (audit 15)

**CONFIRMED CANONICAL.** OpenTelemetry's own architecture explicitly
treats observability as "a cross-cutting concern — a piece of
software which is mixed into many other pieces of software."
OpenTelemetry distinguishes API (cross-cutting public interfaces)
from SDK (the infrastructure layer). The pattern of a cross-
cutting infrastructure module consumed by CLI + workflow + logging
+ errors simultaneously cannot coherently belong to a single
adapter cluster.

Sources:
- OpenTelemetry Python instrumentation docs
- OpenTelemetry specification overview
- Herberto Graça — Explicit Architecture (DDD/Hexagonal/Onion/Clean
  synthesis)
- Szymon Miks — Hexagonal Architecture in Python (`building_blocks`
  module pattern)

### Decision B — `outbound/<provider>/` sub-cluster nesting (audit 3)

**CONFIRMED CANONICAL** with qualification. Grouping adapters by
technology/provider is an explicitly-endorsed practitioner pattern
("I have structured my adapter packages by technology here, so we
have logical cohesion in this corner"). Canonical sources are
neutral on nesting depth — neither flat nor nested is mandated;
both are practiced. No source forbids the nesting; at least one
explicitly endorses it.

Sources:
- "Implementing DDD + Hexagonal Architecture with Go" — explicit
  endorsement of technology-grouping
- Sairyss/domain-driven-hexagon (GitHub) — agnostic to depth
- Herberto Graça — adapters distinguished by primary/secondary +
  port, doesn't forbid technology sub-grouping
- AWS Prescriptive Guidance — flat layout in single-adapter Lambda
  example, not multi-provider

### Decision C — `domain/` → `adapters/persistence/storage/` carve-out (decision-grounding audit)

**CONFIRMED with caveat.** Industry sources explicitly endorse
intentional, documented pragmatic exceptions when full abstraction
exceeds benefit. Sairyss/domain-driven-hexagon: "if the price is
too high to abstract this away, it might be a good decision to
allow some pollution." Herberto Graça: "this is not the end of
the world as long as you do it intentionally and are aware of the
consequences."

**Caveat**: sources draw the line more at the *application layer*
than the *domain layer*. Documented violations are more typically
acceptable in application/service-layer than in domain-layer. The
project's carve-out applies to the domain layer specifically — a
slightly more aggressive position than canonical literature
endorses, but explicitly documented and bounded to the storage
substrate (not technology adapters).

Sources:
- Sairyss/domain-driven-hexagon — explicit endorsement of pragmatic
  pollution
- Herberto Graça — "as long as you do it intentionally"
- Vaadin — "sometimes you have to be pragmatic"
- Developers Voice — warns against cargo-cult hexagonal but
  preserves "domain entities have no outward dependencies" rule

**Action**: ADR's carve-out documentation must explicitly bound
the scope (storage substrate ONLY, not technology adapters) per
the canonical-literature distinction.

### Decision D — `core/identity/` for shared validators (decision-grounding audit)

**CONFIRMED CANONICAL.** This is the textbook Shared Kernel
pattern. Mehmet Ozkaya: "Shared Kernel centralizes [common code]
to minimize the risk of inconsistencies." Conditions for Shared
Kernel use: "incredibly stable concepts" with cross-bounded-context
consumption. A Spanish tax-ID checksum function (legally defined,
unchanged for years, confirmed cross-domain consumers) is a
textbook fit.

Sources:
- Mehmet Ozkaya — Shared Kernel Pattern in DDD
- DEV — Managing Shared Libraries in Hexagonal + DDD
- Herberto Graça — Shared Kernel "contains functionality used
  across multiple bounded contexts"
- Sairyss/domain-driven-hexagon — shared value objects in common
  location

### Online-research summary

| Decision | Verdict | Confidence |
| --- | --- | --- |
| A — Observability in `core/` | CONFIRMED canonical | high |
| B — `outbound/<provider>/` nesting | CONFIRMED with qualification | high |
| C — `domain/` carve-out for storage | CONFIRMED pragmatic-acceptable, with caveat | medium-high |
| D — `core/identity/` Shared Kernel | CONFIRMED canonical | high |

**No decision contradicted by industry research.**

## Refreshed cold-eyes review (audit 22, 2026-04-30)

Two fresh sonnet reviewers given the CURRENT (post-amendment) ADR
text only. Both raised substantive new findings.

### Reviewer 1 (refreshed) — strongest objection

**Headline**: "The repository-pattern carve-out is an uncontrolled
precedent in a high-churn codebase that will erode layering."

**Prior-review concern status** (13 prior concerns):
- 9 ADEQUATELY ADDRESSED
- 4 PARTIALLY ADDRESSED (import-linter contract shape,
  test-marker mixed-destination override count, vault Tier-2
  "revalidated" definition, semver decision point + owner)

**NEW issues surfaced**:
1. **Carve-out enforcement boundary** — without a named registry
   of which `_repository.py` files qualify, import-linter must
   either name 8+ exceptions explicitly OR use a wildcard. The
   wildcard option creates an open door for future repositories
   to inherit the exception silently.
2. **Freeze-window extension policy** — what if layout-move PR
   is not mergeable within 24h?
3. **`WorkspaceLockedError` conflicting dispositions** — public-
   surface table says "verify before final cutover"; dead-code
   Phase 2 list says "rename or delete". Neither gates the other.

**Persuasion path**: add a "Carve-out registry and escalation
policy" appendix that names every qualifying `_repository.py`
file explicitly + skeleton import-linter contract showing how
exceptions are expressed.

### Reviewer 2 (refreshed) — what's still missing

**Headline**: "Acceptance criteria confirm the plumbing compiles
but not that the system still does the right thing for Kent."

**7 gaps surfaced**:
1. **No end-to-end behavioural smoke test acceptance criterion**
   — all 13 acceptance criteria are structural. A mechanical
   import rewrite can pass all of them while silently breaking
   the produce → verify → export pipeline.
2. **Migration model contract** — no explicit statement of whether old paths would be shimmed or hard-cut; resolved as hard-cutover in the ADR.
3. **Carve-out enforcement boundary scope** — same finding as
   Reviewer 1 #1 (convergent).
4. **Python packaging / editable-install / wheel verification**
   — `python -c "import aeat"` confirms in-tree resolution but
   not packaging behaviour.
5. **mypy / pyright clean run not in acceptance criteria** —
   type errors can accumulate silently post-move.
6. **Migration script correctness** — described but no test
   for: relative imports, star imports, TYPE_CHECKING blocks,
   dynamic `importlib.import_module` calls.
7. **No named rollout decision authority** — abort criteria are
   useless without a decision-owner.

**Top 3 required**:
1. End-to-end behavioural acceptance criterion (smoke test).
2. Explicit migration model contract (hard-cutover; resolved in the ADR).
3. Named rollout decision authority.

### Convergent themes (both reviewers)

- **Carve-out enforcement gap** (R1 #1 + R2 #3) — both flagged
  independently; the most acute new issue.
- **Acceptance-criteria gaps**: structural-only (R2 #1, #5)
  versus behavioural validation.
- **Decision authority / ownership** (R1 #5 semver, R2 #7
  rollout) — same gap, different surfaces.

### Triage and ADR amendments to apply (11)

| # | Source | Concern | Amendment |
| --- | --- | --- | --- |
| 22.1 | R1 #1 + R2 #3 | Carve-out enforcement | NEW appendix: "Carve-out registry and escalation policy" — explicit list of qualifying `_repository.py` files + skeleton `import-linter` contract |
| 22.2 | R2 #1 | Behavioural smoke test missing | Add to acceptance criteria: end-to-end pipeline test (produce → verify → export) green in CI |
| 22.3 | R2 #5 | mypy/pyright clean run | Add to acceptance criteria: zero mypy/pyright errors on new layout |
| 22.4 | R2 #6 | Migration script correctness | Add to acceptance criteria: migration-script test fixture covering relative imports + TYPE_CHECKING + star imports + dynamic imports |
| 22.5 | R2 #2 | Migration model contract | Add to public-surface section: explicit hard-cutover policy — every rename or relocation updates all callers in the same change-set as the source move; no backward-compat re-export layer is introduced |
| 22.6 | R1 #5 + R2 #7 | Rollout decision authority | Add to operational contract: named role (project owner) authority to call freeze, declare done, invoke rollback |
| 22.7 | R1 #6 | Tier-2 "revalidated" undefined | Add to vault-supersession: "revalidated" = explicit guardrail unit test passes against new path + audit doc inline-updated |
| 22.8 | R1 #4 | Freeze-window extension policy | Add to transition mechanic: if move PR not mergeable in 24h → freeze extends in 12h increments; agent-slot orchestration informed; rollback considered after 72h cumulative |
| 22.9 | R1 #3 | Mixed-destination test override count | Add to test-marker mechanic: audit produces explicit override list pre-execution; manual-override count is a hard pre-merge gate |
| 22.10 | R2 #4 | Python packaging verification | Add to acceptance criteria: `pip install -e .` succeeds; `pip install dist/*.whl` succeeds; installed wheel exposes new paths |
| 22.11 | R1 #7 | `WorkspaceLockedError` disposition conflict | Resolve to single disposition: keep as test-only fixture; rename to `_TestableAeatError` if kept, OR delete + replace with synthetic test exception. Decision: delete + replace (cleaner) |



These are project-wide conventions identified during per-module
audits that were not visible in the initial shape inventory. They
are not decisions for the restructure to make; they are existing
practice the restructure must respect.

### Colocated-test naming: `_test_*.py` is canonical

`pyproject.toml` configures both `test_*.py` AND `_test_*.py` as
collected test patterns:

```
[tool.pytest.ini_options]
python_files = ["test_*.py", "_test_*.py"]
```

Coverage configuration (`tool.coverage.run.omit`) and Ruff per-
file-ignores explicitly list both patterns. Subpackages using the
`_test_*.py` form: `aeat.domain.rental` (5 files), `aeat.adapters.persistence.storage` (21
files), `aeat.application.filing` (subset), `aeat.entrypoints.cli` (subset).

The `_` prefix signals that the test file is an internal-to-package
unit test (consistent with the project's underscore-private
convention for module names). Both patterns coexist.

**Implication for the restructure**: the move preserves these
patterns; no test file gets renamed by the layout change.

### Per-domain repository pattern

Per-domain `_repository.py` modules sit alongside their domain (not
under `storage/`):

- `aeat.domain.rental._repository` (5 repository classes).
- `aeat.application.filing._repository` + `aeat.application.filing._complementaria_repository`
  + `aeat.application.filing._history_repository`.
- `aeat.domain.justificante._repository`.
- `aeat.adapters.outbound.aeat.export._repository`.
- `aeat.application.sync._repository`.

`aeat.adapters.persistence.storage/` provides the ORM, blob store, crypto, classification,
recovery, redaction, rotation, and secret-store underlying layer.
Domain repositories import from `aeat.adapters.persistence.storage._orm` for row types
and `aeat.adapters.persistence.storage.errors.RepositoryError` for error wrapping.

**Implication for the restructure**: per-domain repositories ride
home with their domain (under `domain/<name>/_repository.py`), not
under `adapters/persistence/`. Only `aeat.adapters.persistence.storage` itself moves to
`adapters/persistence/storage/`.

### CLI sub-package import depth

CLI sub-packages reach into their parent domain via 3-dot relative
imports (`from ...rental import ...`). Inventory greps must include
`from ...<subpackage>` patterns to catch CLI-side consumers.

### Audit cadence note

Each audit produces (a) a per-module verdict + split design, (b)
heat-map updates, (c) ADR public-surface table updates if relevant,
(d) any project-wide conventions surfaced (this section), and (e)
any dead-code candidates identified (the next section).
Convention discoveries propagate to the audit-schema and to all
future audits.

## Dead-code workstream

Consolidated from per-module audits, all candidates verified by
follow-up grep of `src/aeat/` (excluding defining file + colocated
tests) on 2026-04-30. The workstream is phased and rolls out in
lockstep with the restructure.

### Verification methodology

For each candidate:
- Grep `src/aeat/` for any import or reference (excluding the
  defining file and its colocated tests).
- Result categories:
  - **CONFIRMED-DEAD**: zero non-test references.
  - **TEST-ONLY**: only test files reference; not in any
    production code path.
  - **NEEDS-DEEPER-CHECK**: dynamic-resolution risk; pre-merge
    `grep -r '<symbol>' src/` (no exclusions) required.

### Confirmed dead code (verified 2026-04-30)

| Item | From audit | Scope | Verification | Phase | Notes |
| --- | --- | --- | --- | --- | --- |
| `auth._secret_adapters` (entire module) | 3 | module | CONFIRMED — only `_test_secret_adapters.py` references. Wave-2 migration helpers never wired to production. | **Phase 1** | Delete module + colocated test together (~470 LOC). |
| `errors.WorkspaceLockedError` | 1 | symbol (~10 LOC) | CONFIRMED — defined + registered in `_DECLARED_ERROR_CODES`, zero production raise sites. | **Phase 2** (with errors split) | Used as a "convenient concrete `AeatError`" in 4 errors test files. Either rename to `_TestableAeatError` (test-only fixture) or replace with synthetic test exception before delete. |
| `filing.utc_now` | 5 | symbol (~2 LOC) | CONFIRMED — exported in `__all__`, zero external consumers. | **Phase 1** | Escaped test helper. Either move to test fixture or delete from `__all__`. |
| `filing._repository.migrate_legacy_drafts_to_repository` | 5 | function (~70 LOC including helpers) | CONFIRMED — only `_test_repository.py` references. | **Phase 2** (with filing split) | One-shot migration helper. **Verify migration window with project owner** before deletion (in case retain-for-rerun was intentional). |
| `filing._complementaria_repository.migrate_legacy_amendments_to_repository` | 5 | function | CONFIRMED — only colocated tests. | **Phase 2** (with filing split) | Same caveat as above. |
| `filing._history_repository.migrate_legacy_filing_history_to_repository` | 5 | function | CONFIRMED — only colocated tests. | **Phase 2** (rides with `_history_repository.py` move to sync). | Same caveat. |
| `auth._providers.describe_certificate_provider` | 3 | function (~20 LOC) | CONFIRMED — defined + listed in `_providers.__all__`, zero external consumers. | **Phase 1** OR **Phase 2** (with auth split) | Either remove from `__all__` (intentional non-exposure) or delete entirely. Likely an export inconsistency. |
| `filing._builders._modelo_130_schema.default_schema_provider` | 5 | function (~30 LOC) | CONFIRMED — duplicate of `filing.testing.default_schema_provider`. The latter is consumed by tests; the former is unused. | **Phase 2** (rides with static-schema-corpus relocation) | Safe to delete once shared kernel relocates. |
| `llm._FakeAdapter` in `__all__` | 7 | export-list entry | CONFIRMED — leading-underscore symbol exported on public surface; only test files use it. | **Phase 1** | Remove from `__all__`; keep as private test helper. Same export-inconsistency pattern as audit-3's `describe_certificate_provider`. |
| `llm.ProviderRequest` in `__all__` | 7 | export-list entry | CONFIRMED — internal wire type; CLI consumer doesn't import it. | **Phase 1** | Remove from `__all__`; can re-export later if direct-adapter use case lands. |
| `schema._extractor.Extractor` (Protocol) | 9 | class + module (27 LOC) | CONFIRMED — exported in `__all__`, zero production callers. | **Phase 2** (with schema split) OR keep | Project decision: keep IF non-BOE extractors planned, otherwise inline + delete. Currently dormant. |
| `schema._enums.SchemaSource` reserved slots (`PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`, `XSD_WIRE`) | 9 | enum members | CONFIRMED placeholders — `SchemaProvenance` validator actively rejects them. | KEEP (not "dead" in conventional sense) | Placeholder enum values for future backends. Deletion would require alignment on which non-BOE backends will land. Document as forward-looking; don't delete. |
| `schema._BOE_REF_RE` regex duplication (`_cache.py` and `_fetch.py`) | 9 | duplicated definition | CONFIRMED — documented intentional dedup, but maintenance hazard. | **Phase 2** (with schema split) | Consolidate to single home (likely `domain/schema/_patterns.py` or merged into one of the files). Not dead per se; cleanup. |
| Empty subpackages: `corpus/`, `history/`, `inbox/`, `status/` | initial inventory | 4 directories | CONFIRMED — no `.py` source files. | **Phase 2** (with layout move) | Default fate: DELETE. Confirm with project owner before delete in case intended-future-content. |

### Phasing rationale

- **Phase 1 (immediate, before layout move)**: items with zero
  cross-domain coupling and zero risk of dynamic invocation. Ship
  in standalone PRs before the layout-move PR. Candidates:
  `_secret_adapters`, `utc_now`, `describe_certificate_provider`.
  Estimated removal: ~480 LOC + 191 LOC of tests.
- **Phase 2 (with restructure)**: items that ride home with their
  domain's split or move PR. Deletion is folded in as part of the
  move. Candidates: `WorkspaceLockedError` (rides with errors
  split), 3 `migrate_legacy_*_to_repository` helpers (ride with
  filing split / sync move), duplicate `default_schema_provider`
  (rides with static-schema-corpus relocation), 4 empty
  subpackages. Estimated removal: ~110 LOC + 4 directories.
- **Phase 3 (post-restructure)**: none currently. Reserve for
  candidates surfaced by future audits.

### Pre-merge safety check

For every Phase 1 deletion, run `grep -r '<symbol>' src/`
(unrestricted, no `--include` filter — catches `*.toml`, `*.yml`,
docstrings, comments) before merge to catch:

- Dynamic resolution (`getattr`, `__import__`, `importlib`).
- Configuration references (e.g. entry points in `pyproject.toml`).
- Documentation references that should update or stay.

The static-import grep used for verification today does NOT catch
dynamic resolution; the unrestricted final grep is the safety net.

### Cumulative impact

Aggregate Phase 1 + Phase 2 deletions: **~590 LOC of production
code + ~190 LOC of obsolete test code + 4 empty subpackage
directories**. Net code reduction is small (~1% of `src/aeat/`)
but the cohesion improvement is meaningful: 6 dormant migration
helpers + 1 dead module + 1 duplicate function + 4 empty
placeholders that are visual noise in the tree.

### What is NOT in this workstream

- **Symbols flagged for relocation but not deletion** (e.g. the 11
  errors-domain exception classes that move to their domain
  `_errors.py` per audit 1, the 5 storage CORE-LEAK promotions per
  audit 4) are part of the restructure proper, not the dead-code
  workstream.
- **Subpackage-private import boundary violations** (e.g.
  `_review.py` importing `aeat.domain.financial.transactions._repository`
  per audit 5) are layering violations, not dead code.
- **Misplaced files** (e.g. `filing._history_repository.py`
  moving to sync, `cli/_live.py` moving to test infrastructure) are
  relocations, not deletions.

## Open questions / themes

> Cross-cutting observations that don't belong to a single module are
> captured here as they emerge, then carried into the ADR.

### Audit completion verdict (2026-04-30)

**All 39 non-empty modules audited** across 18 audit operations
(17 deep + 1 survey batch covering 22 small/clean modules):

| Audit | Module | Verdict |
| --- | --- | --- |
| 1 | errors | splits-into-5 |
| 2 | rental | clean-MONO + 3 project conventions surfaced |
| 3 | auth | splits-into-5 + 1 delete + 1 CORE-LEAK upgrade |
| 4 | storage | 7-internal + 5 core-promotions |
| 5 | filing | 2-domain + 1 misplacement + LAYERING TENSION surfaced |
| 6 | cli | internal reorg + 1 misplacement |
| 7 | llm | single-destination, persistence→outbound |
| 8 | sanitizer | clean single-destination + CONFLATE? false alarm |
| 9 | schema | splits-into-2 clean (extraction vs IR) |
| 10 | workflow | clean-MONO; CONFLATE downgraded |
| 11 | justificante | 3-destination split + new outbound/aeat/verify/ |
| 12 | sede | clean-MONO with future sub-packaging option |
| 13 | sync | 2-destination (domain + application) |
| 14 | setup | clean-MONO single-destination |
| 15 | observability | persistence→**core** (cross-cutting infra) |
| 16 | submission | 2-destination (domain/submission/ + adapters/outbound/aeat/export/) |
| 17 | browser | clean-MONO; SiteHealthAlert relocation needed |
| 18 | survey-batch (22 modules) | all destination-confirmed; 3 layered violations + inventory correction |

#### Cumulative deliverables

**Destinations finalised**:
- `domain/` cluster: 13 modules (modelos, casillas, manuals,
  normatives, portals, formulas, deadlines, schema, profile,
  rental, filing, justificante, sync, submission)
- `adapters/inbound/` cluster: 8 modules (pdf, borrador,
  declaracion, justificante, identity, sanitizer, schema,
  financial)
- `adapters/outbound/aeat/` cluster: 5 modules (auth, browser,
  sede, verify, export)
- `adapters/outbound/google/` and `adapters/outbound/llm/`
- `application/` cluster: 7 modules (filing, workflow, sync,
  setup, review, verification, auth)
- `entrypoints/` cluster: 2 modules (cli, mcp)
- `core/` cluster: 14 modules (config, logging, errors, i18n,
  env_io, paths, json_contract, click_context, access_gate,
  file_permissions, locks, classification, redaction,
  corpus_manifest, observability)

**ADR layout block** now reflects every audited destination
including the splits.

**Heat-map flag resolution**:
- `[MONO]` count: 21 of 39 non-empty modules confirmed
  monolithic.
- `[CONFLATE]` confirmed: storage, cli, auth, filing, errors,
  justificante, schema, llm (8 modules).
- `[CONFLATE?]` resolved: sanitizer (FALSE ALARM cleared),
  schema (CONFIRMED with split), llm (partially — 4-axis split
  but cohesion holds), workflow (DOWNGRADED to MONO).
- `[CORE-LEAK]` confirmed: auth (`_file_permissions`), storage
  (`_classification`, `_redaction`, `_corpus_manifest`, `_lock`,
  `_path_safety`).

#### Cross-cutting findings (consolidated)

**6 layered-architecture violations** (must untangle before
execution): see "Layered-architecture violations consolidated"
above.

**3 confirmed misplacements** (move during restructure):
- `auth._secret_adapters` — dead in production, deletion
  candidate.
- `filing._history_repository` — persists sync-domain type;
  moves to sync.
- `cli/_live.py` — cross-package test fixture, moves to
  test infrastructure.

**Module-level relocations** (8+):
- `LiveSubmitForbiddenError` from `submission/` to
  `core/access_gate/_errors.py`.
- `AeatLiveReadNotEnabledError` from `auth/certificate.py` to
  `core/access_gate/`.
- `SiteHealthAlert` from `browser/_site_health.py` to
  `workflow/_models.py` (eliminates circular dep + rebuild
  ritual).
- `validate_spanish_tax_id` from
  `financial.invoices._validators` to `core/identity/`
  (resolves 2 violations).
- 5 storage CORE-LEAK promotions to `core/`
  (`classification/`, `redaction/`, `corpus_manifest/`,
  `locks.py`, `path_safety.py`).
- 11 errors-domain exception classes to their domain
  `_errors.py` files (per audit 1).
- Browser Playwright protocols from `auth/_authenticator.py` to
  `outbound/aeat/adapters/outbound/aeat/browser/_protocols.py`.
- `StaticCasillaSchema` / `CasillaSource` from
  `filing/_builders/_modelo_130_schema.py` to a shared kernel.

**Dead-code workstream**: ~21 candidates verified across audits;
~590 LOC of production code + ~190 LOC test code + 4 empty
directories deletable. Phased Phase 1 / Phase 2 plan in the
"Dead-code workstream" section.

**Inventory correction**: total `src/aeat/` source code is
~100,000+ LOC (vs heat-map estimate of ~61,500). The original
inventory tool was non-recursive on nested subdirs.

#### Items requiring user decision before execution

1. **LAYERING TENSION** (audit 5) — per-domain repositories vs
   `domain/` import rule. Three options laid out; affects 7+
   domains. Audit recommends (A).
2. **Sanitizer destination** (audit 8) — inbound (pragmatic) vs
   tools (architecturally honest) vs core (cross-cutting). Audit
   recommends inbound.
3. **`_secret_adapters` deletion** (audit 3) — confirmed dead
   but verify with project owner.
4. **`_submitters/` directory deletion** (audit 16) — tombstone,
   confirmed safe.
5. **Empty subpackage deletions** (`corpus`, `history`, `inbox`,
   `status`) — confirm with project owner.
6. **Reserved `SchemaSource` enum slots** (audit 9) — keep as
   forward-looking placeholders or delete?
7. **`Extractor` Protocol** (audit 9) — keep for future extractors
   or delete?
8. **`SiteHealthAlert` ownership** (audit 17) — move to workflow
   to eliminate circular dep, or keep with browser via
   `model_rebuild()` ritual?
9. **`_FakeAdapter`, `ProviderRequest` `__all__` removal**
   (audit 7) — straightforward Phase 1 cleanup.
10. **Migration helper retention window** (audits 5, 11) — when
    can `migrate_legacy_*_to_repository` helpers be deleted?

#### What this audit did NOT do

- **Pre-emptive code edits** — every audit was read-only.
  Restructure execution is a separate phase.
- **Per-symbol audits within modules** — for the survey-batch
  modules (formulas, financial especially), only file-level
  cohesion was assessed. Pre-execution, per-cluster deep audits
  inside `formulas/` and `financial/` are recommended given their
  size.
- **Validation of every cross-domain import claim** — audits
  flagged imports observed; the move PRs need to verify each
  claim against the actual import statements.

#### Approval-gate progress (per ADR)

- ✅ Condition 1: top-5 monolith split designs (errors, auth,
  storage, filing, cli) folded in.
- ✅ Condition 2: vault contradiction list 100% classified
  across 4 tiers.
- ◯ Condition 3: acceptance-criteria checklist met (deferred to
  execution).
- ◯ Condition 4: abort criteria reviewed (user decision).

**Plus a HARD pre-execution decision pending**: layering tension
(A/B/C). Without that decision, several audit recommendations are
conditional on it.

The restructure is **fully designed end-to-end**. Execution is
ready to plan once the layering tension is resolved.

## Decision-grounding audit (2026-04-30)

The architectural audits surfaced 10 user-decision items. The user
cannot make these decisions on architectural grounds alone — they
need to be **grounded in Kent's user experience and codebase
legibility**, not just coding standards. This section evaluates
each pending decision through three lenses:

- **Kent UX**: does this decision change what Kent can do, see, or
  trust? (per project mandate: "every change answers — what can
  Kent do now that he couldn't before?")
- **Contributor legibility**: does this decision make the
  codebase more or less readable for a new contributor on day one?
  (per DDD's "scream business" + the "ubiquitous language"
  principle the project already half-honours)
- **Coding-standards alignment**: the architectural-purity lens
  the per-module audits already cover.

The recommendation comes from the **synthesis** of all three, not
from one in isolation. Where the lenses conflict, the project's
mandates (Kent is the north star; legibility supports Kent
indirectly via developer velocity) break the tie.

### Decision 1 — LAYERING TENSION (per-domain repositories)

**Three options** (from audit 5, affects 7+ domains):
- (A) Loosen `domain/` import rule to permit
  `domain/<name>/_repository.py` to import from
  `adapters/persistence/storage/`.
- (B) Strict hexagonal — define repository protocols in
  `domain/<name>/_protocols.py`, place implementations in
  `adapters/persistence/<name>/`.
- (C) Repositories as application layer —
  `application/<name>/_repositories.py`.

| Lens | (A) Loosen | (B) Strict hexagonal | (C) Application-layer |
| --- | --- | --- | --- |
| Kent UX | Zero direct impact | Zero direct impact | Zero direct impact |
| Contributor legibility | **HIGH POSITIVE**: a new contributor finds `domain/filing/_repository.py` next to `FilingDraft` — answers "where do filing records live?" in one place. | **NEGATIVE**: `domain/filing/_protocols.py` defines the contract, `adapters/persistence/filing/_repository.py` defines the implementation — two homes, must navigate both. Convention-correct but cognitive overhead. | **AMBIGUOUS**: repository sits next to use cases; new contributor wonders "is the repository a use case or persistence?" |
| Coding standards | Tradeoff: violates layered import rule but documents it as a per-domain-repository carve-out. | Maximally hexagonal-correct. | Less canonical pattern; awkward when use cases come and go but persistence is durable. |
| Project pattern fit | **MATCHES** existing project pattern (audit 2 surfaced; rental/filing/justificante/sync/submission already do this). | Requires inverting every existing repository placement. | Requires inverting every existing repository placement. |

**Audit-grounded recommendation**: **(A) — loosen `domain/` import
rule with a documented carve-out**.

**Rationale**: contributor legibility is the load-bearing lens
here (Kent is unaffected). The project already has the
"per-domain repositories live with their domain" pattern
established — the pragmatic recommendation honours that pattern,
documents the layering compromise explicitly in the ADR's import-
boundary contract, and avoids forcing every domain through a
restructure that adds two-home cognitive load. Kent doesn't
benefit from option B's purity; the contributor velocity of (A)
ships features for Kent faster.

### Decision 2 — Sanitizer destination (`adapters/inbound/sanitizer/` vs `tools/` vs `core/`)

| Lens | (a) inbound | (b) tools | (c) core |
| --- | --- | --- | --- |
| Kent UX | Zero direct impact (Kent uses CLI; CLI sub-app `aeat sanitize` works regardless). | Zero direct impact. | Zero direct impact. |
| Contributor legibility | **POSITIVE**: groups all PDF-handling under `adapters/inbound/` (`pdf/`, `borrador/`, `declaracion/`, `justificante/`, `sanitizer/`). One bucket = "incoming PDFs". | **NEGATIVE**: introduces a new top-level `tools/` bucket for ONE module — feels invented. | **NEGATIVE**: `core/` is foundational cross-cutting plumbing; sanitizer is a tool, not a primitive. |
| Coding standards | Slight stretch of "inbound" (sanitizer doesn't produce a domain model — it produces sanitised bytes for fixtures). | Architecturally honest in pure DDD. | Mismatched layer — `core/` shouldn't host transformation tools. |

**Audit-grounded recommendation**: **(a) inbound** — keep at
`adapters/inbound/sanitizer/`.

**Rationale**: introducing a `tools/` bucket for a single module
hurts contributor legibility. Grouping with sibling PDF-handling
modules is more discoverable. The "tool, not adapter" purity
argument loses to "all PDF-touching code lives together" on the
legibility lens.

### Decision 3 — `auth._secret_adapters` deletion

| Lens | Outcome |
| --- | --- |
| Kent UX | Zero direct impact (module unwired in production). |
| Contributor legibility | **POSITIVE**: ~470 LOC of dead code + ~191 LOC of obsolete tests removed. New contributor doesn't have to understand what "Wave-2 migration helpers" mean. |
| Coding standards | Standard practice — delete unused code. |
| Risk | LOW (zero production callers verified by grep). |

**Audit-grounded recommendation**: **DELETE**. Phase 1 (immediate,
standalone PR before layout move). Standard pre-merge unrestricted
grep as safety net.

### Decision 4 — `_submitters/` directory deletion

| Lens | Outcome |
| --- | --- |
| Kent UX | Zero direct impact. |
| Contributor legibility | **POSITIVE**: a tombstone directory is a "what is this?" moment for a new contributor. The directory exists, the source files don't, and a guard test asserts they shouldn't. Confusing. |
| Coding standards | Standard practice. |
| Risk | LOW (asserted absent by `test_submitter_modules_are_absent`). |

**Audit-grounded recommendation**: **DELETE**. Phase 2 (with the
submission rename PR).

### Decision 5 — Empty subpackage deletions (`corpus`, `history`, `inbox`, `status`)

| Lens | Outcome |
| --- | --- |
| Kent UX | Zero direct impact. |
| Contributor legibility | **POSITIVE**: 4 empty directories are 4 "what was this for?" moments. Their absence forces the actual code to live where it is (`filing._history_repository`, `manuals/`, etc.). |
| Coding standards | Empty placeholder directories are noise. |
| Risk | LOW (no source files; nothing depends on them). |

**Audit-grounded recommendation**: **DELETE**. Phase 2 (with the
layout move). Confirm with project owner that no in-flight work
depends on them.

### Decision 6 — Reserved `SchemaSource` enum slots (`PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`, `XSD_WIRE`)

| Lens | Keep | Delete |
| --- | --- | --- |
| Kent UX | Zero. | Zero. |
| Contributor legibility | **NEUTRAL**: a new contributor sees enum members and asks "when is this used?" The validator that rejects them documents the answer. Keeping makes the future-readiness visible. | Slight positive (less noise). |
| Coding standards | Tradeoff: forward-looking but currently inert. | Tradeoff: removable now but reintroducing means churning the schema again. |

**Audit-grounded recommendation**: **KEEP** (with explicit comment
in `_enums.py` documenting that they are forward-looking
placeholders for future BOE-extractor backends, and that
`SchemaProvenance._reject_unimplemented_sources` actively
guards against premature use).

**Rationale**: not actually "dead code" in the conventional sense
— these are enum values reserved for future implementations. The
guard validator already prevents misuse. Keeping is forward-
compatible with no real legibility cost.

### Decision 7 — `Extractor` Protocol fate (keep vs delete)

| Lens | Keep | Delete |
| --- | --- | --- |
| Kent UX | Zero. | Zero. |
| Contributor legibility | **NEUTRAL**: a Protocol with no implementations besides the BOE one is academic. New contributor wonders if non-BOE backends exist. | Slight positive: cleaner public surface. |
| Coding standards | Forward-looking abstraction with no current binding. | Standard practice — delete unused. |

**Audit-grounded recommendation**: **DELETE** the standalone
`_extractor.py` file (27 LOC). If non-BOE extractors land later,
re-introduce the Protocol then; current Protocol with one
implementation is YAGNI.

**Caveat**: confirm with project owner whether non-BOE extractors
are imminent (#23 / #25 references in the audit).

### Decision 8 — `SiteHealthAlert` ownership (browser vs workflow)

| Lens | Keep in browser (current) | Move to workflow |
| --- | --- | --- |
| Kent UX | Zero. | Zero. |
| Contributor legibility | **NEGATIVE**: `aeat.application.workflow.__init__` does monkey-patch + `model_rebuild()` ritual to break a circular forward-ref. A new contributor opening this file sees magic and wonders "what's this?". | **POSITIVE**: `SiteHealthAlert.stage: WorkflowStage` is semantically a workflow concept; moving it home eliminates the magic ritual entirely. The class lives where its concept lives. |
| Coding standards | Working but fragile (import-order-sensitive). | Architecturally clean. |

**Audit-grounded recommendation**: **MOVE TO WORKFLOW**
(`aeat.application.workflow._models.SiteHealthAlert`). `aeat.adapters.outbound.aeat.browser` keeps
the parsers and probe; the alert TYPE goes to the domain that owns
the WorkflowStage concept.

**Rationale**: the model_rebuild ritual is a contributor-
legibility wart that nobody noticed because it's hidden in
`__init__.py`. Eliminating it materially improves the codebase's
"obviousness" for a new contributor. Cost: one type relocation;
benefit: zero magic.

### Decision 9 — `_FakeAdapter` / `ProviderRequest` `__all__` cleanup

| Lens | Outcome |
| --- | --- |
| Kent UX | Zero. |
| Contributor legibility | **POSITIVE**: a leading-underscore symbol on a public surface is contradictory. `_FakeAdapter` is clearly intended as a test fixture; advertising it on `aeat.adapters.outbound.llm.__all__` invites accidental dependency. |
| Coding standards | Standard practice — private symbols stay private. |
| Risk | LOW (zero external consumers verified by grep). |

**Audit-grounded recommendation**: **REMOVE FROM `__all__`** for
both. Phase 1 (immediate). Same pattern as
`auth._providers.describe_certificate_provider` (audit 3).

### Decision 10 — Migration helper retention window

| Lens | Outcome |
| --- | --- |
| Kent UX | Zero. |
| Contributor legibility | **POSITIVE if deleted**: 4+ functions named `migrate_legacy_*_to_repository` invite the question "what legacy?". Removing them eliminates the question. |
| Coding standards | One-shot migration helpers are typically retained for a window then removed. |
| Risk | MEDIUM (depends on whether legacy data still exists in any deployed instance). |

**Audit-grounded recommendation**: **DELETE in Phase 2** (with the
filing / justificante / submission rename PRs) **IF** project
owner confirms no deployed instances need re-running the
migration. Otherwise retain with a `# TODO(#issue): remove after
2026-MM-DD` annotation.

### Cross-decision pattern: contributor legibility is the load-bearing lens

Of the 10 decisions:
- **Kent UX is unaffected by 10 of 10**. Architectural decisions
  about file placement, exception relocation, and dead-code
  removal don't change what Kent can do.
- **Contributor legibility drives 9 of 10** (decision 6 is
  neutral). Every other decision improves "what does this
  codebase look like to a new contributor on day 1?".
- **Coding standards align with legibility in 9 of 10**. The one
  exception (Decision 1 — LAYERING TENSION) is where pure DDD
  loses to project-pattern legibility.

**Conclusion**: the project's existing pattern of "domain owns
its repository" + "domain owns its errors" + "Spanish AEAT
vocabulary preserved" already privileges Kent's ubiquitous
language. The restructure decisions mostly extend that
principle: **make the codebase tell a Kent-shaped story**, even
when the architectural-purity lens would say otherwise.

### Audit-grounded action list (en-bloc approvals)

The following are recommended for direct execution without
further per-item user approval (architecturally and UX-grounded
all converge):

- **DELETE** (Phase 1 standalone PRs):
  - `auth/_secret_adapters.py` (whole module + test)
  - `_FakeAdapter` from `aeat.adapters.outbound.llm.__all__`
  - `ProviderRequest` from `aeat.adapters.outbound.llm.__all__`
  - `auth._providers.describe_certificate_provider` from
    `_providers.__all__`
  - `filing.utc_now` from `filing.__init__.__all__`
  - `schema._extractor.py` (whole 27-LOC file)
- **DELETE** (Phase 2 with restructure):
  - 4 empty subpackages (`corpus`, `history`, `inbox`, `status`)
  - `_submitters/` tombstone directory
  - `_FilingHistoryRepository.fetch_justificante_pdf` (raises
    `NotImplementedError`)
  - 4 hollow Protocol stubs in `sync` (`LLMClient`, `LLMRequest`,
    `ManualRulesLoader`, `SchemaLoader`)
- **RELOCATE** (Phase 2 with restructure):
  - `SiteHealthAlert` → `aeat.application.workflow._models`
  - `LiveSubmitForbiddenError` → `core/access_gate/_errors.py`
  - `AeatLiveReadNotEnabledError` → `core/access_gate/`
  - `validate_spanish_tax_id` → `core/identity/`
- **STRUCTURAL DECISION**:
  - **(A) loosen `domain/` import rule** for per-domain
    repositories — adopt as ADR carve-out.
  - **`adapters/inbound/sanitizer/`** — keep proposed destination.

**Items still requiring project-owner confirmation** (no
audit-grounded recommendation possible without):
- Migration helper retention window (Decision 10 conditional on
  deployment state).
- Reserved `SchemaSource` enum slots (Decision 6 — keep is the
  audit recommendation, but project may have plans).

### Layering tension: per-domain repositories vs `domain/` import rule

**Surfaced**: audit 5 (filing). **Affects**: every prior audit
(rental, errors, auth, storage) and every domain-with-repository
(rental, filing, justificante, sync, submission, workflow,
financial.*).

**The tension**:

- The project's established pattern (audit 2 surfaced) is per-domain
  `_repository.py` lives WITH its domain.
- The ADR's import-boundary contract says `domain/` MUST NOT import
  from `adapters/` (`core/` allowed only for foundational types).
- Repositories import heavily from `aeat.adapters.persistence.storage` (envelope I/O,
  encrypted columns, errors, lock).
- Placing repositories in `domain/<name>/` violates the layered
  contract.

**Three resolution options**:

- **(A) Loosen domain rules**: explicitly permit
  `domain/<name>/_repository.py` to import from
  `adapters/persistence/storage/` (treat persistence-substrate as
  quasi-foundational, similar to `core/`). Honest about the
  current pattern; minimal restructure cost; documents the
  compromise.
- **(B) Strict hexagonal split**: define repository protocols in
  `domain/<name>/_protocols.py`, place implementations in
  `adapters/persistence/<name>/`. Architecturally cleaner; bigger
  refactor; affects 7+ domains.
- **(C) Repositories as application-layer**: move all per-domain
  repositories to `application/<name>/_repositories.py`. Less
  conventional; awkward when use cases come and go but persistence
  is durable.

**Decision required before execution.** The audit recommends (A);
the user has final say.

**Cascading impacts**:

- Audit 2 (rental) project-convention claim ("per-domain
  repositories ride home with their domain") needs an "if (A) is
  chosen" caveat.
- Audit 4 (storage) persistence treatment needs the same caveat.
- Filing audit 5 destinations are written assuming (A); will need
  a rewrite for (B) or (C).
- Future audits (justificante, sync, submission, workflow,
  financial.*) all touch this question.

### Misplacement: `aeat.application.filing._history_repository`

**Surfaced**: audit 5 (filing). **Resolution**: file moves out of
`filing/` into the sync domain. Persists `WireFilingHistory` —
type owned by `aeat.application.sync`. No production consumer outside `filing/`
itself today; safe to relocate. To be folded into the sync audit
when that lands.

### Static schema corpus relocation (filing/_builders/_modelo_130_schema.py)

**Surfaced**: audit 5 (filing). The classes
`StaticCasillaSchema`, `StaticCasillaCollection`,
`StaticCasillaSchemaProvider`, `CasillaSource` live in a per-modelo
file but are the project's canonical runtime schema-provider
implementation, used by `runtime.py`, `testing.py`, AND all three
builders. Decision: promote to a shared kernel under
`domain/filing/_schemas.py` OR accept the misnomer until the real
casilla DB (#23) lands. Recommendation: promote at restructure
time — the misnomer is a footgun for new contributors.

### Layered-architecture violations consolidated (7 across all audits)

Pre-execution untangling required. Each violates the ADR's import-
boundary contract.

1. **`casillas` → `aeat.entrypoints.cli`** (audit 18) — domain → entrypoint.
   Specific file:line not yet located; verify during execution.
2. ~~`financial` → `aeat.entrypoints.cli`~~ — **FALSE POSITIVE** (audit 20
   corrected; no such import in current source).
3. **`profile.assets` + `profile.inventory` → `formulas._rulesets.modelo_100._amortization` / `_inventario` / `_ccaa`** (audit 18) — cross-domain private import.
4. **`filing._review` → `aeat.domain.financial.transactions._repository`** (audit 5) — subpackage-private import.
5. **`storage._master_key` → `aeat.domain.financial.invoices._validators`** (audit 4) — `core/`-bound code → `adapters/`. NIF canary.
6. **`sanitizer._records` → `aeat.domain.financial.invoices._validators`** (audit 8) — same target as #5.
7. **`verification._verify` → `formulas._ledger.Discrepancy` + `formulas._ruleset.Ruleset`** (audit 19) — private bypass; resolve by promoting to public formulas surface.
8. **`cli/filing/__init__.py` → `formulas._period`, `formulas._registry`, `formulas._rulesets`, `formulas._rulesets.modelo_100._ccaa.compute_cuota_autonomica_general`** (audit 19) — 4-level deep private bypass into ruleset implementation.

**Resolution patterns** (audit recommendations):

- **#1, #2** (`casillas`, `financial` → cli): trace specific
  imports during execution; likely test-utility leak, not actual
  runtime dep. Resolve at move time.
- **#3** (profile → formulas private): extract a public API in
  `domain/formulas/` for amortization tables + CCAA registry.
- **#4** (filing → financial private repo): rewrite to use
  `aeat.domain.financial.transactions` public surface, OR document and
  promote the symbol.
- **#5, #6** (NIF canary): move `validate_spanish_tax_id` to
  `core/identity/` (option A) — eliminates BOTH violations in
  one move. Already flagged in audit 4 and confirmed in audit 8.

### Subpackage-private import boundary violation: `aeat.domain.financial.transactions._repository`

**Surfaced**: audit 5 (filing). `filing/_review.py` imports
`TransactionCatalogueRepository` from
`aeat.domain.financial.transactions._repository` (private path), not via
the subpackage's public `__init__.py`. To be flagged in the
financial.transactions audit.
