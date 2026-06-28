---
tags:
  - "#research"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-20-pdf-import-research]]"
  - "[[2026-04-20-pdf-import-adr]]"
  - "[[2026-04-17-export-first-adr]]"
---

# real-pdf-import umbrella research

## Problem statement

`#271` shipped `aeat filing import --from-justificante` against *synthetic* reportlab-generated PDFs. The feature reconstructs a `FilingDraft` **scaffold** (modelo / period / profile, every casilla `EMPTY`) plus a companion `SubmittedFiling` — which is the correct thing to do against a justificante receipt, because that document **does not carry per-casilla values** by design.

The gap raised by the user is substantively different: Kent wants to drop a **real AEAT-produced PDF** onto the tool and get back a **verified** draft — every casilla populated with the printed value, every computed casilla re-derived via the project's formula engine, every divergence surfaced to Kent. That flow requires:

1. Parsing the **full declaración** PDF (or *borrador* / *predeclaración* / *datos fiscales*, depending on modelo and life-cycle stage), not the receipt.
2. A **complete casilla schema** per modelo — the current corpus has 4 / 4 / 3 casillas for 130 / 303 / 390 respectively, which is an order of magnitude short of reality.
3. A **per-modelo extractor** mapping PDF bounding boxes / anchor labels / form-field names to casilla IDs.
4. A **round-trip verification pass** running the formula engine's `Engine.audit_against(ruleset, provided, tolerance)` (already present at `src/aeat/domain/formulas/_engine.py:51`) and reporting discrepancies classified by cause (extraction bug / formula bug / un-modelled AEAT rule / rounding).
5. A **real-fixture corpus** sourced outside the repo, scrubbed, and committed under a deterministic hash-pinning policy.
6. Special treatment for **Modelo 100 (IRPF, RENTA)**: multi-page, multi-anexo (A, B, C, D, Ñ, G, H, I, J, K), conditional sections by régimen and civil status, borrador ≠ declaración semantics. Likely its own sub-EPIC.

This umbrella scopes the work as a cluster graph so each cluster can run its own `research → ADR → plan` triplet with a clear dependency order.

## Current state (grounded)

From the repo-wide inventory:

| Dimension | Current state | Evidence |
| --- | --- | --- |
| Modelos with `FilingBuilder` | 130, 303, 390 (3 of ~21) | `src/aeat/application/filing/_builders/` |
| Modelos with formula ruleset | 130 (2024, 2025), 303 (2024, 2025) | `src/aeat/domain/formulas/_rulesets/` |
| Casilla catalogue size per modelo | 130: 4 · 303: 4 · 390: 3 | `corpus/casillas/modelo_{130,303,390}/*.json` |
| PDF fixtures on disk | 3 synthetic reportlab-generated justificantes | `tests/fixtures/justificantes/` |
| PDF parsing backends | `pdfplumber` only (text extraction) | `src/aeat/domain/justificante/_parsers/_pdfplumber_backend.py:15` |
| Round-trip verification primitive | `Engine.audit_against` emits `Discrepancy` records | `src/aeat/domain/formulas/_engine.py` |
| `aeat.domain.justificante` scope | Receipt metadata only (CSV + totales + modelo + período) | `src/aeat/domain/justificante/_schema.py` |
| Existing related ADRs | `2026-04-12-justificante-parser-adr`, `2026-04-12-filing-draft-engine-adr`, `2026-04-13-filing-complementaria-adr`, `2026-04-20-pdf-import-adr` | `.vault/adr/` |
| Open GitHub issues | #271 (this PR), #272 (cert-dependent), #233 (EPIC), #222 (fetch live), #228 (EPIC C13) | — |

The `audit_against` primitive is the biggest unexpected asset: round-trip verification is already implemented at the formula-engine layer. The bottleneck is **extraction fidelity** (cluster D) and **catalogue completeness** (cluster B), not math.

## Cluster decomposition

Each cluster is a candidate for its own vaultspec `research → ADR → plan` triplet. The `blocked-by` column encodes the minimum dependency graph.

