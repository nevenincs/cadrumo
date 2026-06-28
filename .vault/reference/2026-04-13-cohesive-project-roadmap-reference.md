---
name: Cohesive project roadmap
description: Cross-domain roadmap consolidating Phase 1 (AEAT loop), Phase 2 (financial data), and mediation milestones for the aeat project
type: reference
tags: ["#reference", "#roadmap"]
date: 2026-04-13
modified: '2026-04-13'
---

# Cohesive project roadmap (2026-04-13 snapshot)

## What this project is

`aeat` is a CLI-driven mid-layer that bridges the Spanish tax authority (AEAT Sede Electrónica) with a Spanish autónomo's local financial state. It is not a tax product and not a bookkeeping product — it is the translator that sits between three layers: (1) AEAT remote state (modelos, casillas, expedientes, notificaciones, justificantes), accessed bi-directionally via authenticated browser automation, (2) local persisted state (catalogues, schemas, casilla self-database, normativa corpus, filing history, sync snapshots), and (3) inbound financial data (bank transactions, invoices, receipts, Drive/Gmail evidence) flowing one-directionally into the mid-layer. The end goal is automated, manual-gated tax filing for Spanish autónomos with full legal defensibility: every casilla value justified end-to-end, every submission preflighted, every change reproducible. Stack is Python 3.13, pydantic v2 strict, src layout, pytest-only, ty + prek, GitHub Actions disabled (release-please runs locally).

## The four domain boxes

