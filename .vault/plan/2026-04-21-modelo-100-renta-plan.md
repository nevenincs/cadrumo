---
tags:
  - "#plan"
  - "#modelo-100-renta"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-modelo-100-renta-adr]]"
  - "[[2026-04-21-modelo-100-renta-research]]"
---

# `modelo-100-renta` plan (summary-block MVP)

## Phase 1 — `aeat.adapters.inbound.borrador` module skeleton

### Step 1.1 — Package + schema

Create `src/aeat/adapters/inbound/borrador/` per ADR §1. `BorradorFiling` extends `DeclaracionFiling` with `artefact_kind`.

### Step 1.2 — Detection + extractor ABC

`_detect.py`, `_extractor.py`, `_extractors/__init__.py` (empty registry).

### Step 1.3 — Unit tests

Scaffold-shape tests (strict+frozen, JSON round-trip).

## Phase 2 — Modelo 100 summary-block extractor

### Step 2.1 — L3 generator `modelo_100_summary_generator.py`

Renders 3 pages: cover, detail, summary. Summary block on page 3 with casillas 001–030. Reuses cluster-C `_generator_shared.py`.

### Step 2.2 — Extractor `_extractors/modelo_100_summary_v2025.py`

Label-regex primary; bbox fallback scoped to last 2 pages.

### Step 2.3 — Tests

`test_parse_borrador_summary_l3` parametrised over 200 life shapes; assert all 30 casillas extracted.

## Phase 3 — Modelo 100 summary ruleset

### Step 3.1 — `modelo_100_summary_2025.py` ruleset

~5 derivations + `_TARIFA_2025` tarifa table from BOE.

### Step 3.2 — Ruleset tests

Unit tests per derivation; one integration test running `audit_against` on the full summary.

## Phase 4 — CLI + verification

### Step 4.1 — `--from-borrador` flag

Extend `aeat filing import`.

### Step 4.2 — Artefact-kind detection integration

When Kent drops an unknown PDF, detect kind first, then route.

### Step 4.3 — Verification chaining

When `parse_borrador` yields a `BorradorFiling` for 2024+, chain cluster-E's `verify_declaracion` with the summary ruleset.

## Phase 5 — L1 fixture sourcing

### Step 5.1 — Generate ≥ 5 Renta-Web-Open anchors per año

Manual action: visit `https://sede.agenciatributaria.gob.es/...renta-web-open...`, feed 5 synthetic life shapes, download the "vista previa" PDFs. Commit to `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_100/2024/` with SHA-256 in `_manifest.json`. (This is the one manual step in this cluster; the script produces the PDFs, a human saves them.)

### Step 5.2 — Fidelity validation test

`test_modelo_100_summary_fidelity_l1` parametrised over the L1 anchors; xfail until anchors land.

## Phase 6 — Audit + docs

Subagent code review per phase. `docs/concepts/aeat-pdfs.md` Renta section expanded. Coverage matrix updated.

## Exit criteria per phase

- `uv run ruff check src/aeat/adapters/inbound/borrador/ src/aeat/domain/formulas/_rulesets/modelo_100_summary_2025.py` — clean.
- `uv run ty check` — clean.
- `uv run pytest -m unit src/aeat/adapters/inbound/borrador/ src/aeat/domain/formulas/_rulesets/` — green.
- Code-review audit: zero severity-high findings.

## Kent UX roleplay

- Kent downloads his 2024 Renta borrador from Portal Renta (with cert) OR runs Renta Web Open anonymously.
- Runs `aeat filing import --from-borrador ~/Downloads/borrador-renta-2024.pdf`.
- Sees: "Detected artefact: borrador (Modelo 100, 2024). 30 of 30 summary casillas extracted. Verified against modelo_100_summary_ruleset_2025: cuota diferencial re-derived to within 0.01 €. Status: verified."
- Kent now has a local draft that reflects what AEAT computed for him — he can confidently submit (when live-submission returns in 1.0.0) or amend later.

## Non-goals

- Any anexo-level extraction.
- Pre-2020 Renta XFA.
- Régimen branching beyond summary scope.
- Renta rectificativa flow.

## Follow-up sub-EPIC

Open **sub-EPIC #305-F-full** for full-anexo coverage; this plan explicitly defers. Each anexo is its own issue once summary ships.