| # | Cluster | Scope summary | Blocked by |
| --- | --- | --- | --- |
| A | **PDF taxonomy** | Document the AEAT PDF zoo: justificante vs. declaración vs. borrador vs. predeclaración vs. datos fiscales; decide which one(s) each import flow targets; correct the naming drift in `aeat.domain.justificante`. | — |
| B | **Casilla schema completeness** | Audit casilla corpus vs. real modelo form dimensions; define a per-modelo "schema-complete" bar; enumerate a delivery order. | A |
| C | **Real-PDF fixture corpus** | Sourcing policy (Kent's own filings · AEAT sandbox · community-scrubbed); PII redaction protocol; commit policy (in-tree vs. submodule vs. LFS vs. external); hash-pinning + provenance chain; coverage matrix modelo × año × layout revision. | A |
| D | **Per-modelo declaración extractor** | Layout RE via pdfplumber coordinate maps; per-modelo extractor contract; registry pattern mirroring `FilingBuilder`; AEAT template-drift strategy; MVP scope = 130 + 303 (simplest two with existing rulesets). | A, B, C |
| E | **Round-trip calculation verification** | Wire `audit_against` into the import pipeline; discrepancy classification (extraction · formula · AEAT-rule · rounding); user-facing verdict (verified / needs-review); CLI surface. | D |
| F | **Modelo 100 (RENTA) deep-dive** | Multi-page / multi-anexo traversal; borrador semantics; conditional sections by régimen / estado civil; scope recommendation ("summary block MVP" vs. "full declaration"); likely its own EPIC. | A, B, C |
| G | **`aeat.domain.justificante` reframing** | Decide: rename → `aeat.receipts`? narrow docs? keep as-is with explicit scope note? Backwards-compat for #271 amendment baseline must survive. | A |
| H | **Integration tests + CI surface** | Real-PDF parsing tests marked `live_read` + gated; per-modelo extraction-quality metric; AEAT template-drift regression tracking; dashboard / CI artifact for each run. | D, E |

Order of delivery (topological): **A → B → C → D → E → F → G → H**. Clusters G and H can slip alongside later clusters without blocking.

## Cross-cutting constraints (inherited from project mandates)

- Every strict/frozen pydantic model at every boundary. No bare dicts.
- Zero cert-auth coupling. These clusters operate on files on disk; no AEAT network calls.
- Zero live-write coupling. No path here registers `aeat submission submit`.
- All tests `@pytest.mark.unit` with module-level markers; no skips, no mocks in live tests, no `unittest`.
- Trilingual `Translatable` for any user-visible narrative.
- `FilingDraftError`-rooted exceptions for filing-side errors; new `PdfImportError` under cluster D would inherit the same root.
- Relative imports inside `src/aeat/`.
- Kent-observable acceptance criteria on every child issue.

## Risks & open questions

1. **AEAT PDF licensing / PII**: real PDFs contain Kent's tax data. We need an explicit ADR on sourcing + scrubbing before any real fixture lands.
2. **AEAT template drift**: AEAT refreshes templates yearly (form revisions inside a fiscal year too). The extractor registry must key on `(modelo, template_revision)`, not just `(modelo, año)`.
3. **XFA forms**: older Renta PDFs used Adobe XFA (XML inside PDF). `pdfplumber` cannot read XFA fields. Need a fallback strategy (pypdf's form-field reader, or rendering + OCR).
4. **Scanned / image-only PDFs**: Kent may have older receipts that are pure scans. OCR (`pytesseract` / `easyocr`) becomes a candidate back-end for cluster D. Adds a heavy dependency.
5. **Formula-engine coverage**: even on the happy path, only modelos 130 and 303 have rulesets. Cluster E's verification is bounded by cluster B's schema + the ruleset registry.
6. **Scope creep into schema #9**: extraction work exposes casilla-schema gaps. We may end up driving #9's corpus completion in parallel.
7. **RENTA (Modelo 100)** alone is arguably a full EPIC; fitting it into cluster F may still require a further split.

## Exit criteria for the umbrella

The umbrella is "done" when:

- All 8 clusters have their `research → ADR → plan` triplet committed to `.vault/`.
- A tracking EPIC issue on GitHub lists every cluster with a pointer to its three artefacts.
- The coverage matrices (`docs/coverage/modelos.md`, `docs/coverage/kent-capabilities.md`) have a new row per cluster reflecting its "not-started / in-plan / in-exec / done" state.
- No cluster leaves a gap in the dependency graph.
