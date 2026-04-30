---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/research/ location)
# Feature tag (replace aeat-restructure with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#research'
  - '#aeat-restructure'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-30'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-plan]]")
related:
  - '[[2026-04-30-aeat-restructure-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
| Local state | 14 | 25,800 | 8 | `storage` (11,972) `[MONO]`, `observability` (1,802) `[MONO]`, `schema` (1,774) `[MONO]`, `llm` (1,711) `[MONO]` |
| Remote AEAT | 3 | 4,500 | 3 | `sede` (2,024) `[MONO]`, `submission` (1,264) `[MONO]`, `browser` (1,196) `[MONO]` |
| Connectors | 8 | 18,900 | 6 | `cli` (7,625) `[MONO]`, `auth` (4,782) `[MONO]`, `filing` (4,465) `[MONO]`, `workflow` (2,028) `[MONO]` |
| Cross-cutting infra | 9 | 4,800 | 1 | `errors` (2,945) `[MONO]`, `config.py` (851), `logging.py` (295) |
| Empty placeholders | 4 | 0 | 0 | `corpus`, `history`, `inbox`, `status` |
| **Total** | **38 non-empty** | **~59,200** | **20** | over half the codebase is at or over the 950-LOC threshold |

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
| `financial` | Track-B financial-input root (`_decimal`, `_raw_transaction`); ingestion-domain skeleton. | 193 | high | `adapters/inbound/financial/` | (candidate `transactions/`) | — |
| `_pdf_import` | Shared primitives for PDF-import families (regex, scrub, errors). | 488 | high | `adapters/inbound/pdf/` | `pdf/` | — |
| `borrador` | Casilla-complete Modelo 100 (IRPF / Renta) PDF parser. | 399 | high | `adapters/inbound/borrador/` | — | — |
| `declaracion` | Casilla-complete declaración PDF parser. | 818 | high | `adapters/inbound/declaracion/` | — | — |
| `justificante` | AEAT receipt parser + repository. Receipt is AEAT-issued but Kent ingests it as outside data. | 1,292 | med | `adapters/inbound/justificante/` | — | `[MONO]` `[CONFLATE?: parser + repository — repository concern leaks toward persistence]` |
| `identity` | Spanish identity-document parsing + validation (NIF/NIE). User-supplied data. | 212 | med | `adapters/inbound/identity/` | — | — |
| `sanitizer` | PDF sanitiser pipeline; redacts and rewrites incoming PDFs. | 1,774 | med | `adapters/inbound/sanitizer/` | — | `[MONO]` `[CONFLATE?: imports both `financial` and `justificante` — possible hidden connector]` |

### Table 2 — local state → split between `domain/` and `adapters/persistence/`

The "local state" bucket bifurcates in the new layout. Catalogues +
computation engines + profile move to `domain/`. Persistence + run-trace
+ external-service caches move to `adapters/persistence/`. The
`Destination` column is the split decision per module.

| Module | Functionality (1 line) | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `storage` | Persistence backbone: ORM, repositories, blob store, encryption, migrations, secret store, recovery, classification. | 11,972 | high | `adapters/persistence/storage/` | — | `[MONO]` `[CONFLATE: ORM + blob + crypto + classification + recovery + redaction + rotation + secret-store; internal split deferred to follow-up ADR]` `[CORE-LEAK?: `_path_safety`, `_lock`, `_crypto`, `_master_key` may belong in `core/`]` |
| `observability` | Run-trace events, replay, sinks, redaction, fingerprints. | 1,802 | high | `adapters/persistence/observability/` | — | `[MONO]` |
| `schema` | Programmatic AEAT modelo schema extraction and typed IR (BOE-driven). | 1,774 | med | `domain/schema/` | — | `[MONO]` `[CONFLATE?: extraction is inbound, IR is domain — possible split into `adapters/inbound/schema-extraction/` + `domain/schema/`]` |
| `llm` | LLM client, prompt registry, cache, translator, usage recorder. | 1,711 | low | `adapters/persistence/llm/` | — | `[MONO]` `[CONFLATE?: external client + local cache + usage tracking; client is not really persistence]` |
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

### Table 3 — remote AEAT → `adapters/outbound/`

Direct interaction with the AEAT portal / external AEAT surface.

| Module | Functionality (1 line) | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `sede` | Read-only driver for the authenticated AEAT sede electrónica (expediente walker, parsers). | 2,024 | high | `adapters/outbound/sede/` | — | `[MONO]` |
| `submission` | Submission engine + preflight + dry-run + format builders. Live transport gated; CLI excised. | 1,264 | high | `adapters/outbound/export/` | `export/` | `[MONO]` (rename closes legal-liability ambiguity per `2026-04-18-live-submit-cli-excision-adr`) |
| `browser` | Browser automation (Playwright, evasion, profile, site-health probe). | 1,196 | high | `adapters/outbound/browser/` | — | `[MONO]` |

### Table 4 — connectors → `application/` (with `cli` routed to `entrypoints/`)