### `domain:aeat-remote` — AEAT remote bi-directional
Reads and writes against Sede Electrónica via authenticated Playwright sessions: live status reader, notifications inbox, draft preflight, dry-run-default submission engine, justificante (PDF receipt) parsing.
- Open: 1 — Closed: many (status reader, inbox, submission engine, justificante parser, PKCS#12 auth all merged).
- Top open: #65 (refactor `SubmissionEngine.preflight()` to public API).

### `domain:local-state` — Local state management
Persisted catalogues and schemas the mid-layer reasons over: typed modelo enum, portal enum, year-scoped filing rulebook corpus, programmatic modelo schema extraction, external knowledge sources inventory.
- Open: 4 — Closed: storage layer (#10), filing-history fixtures (#14), Manual práctico ingestion (#25), casilla catalogue (#23), normatives (#45), trilingual i18n (#20), LLM client (#21).
- Top open: #6 (modelo enum), #7 (portals enum), #9 (programmatic schema extraction), #17 (per-year rulebook corpus + fetch/verify CLI), #24 (external knowledge sources research).

### `domain:financial-input` — Incoming financial data (one-directional)
Pulls receipts, invoices, transactions, and supporting documents from manual imports, Google Workspace, and other providers; normalises them into typed records with provenance; classifies VAT and deductibility; matches receipts ↔ invoices ↔ transactions; closes financial periods into modelo inputs. The largest open work area on the project.
- Open: 18 — Closed: 0.
- Top open: #71 (EPIC: Phase 2 financial-data ingestion + filing-input pipeline), #84 (EPIC: receipt + VAT extraction + classification pipeline), #73 (P2-A financial provider ABC + manual import providers — the unblocking foundation).

### `domain:mediation` — Mid-layer mediation
The translator itself: composite workflow engine, period close + casilla derivation, provenance / audit trail, LLM-driven natural-language tax advice, AEAT live↔local self-healing.
- Open: 4 — Closed: workflow engine (#59), self-healing cross-validation (#11).
- Top open: #70 (EPIC: Phase 1 AEAT remote read/write loop with local sync), #81 (P2-I FinancialPeriod → modelo inputs), #82 (P2-J end-to-end provenance), #92 (LLM-driven NL tax advice).

### `domain:infra`
Tooling, CI substitute, dev loop, lint/typecheck/test gates.
- Open: 1 — Closed: many (release-please local pipeline, justfile recipes, env provisioning, prek hooks).
- Top open: #15 (standardise on pytest-only, ban unittest, install live-web plugins).

### `domain:docs`
User-facing documentation, getting-started, architecture diagrams.
- Open: 0 — Closed: 1 (#67 — README rewrite + getting-started + architecture).
- This roadmap PR sits in this domain.

## Milestones

### `0.0.1-scaffolding` — substrate
Theme: pre-alpha scaffolding — base module structure, dev tooling, foundational catalogues, storage, auth, schema extraction. No filing functionality, only the substrate.
Acceptance gate: dev loop is reproducible, src layout is fixed, lint/typecheck/test/hooks all green, base catalogues + storage scaffolded.
Open issues: #15 (pytest-only standardisation), #24 (external knowledge sources research).
Closed: 26.

### `0.0.2-foundations` — first features on the substrate
Theme: working PoC extractors, populated catalogues, sync runner stub, first AEAT auth backend, first filing draft.
Acceptance gate: at least one modelo end-to-end through draft generation, populated portal/modelo enums, year-scoped rulebook corpus, financial-data ingestion ABCs in place.
Open issues: #6 (modelo enum), #7 (portal enum), #9 (programmatic schema extraction), #17 (per-year rulebook corpus), #65 (preflight() public API), #73 (P2-A financial provider ABC), #74 (P2-B transaction model + provenance), #75 (P2-C invoice catalogue), #76 (P2-D document attachment service), #77 (P2-E AEAT category catalogue + proportionality), #79 (P2-G transaction categorisation), #80 (P2-H Google Workspace ingestion), #85 (R-1 VAT category enumeration), #86 (R-2 LLM receipt extractor), #87 (R-3 VAT classification engine), #88 (R-4 receipt source connectors), #89 (R-5 reconciliation engine), #90 (R-6 utilities handler), #91 (statutory threshold engine).
Closed: 20.

### `0.1.0-pre-alpha` — read-only loop end-to-end
Theme: live↔local self-healing read-only loop running against at least one modelo + period; CLI usable; no actual filing.
Acceptance gate: a user can run `aeat workflow next/run` and get a fully reconciled, provenance-tagged read-only view of their AEAT state for one modelo without manual intervention.
Open issues: #70 (EPIC Phase 1 AEAT loop), #78 (P2-F proportionality engine), #81 (P2-I period close), #82 (P2-J provenance trail), #84 (EPIC receipt + VAT pipeline), #92 (LLM NL tax advice).
Closed: 10.

### `0.2.0-alpha` — first manual-gated filing
Theme: first end-to-end filing of at least one modelo against AEAT, manual review gate before submission, multi-modelo schema coverage, complete audit trail.
Acceptance gate: a real autónomo filing successfully posted to AEAT through the dry-run-default submission engine, with the human review gate enforced and an end-to-end audit record persisted.
Open issues: #71 (EPIC Phase 2 financial-data + filing-input pipeline).
Closed: 2.

### `0.3.0-beta` — unattended
Theme: unattended filing for the supported modelo set, divergence alerting, full self-heal allowlist enforcement, hardened security posture, runbook complete.
Acceptance gate: scheduled unattended runs file the supported modelo set without human action under normal conditions; allowlist enforcement blocks anomalies; runbook is published.
No issues yet.

### `1.0.0` — GA
Theme: stable supported modelo set, documented release process, public README, security review complete.
No issues yet.

## EPIC dependency graph

| EPIC | Title | Domain | Milestone gate | Depends on |
| :--- | :--- | :--- | :--- | :--- |
| #70 | Phase 1 — AEAT remote read/write loop with local sync | mediation + aeat-remote | `0.1.0-pre-alpha` | base catalogues (#6, #7), schema extraction (#9), storage (#10, closed), auth (#8, closed), submission engine (#42, closed), workflow (#59, closed), self-heal (#11, closed) |
| #84 | Receipt + VAT extraction and classification pipeline | financial-input | `0.1.0-pre-alpha` | R-1..R-6 (#85→#90), statutory thresholds (#91), LLM client (#21, closed), trilingual corpus (#20, closed) |
| #71 | Phase 2 — Financial data ingestion and filing-input pipeline | financial-input | `0.2.0-alpha` | EPIC #84, P2-A..P2-J (#73→#82), AEAT category catalogue (#77), workflow engine (#59, closed), provenance (#82) |

Text view of the dependency chain:

```
  #70 (Phase 1 AEAT loop, 0.1.0)
      ├── #6, #7, #9, #17, #65   [foundations: catalogues + schema]
      └── (depends on closed: #8, #10, #11, #42, #46, #59)

  #84 (Receipt + VAT pipeline, 0.1.0)
      └── #85 → #86 → #87 → #88 → #89 → #90 → #91

  #71 (Phase 2 financial pipeline, 0.2.0)
      ├── needs #84 complete
      ├── #73 → #74 → #75 → #76 → #77 → #78 → #79 → #80
      └── #81, #82 (close-out: period derivation + provenance)
```

## What's on main today

Subpackages currently present under `src/aeat/`:

- `auth/` — PKCS#12 client-certificate authentication backend for AEAT.
- `browser/` — Playwright-based browser automation, stealth, anti-bot evasion.
- `casillas/` — Reviewed casilla self-database (per-modelo casilla catalogue).
- `cli/` — `aeat` CLI entry point and command tree.
- `config.py` — Pydantic-settings `Settings` model (single source of env truth).
- `corpus/` — AEAT Manual práctico ingestion, normatives corpus, BOE references.
- `deadlines/` — Filing-deadline computation engine (typed schedule per profile + year).
- `env_io.py` / `_test_env_io.py` — Env provisioning helpers.
- `errors.py` — Project-wide typed exceptions.
- `filing/` — Filing draft engine (FilingDraft + builders), Modelo 130 PoC, Modelo 303, Modelo 390.
- `i18n/` — Trilingual (en/es/hu) i18n primitives + storage shape.
- `inbox/` — AEAT notifications inbox (requerimientos, propuestas, embargos, acuses).
- `justificante/` — PDF justificante (receipt) parser + CSV verification.
- `llm/` — Provider-agnostic LLM client + translation pipeline.
- `logging.py` — Centralised structured logging.
- `manuals/` — Manual práctico schema, loader, raw-PDF manifests.
- `models/` — Modelo catalogue scaffolding.
- `normatives/` — Typed BOE-linked Spanish tax normatives catalogue.
- `portals/` — Portal catalogue scaffolding.
- `schema/` — Modelo schema extraction substrate.
- `setup/` — First-run interactive `aeat setup` wizard.
- `status/` — AEAT live status reader (Mis expedientes / Notificaciones / Devoluciones / Borrador / Datos fiscales).
- `storage/` — SQLite + SQLAlchemy + Alembic storage layer.
- `submission/` — Dry-run-default browser submission engine for READY_TO_SUBMIT drafts.
- `sync/` — Live↔local sync runner stub.
- `testing/` — Synthetic filing-history fixtures + loader.
- `workflow/` — Composite end-user workflow engine (`aeat workflow next/run`).

## The next 5 highest-priority issues across the whole backlog

1. **#73 — P2-A: Financial provider ABC + manual import providers (CSV / XLSX / OFX)** — `domain:financial-input`. Unblocks the entire P2-B → P2-J chain and EPIC #71. Until the provider ABC exists nothing else in Phase 2 can land.
2. **#6 — Catalogue AEAT freelancer modelos as core Python enums with extensible metadata** — `domain:local-state`. The modelo enum is the type that every other layer (filing builders, schema extraction, deadlines, casillas) keys off. Closing it tightens the type surface across the codebase.
3. **#9 — Programmatic AEAT modelo schema extraction (PDF/HTML → typed model)** — `domain:local-state`. Required for EPIC #70 (Phase 1 loop) — without typed schemas the read-only loop cannot validate live state against local expectations.
4. **#85 — R-1: VAT category enumeration + Spanish/EU regulation codification** — `domain:financial-input`. Foundation of EPIC #84 (receipt + VAT pipeline); R-2..R-6 + #91 all consume R-1's enumeration.
5. **#82 — P2-J: Provenance + audit trail (every casilla value justified end-to-end)** — `domain:financial-input` / `domain:mediation`. The legal-defensibility backbone; #70 and #71 cannot close their respective milestones without it.

## Delivery sequence

Numbered next deliveries from current `main` HEAD (`503da14` — first-run setup wizard) to the `0.2.0-alpha` gate:

1. #15 — pytest-only standardisation (infra cleanup; unblocks live-test plugin install).
2. #6 — Modelo enum with extensible metadata.
3. #7 — Portal enum.
4. #9 — Programmatic modelo schema extraction.
5. #17 — Per-year rulebook corpus + fetch/verify/diff CLI.
6. #65 — Promote `SubmissionEngine.preflight()` to public API.
7. #85 — R-1 VAT category enumeration (Ley 37/1992 as code).
8. #73 — P2-A financial provider ABC + manual import providers.
9. #74 — P2-B transaction model + raw-source provenance.
10. #75 — P2-C invoice catalogue (issued + received) + transaction linking.
11. #76 — P2-D document attachment service.
12. #77 — P2-E AEAT tax category catalogue + per-category proportionality rules.
13. #86 → #87 → #88 → #89 → #90 → #91 — receipt extraction, VAT classification, source connectors, reconciliation, utilities, statutory thresholds (closes EPIC #84).
14. #78 → #79 → #80 — proportionality engine, transaction categorisation, Google Workspace ingestion.
15. #81 → #82 — financial period close + end-to-end provenance (closes EPIC #71 → milestone `0.2.0-alpha`).

(EPICs #70 and #84 close into `0.1.0-pre-alpha` along this sequence; #71 closes into `0.2.0-alpha`.)

## Definitions

- **Substrate** — The dev/runtime base everything else stands on: src layout, pydantic v2 strict, ty, prek, pytest, justfile, release-please-local, env provisioning. Mostly closed under `0.0.1-scaffolding`.
- **Mid-layer** — `aeat` itself; the translator between AEAT remote state, local persisted state, and inbound financial data.
- **Modelo** — An AEAT tax form (e.g., Modelo 130, 303, 390, 100). Each modelo has a fixed casilla schema per year.
- **Casilla** — A numbered field on a modelo. Filing means computing every casilla and submitting them.
- **Dieta** — Per-diem allowance (subsistence + lodging) deductible under specific statutory thresholds.
- **Manutención** — Subsistence-meal expense category with its own statutory cap and documentary requirements.
- **IVA reverse charge (inversión del sujeto pasivo)** — VAT regime where the recipient self-accounts for VAT instead of the supplier; applies to most intra-EU B2B services and some domestic categories.
- **Justificante** — Official PDF receipt issued by AEAT after a successful filing or payment; the legal proof of submission.
- **Sede Electrónica** — AEAT's online portal at sede.agenciatributaria.gob.es; the only sanctioned channel for electronic interaction with the tax authority.
- **Autónomo** — Spanish self-employed individual; the target user persona of `aeat`.
- **Preflight** — Pre-submission validation pass run by `SubmissionEngine` before any write to AEAT; dry-run by default.
- **Self-heal** — Live↔local cross-validation loop that detects divergence between AEAT remote state and local snapshots and reconciles within an allowlist.
- **Provenance / audit trail** — End-to-end record linking every casilla value back through transactions, invoices, receipts, and statutory citations.
- **Rulebook corpus** — Year-scoped, in-repo collection of normative texts and AEAT manuals consumed by the mediation layer.
- **EPIC** — A roll-up issue grouping a multi-issue work stream (currently #70, #71, #84).
