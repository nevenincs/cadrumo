---
tags:
  - "#plan"
  - "#calc-verification"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-calc-verification-adr]]"
  - "[[2026-04-21-calc-verification-research]]"
---

# `calc-verification` plan

## Phase 1 — `src/aeat/application/verification/` module

### Step 1.1 — Package scaffolding

Create the six files per ADR §1. Imports are relative (per project mandate). Every record is strict+frozen.

### Step 1.2 — `verify_declaracion` implementation

Follow ADR §2 flow. Use `src/aeat/domain/formulas/_engine.py`'s `Engine` directly; no wrapper.

### Step 1.3 — Classifier

Follow ADR §3. Unit-testable in isolation (inputs are simple pydantic records; outputs are pure).

### Step 1.4 — Trilingual narratives

`_verify.py` owns narrative templates (ES authoritative; EN + HU companions). Generated via small format helpers, not string concat.

### Step 1.5 — Tests

Per ADR §6. Synthetic `(draft, declaracion, ruleset)` fixtures built in-test; no PDF dependency.

## Phase 2 — CLI `aeat filing verify`

### Step 2.1 — Command definition

`src/aeat/entrypoints/cli/filing/__init__.py` adds `@app.command("verify")`. Accepts a draft ID or path; finds the companion `_declaracion.json`; runs `verify_declaracion`.

### Step 2.2 — Import-chaining

When `aeat filing import --from-declaracion` runs and a ruleset exists, automatically chain verification and print the verdict alongside the draft render. Command exit code stays 0 on `needs_review` (non-fatal); 2 on hard CLI errors.

### Step 2.3 — Smoke tests

Parametrised CLI tests against synthetic fixtures; assert exit codes + verdict JSON on disk.

## Phase 3 — Coverage-matrix + docs

- `docs/coverage/modelos.md` gains a `Verification coverage %` column derived from the `VerificationVerdict.coverage` at last verify.
- `docs/concepts/calc-verification.md` — one page explaining what `verified` / `needs_review` / `unverifiable` mean for Kent.

## Phase 4 — Audit loop

Subagent code review over the phase-1 diff; any severity-high finding blocks phase 2; etc.

## Exit criteria per phase

- `uv run ruff check src/aeat/application/verification/ src/aeat/entrypoints/cli/filing/` — clean.
- `uv run ty check src/aeat/application/verification/ src/aeat/entrypoints/cli/filing/` — clean.
- `uv run pytest -m unit src/aeat/application/verification/ src/aeat/entrypoints/cli/filing/` — green.
- Code-review audit: zero severity-high findings.

## Kent UX roleplay

- Kent imports a declaración. Three outcomes possible:
    - "Status: verified — every computed casilla re-derived within 0.01 €." Kent proceeds.
    - "Status: needs_review — 2 discrepancies. Casilla 44 looks like an extraction-reliability issue (bbox fallback); casilla 80 differs by €5.00 (review)." Kent opens the PDF, checks casilla 44 and 80, fixes the one the extractor got wrong, re-runs `aeat filing verify`.
    - "Status: unverifiable — no ruleset registered for Modelo 390 2025." Kent knows this is cluster-B / #221 gap; the draft still lands, just without calc-verification.

## Non-goals

- No formula-engine changes.
- No live AEAT calls.
- No visual UI — CLI only.
- No auto-reconciliation of discrepancies (Kent reviews).