These are the modules to watch. Each was chosen for the connector bucket
because its import surface or stated purpose spans multiple domains.

| Module | Bridges | LOC | Conf | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| `cli` | inbound + state + remote + infra | 7,625 | high | `entrypoints/cli/` | — | `[MONO]` `[CONFLATE: 43 flat files spanning every domain CLI; internal restructure by Kent action verb deferred]` |
| `auth` | remote (cert + cl@ve) + persistence (secret storage) + external (Google) | 4,782 | high | `application/auth/` | — | `[MONO]` `[CONFLATE: Google auth + AEAT auth + secret storage — split into `auth/aeat/` + `auth/google/` deferred to follow-up ADR]` `[CORE-LEAK?: `_secret_adapters`, `_file_permissions` may belong in `core/`]` |
| `filing` | inbound (justificante) + state (storage, formulas, models, deadlines) + remote (submission, sync) | 4,465 | high | `application/filing/` | — | `[MONO]` `[CONFLATE: cross-domain orchestrator; internal `_builders` + `reconciliation` dirs hint at split potential]` |
| `workflow` | inbound + state + remote | 2,028 | high | `application/workflow/` | — | `[MONO]` `[CONFLATE: imports `auth`, `browser`, `sede`, `submission`, `sync`, `filing`, `storage`, `deadlines` — highest cross-domain in-degree]` |
| `sync` | state (storage) + remote (browser, live fetcher) | 1,499 | high | `application/sync/` | — | `[MONO]` |
| `setup` | state (storage, profile) + remote (auth, browser via auth) | 1,312 | high | `application/setup/` | — | `[MONO]` |
| `review` | inbound (financial) + state (storage) + remote (via sync) | 844 | high | `application/review/` | — | — |
| `verification` | inbound (declaracion) + state (formulas, models) | 361 | high | `application/verification/` | — | (clean small connector — likely a model for what other connectors should look like) |

### Table 5 — cross-cutting infrastructure → `core/` (with `mcp` routed to `entrypoints/`)

Not a domain. These modules are imported by everything and have no
particular allegiance.

| Module | Functionality (1 line) | LOC | Destination | Rename | Flags |
| --- | --- | --- | --- | --- | --- |
| `errors` | Domain exception hierarchy + public error registry. | 2,945 | `core/errors/` | — | `[MONO]` `[CONFLATE?: `_registry` is cross-cutting infra but the exception classes themselves may be domain-specific and should ride home with their domain]` |
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

- **`sanitizer`** — `adapters/inbound/sanitizer/` (current proposed) or
  connector under `application/`? Imports `financial` and `justificante`;
  verify whether outputs flow forward only or also feed back into
  persistence.
- **`llm`** — `adapters/persistence/llm/` (current proposed) or its own
  external bucket? In a strict 3-domain frame, calls to non-AEAT
  external services have no home; persistence is the least-bad fit
  because the cache + usage records are local.
- **`schema`** — `domain/schema/` (current proposed) or split into
  `adapters/inbound/schema-extraction/` + `domain/schema/`? Depends on
  whether BOE extraction is one-shot at build time or runs during user
  flows.
- **`portals`** — `domain/portals/` (current proposed) or `adapters/`-
  adjacent metadata? Same question: does it ever drive live behaviour?
- **`identity`** — `adapters/inbound/identity/` (current proposed) or
  `domain/profile/identity/` (profile-adjacent)?
- **`auth`** — placed in `application/auth/`; the audit produces the
  split design (`auth/aeat/` + `auth/google/`) and folds it into the
  ADR. Splits and the move are coordinated.
- **`storage`** — placed in `adapters/persistence/storage/`; the audit
  produces the internal split design (likely separating ORM,
  blob/crypto, classification/recovery, redaction/rotation, secret-
  store) and identifies `[CORE-LEAK]` candidates that bubble up to
  `core/`. Splits and the move are coordinated.
- **`errors`** — placed in `core/errors/`; audit must inventory every
  exception class and decide which ones ride home with their domain
  versus stay in the shared registry.
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

Each audited module gets one section using this schema:

- **Module**: dotted path (e.g. `aeat.submission.engine`).
- **Inventory**: file count, total LOC, public symbols (classes, functions,
  enums, constants exported by `__init__.py` or the module surface).
- **Imports IN**: who depends on this module (callers).
- **Imports OUT**: what this module depends on (its dependencies, especially
  cross-domain ones).
- **Domain mapping**: which of `inbound` / `domain-model` /
  `persistence` / `outbound` / `application` / `core` it serves under
  the new layout. Mark `straddles {a, b}` if it spans more than one.
- **Destination validation**: confirm or revise the destination listed
  in the heat-map row for this module.
- **Flag resolution**: for every `[MONO]` / `[CONFLATE]` / `[CONFLATE?]`
  / `[CORE-LEAK]` / `[CORE-LEAK?]` flag in the heat-map row, mark the
  flag confirmed, cleared, or upgraded (`?` → confirmed). Each `?` flag
  must reach a yes/no by the end of the audit.
