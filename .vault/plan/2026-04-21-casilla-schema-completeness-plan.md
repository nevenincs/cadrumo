---
tags:
  - "#plan"
  - "#casilla-schema-completeness"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-research]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---

# `casilla-schema-completeness` plan

## Goal

Land the `CasillaSchema` provenance extension + cross-validation test + Modelo 130 full 19-casilla corpus + Modelo 303 full ~88-casilla corpus, in that order. Modelo 390 corpus is scoped by this plan but gated on ruleset #221.

## Phase 1 — Schema shape extension (no new casillas)

### Step 1.1 — Extend `CasillaSchema` with provenance

**Files**:

- `src/aeat/application/filing/_protocols.py` — add `CasillaSource` pydantic record; extend `CasillaSchema` with `label`, `description`, `sources`, `valid_from`, `valid_to`.
- `src/aeat/application/filing/__init__.py` — re-export `CasillaSource`.

**Tests**:

- `src/aeat/application/filing/test_schema.py` (new) — `@pytest.mark.unit`, `@pytest.mark.domain_infra`. Round-trip pydantic JSON; strict-mode rejection of unknown fields; rejection of empty `sources` tuple on required casillas; `valid_from ≤ valid_to` validator.

### Step 1.2 — Migrate existing corpus files

The three existing corpus files gain minimum-viable `label`, `sources`, `valid_from`:

- `corpus/casillas/modelo_130/2025Q4.json` → retrofit 4 casillas with label + single `interactive_form_xml` source citation (provisional; step 3.1 replaces it).
- `corpus/casillas/modelo_303/2025Q4.json` → same.
- `corpus/casillas/modelo_390/2025.json` → same.

Each casilla's `label` is the authoritative Spanish text from the AEAT form, with English + Hungarian left `None` or a placeholder flagged `needs_human_review` — the loader accepts partial translations.

### Step 1.3 — Cross-validation test

**File**: `src/aeat/application/filing/test_schema_completeness.py` (new).

- `test_corpus_covers_every_ruleset_casilla[modelo, año]` — parametrised over `{(130, 2024), (130, 2025), (303, 2024), (303, 2025)}`. Xfail for 390 until #221.
- `test_ruleset_has_formula_for_every_corpus_formula_input[modelo, año]` — inverse direction; catches the "corpus says casilla 18 = f(02, 03) but no ruleset implements it" failure already present in the current corpus.
- Both tests run on `uv run pytest -m unit` and will initially **fail** for Modelo 130 (5 ruleset-only casillas missing from corpus) and Modelo 303 (11 ruleset-only casillas missing from corpus). Phase 2 and 3 fix them.

**Gate**: Phase 1 merges even with failing completeness tests — they are added with `@pytest.mark.xfail(strict=True, reason="corpus completion tracked in phase 2/3")` so they convert to unexpected passes (and hard-fail the build) the moment a phase closes its gap.

## Phase 2 — Modelo 130 corpus completion (19 casillas)

### Step 2.1 — Add the interactive-form-XML loader

**New module**: `src/aeat/domain/schema/_forms_xml_loader.py`.

- Reads AEAT's public interactive-form XML for `(modelo, año)` from the published URL pattern `https://sede.agenciatributaria.gob.es/Sede/xml/modelo-N-año.xml` (confirm exact URL before landing — AEAT publishes pilot XMLs at varying endpoints; the loader's URL map is a single hash to update annually).
- Writes raw XML to `corpus/_sources/interactive_forms/modelo_N/YYYY.xml`; records SHA-256.
- Parses XML → strict `CasillaSchema` tuples with `sources` carrying the URL + SHA-256.
- Serialises to `corpus/casillas/modelo_N/YYYY.json` with sorted keys.

**Just recipe**: `just regen-corpus` iterates every registered `(modelo, año)` pair.

**Tests**: `src/aeat/domain/schema/test_forms_xml_loader.py` — round-trip a committed sample XML through the loader; assert byte-identical JSON output.

### Step 2.2 — Regenerate Modelo 130 corpus

`just regen-corpus --modelo 130 --year 2025` produces the 19-casilla JSON.

### Step 2.3 — Extend Modelo 130 ruleset to match

**File**: `src/aeat/domain/formulas/_rulesets/modelo_130_2025.py`.

- For every casilla in the regenerated corpus, register either a formula (if derived) or a literal entry (if user-supplied) so the ruleset's casilla set equals the corpus's.
- Reuse the existing `Engine` DSL; no formula-engine changes.
- Cross-validation tests from step 1.3 flip from xfail to pass.

### Step 2.4 — Regression test on a real Kent-sized draft

**New file**: `src/aeat/application/filing/test_modelo_130_real_shape.py`.

- Builds a draft with every 19-casilla input set; asserts `draft.values` has 19 entries, every required casilla populated, every computed casilla re-derivable via `Engine.audit_against` to zero discrepancies.
- Marker: `@pytest.mark.unit`, `@pytest.mark.domain_financial_input`.

## Phase 3 — Modelo 303 corpus completion (~88 casillas)

Mirrors phase 2 with a much larger loader output. Estimated 3× the manual label-verification effort.

### Step 3.1 — Regenerate

`just regen-corpus --modelo 303 --year 2025`.

### Step 3.2 — Extend Modelo 303 ruleset

`src/aeat/domain/formulas/_rulesets/modelo_303_2025.py` extended from 12 formula casillas + references to the full ~88-casilla set. Where a casilla is a literal (user-supplied), register it as such.

### Step 3.3 — Add `valid_from` / `valid_to` for the 2024-09 renumbering

Modelo 303 renumbered casillas from 2024-09-01 onward (*autoliquidación rectificativa*). The corpus gains two coexisting version rows: `2024.1.json` (pre-September) and `2024.2.json` (post-September), each with per-casilla `valid_from` / `valid_to`. The schema provider picks by period.

### Step 3.4 — Regression test

Parallel to step 2.4 but for a Modelo 303 draft covering the common "freelance SII filer" shape: inputs on casillas 01–30, computed outputs on 31–88.

## Phase 4 — Modelo 390 corpus (gated on #221)

### Step 4.1 — Regenerate corpus

`just regen-corpus --modelo 390 --year 2025` produces a large JSON (~680 casillas).

### Step 4.2 — Mark as ruleset-blocked

The cross-validation test stays xfail'd for 390 until #221 lands. Coverage matrix row shows `🚧 ruleset` alongside `✅ corpus`.

No ruleset extension in this plan.

## Phase 5 — Remaining quarterly modelos (111, 115, 180, 190)

Each follows the phase-2 shape: regen corpus, extend/create ruleset, add regression test. Not in the scope of this plan's PR — each ships as its own issue under EPIC #305.

## Phase 6 — Docs + coverage matrix

- `docs/coverage/modelos.md` — new columns `casillas_in_corpus`, `real_form_casilla_count`, `coverage_%`.
- `docs/concepts/casilla-schema.md` (new) — one-paragraph intro: what a corpus file is, how to regenerate, how to read provenance.

## Kent UX roleplay

Kent does not directly observe phase 1. From phase 2 onward, Kent does:

- `aeat filing build --modelo 130 --period 2025Q1 --inputs inputs.json` now produces a draft with **19 casillas**, not 4. Kent running `aeat filing show` sees every casilla row.
- `aeat filing validate` reports findings against all 19 casillas, surfacing any required-but-empty ones. Previously it saw 4 and said "all good."
- From phase 3: the same pattern for Modelo 303.
- Regression test hammering the same flow is added in each phase; Kent's "complete the form and submit" journey is non-regressing across the landing of each extension.

## Live-testing surface (honest)

- **Unit tests**: run on every commit; cover corpus ↔ ruleset agreement, schema round-trip, built-draft shape.
- **Real-PDF tests**: **blocked on cluster C**. This plan does not claim coverage against real AEAT declaración PDFs — cluster D wires those once fixtures exist.
- **Audit loop**: phase 1 ships the xfail scaffolding so completeness is observable from day one. Every subsequent phase flips one xfail to pass.

## Code-review gate

After each phase merges:

- `vaultspec-code-review` persona runs over the diff.
- A standalone audit file under `.vault/audit/2026-04-21-casilla-schema-phase-N-audit.md` records the review outcome, open risks, and Kent-observable acceptance.

## Quality gates per phase

- `uv run ruff check src/aeat/application/filing/ src/aeat/domain/schema/ src/aeat/domain/formulas/ corpus/` — clean.
- `uv run ty check src/aeat/application/filing/ src/aeat/domain/schema/ src/aeat/domain/formulas/` — clean.
- `uv run pytest -m unit src/aeat/application/filing/ src/aeat/domain/schema/ src/aeat/domain/formulas/` — green, including newly-flipped completeness assertions.
- CI on the PR — green on both Ubuntu + Windows runners.

## Non-goals

- No PDF extractor work (cluster D).
- No Modelo 100 coverage (cluster F).
- No Modelo 390 ruleset (#221).
- No translation completeness (labels may ship ES-only with EN/HU placeholders).
- No runtime loading changes — corpus is still loaded at import time from JSON files.