- **Boundary violations**: concrete cross-domain wiring observed
  (function X reads filesystem state AND posts to AEAT; class Y imports
  both a parser and a storage manifest; etc.).
- **Internal split design** (REQUIRED for `[MONO]` modules): proposed
  sub-modules, public surface per sub-module, fracture lines. The split
  feeds back into the heat-map destination column and the ADR layout
  block. Sub-modules inherit the parent's bucket assignment unless this
  audit produces a `[CORE-LEAK]` finding that bubbles a sub-module up
  to `core/`.
- **Naming clarity**: does the module name telegraph its domain to a
  new reader? `clear` / `ambiguous` / `misleading`. If `misleading`,
  propose a rename.
- **Verdict**: one of `clean` (single-domain, well-named, no MONO),
  `straddling` (touches >1 domain in one module), `misplaced` (single-
  domain but under the wrong destination), `dead` (no callers,
  candidate for removal), `splits-into-N` (MONO with internal split
  design produced) — with a one-line rationale.

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
  `from aeat.models import ...` as the canonical import; pre-dates
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

- `adr/2026-04-12-submission-engine-adr.md` — `aeat.submission` engine.
- `adr/2026-04-22-aeat-fichero-boe-export-adr.md` —
  `submission/_formats/` layout block; `_engine.py`, `_models.py` paths.
- `adr/2026-04-18-live-submit-cli-excision-adr.md` — `submission/`
  path references (doctrinally authoritative on the excision policy;
  paths only need inline-update).
- `adr/2026-04-25-workflow-live-flag-excision-adr.md` — `submission/`
  paths in non-modification rules.
- `adr/2026-04-17-aeat-access-gate-adr.md` — `aeat.submission` import
  from `aeat.auth`; old marker reference.
- `adr/2026-04-18-auth-protocol-adr.md` — `submission/_protocols.py`.
- `adr/2026-04-18-draft-approval-staleness-adr.md` —
  `submission/_confirm.py`.
- `adr/2026-04-24-aeat-cli-wireframe-adr.md` — `submission/_engine.py`
  test paths AND `domain:aeat-remote, domain:submission` issue-label
  references.
- `reference/2026-04-16-submission-safety-sweep-reference.md` —
  `aeat.submission` placement decisions, multiple paths.
- `reference/2026-04-22-submission-pipeline-hardening-reference.md` —
  whole document describes / locks `submission/` structure.

**Models cluster (rename to `modelos`)**:

- `adr/2026-04-13-modelo-inventory-adr.md` — `src/aeat/models/`
  multiple paths; canonicalises `models` as the home.
- `adr/2026-04-22-citation-blocklist-adr.md` —
  `src/aeat/models/_citation_registry.py`.

**Errors cluster (move to `core/errors/`)**:

- `adr/2026-04-25-error-code-registry-adr.md` — `aeat.errors` public
  import contract. Critical: the contract `from aeat.errors import ...`
  must keep working through the restructure (re-export shim at
  `aeat/errors.py` if needed, or document the breaking change).

**Logging cluster (move to `core/logging.py`)**:

- `adr/2026-04-25-json-output-contract-adr.md` — `src/aeat/logging.py`
  named in implementation block.

**MCP cluster (move to `entrypoints/mcp/`)**:

- `adr/2026-04-16-google-workspace-mcp-auth-adr.md` — `aeat.mcp`
  package placement; `.mcp.json` rewires `python -m aeat.mcp.launch_*`
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
  `domain:mediation`) and the `aeat.submission.live_submit` module
  reference.

#### Cross-cutting load-bearing constraints surfaced by the audit

- **Public-import contracts must survive the move.** At minimum
  `aeat.errors` (per `error-code-registry-adr`) is documented as a
  stable public surface; relocating to `aeat.core.errors` requires
  either a re-export shim or a documented breaking change with a
  migration window.
- **Issue-label taxonomy mirrors the markers.** `domain:aeat-remote`,
  `domain:submission`, `domain:local-state`, `domain:mediation`,
  `domain:financial-input` are referenced in multiple ADRs and plans
  as GitHub-issue labels. The label rename ships in lockstep with the
  marker rename, with the same naming.
- **`.mcp.json` is a runtime-config contract**: the script-entry
  string `uv run python -m aeat.mcp.launch_google_workspace` will
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
| 10 | R2 | Public / external API surface not enumerated | ACCEPT | Add a "Public surface" subsection: minimum, `aeat.errors` (per `error-code-registry-adr`); confirm whether anything else is documented as public. Each entry gets shim-or-break decision. Semver: at least minor bump if shims; major if explicit break. |
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

> Appended one at a time. Order is human-driven; the user picks the next
> module each cycle.

_(none yet — awaiting first module)_

## Open questions / themes

> Cross-cutting observations that don't belong to a single module are
> captured here as they emerge, then carried into the ADR.

_(empty)_
