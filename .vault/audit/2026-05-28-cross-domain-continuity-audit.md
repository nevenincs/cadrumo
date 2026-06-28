---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-27-cross-domain-continuity-audit]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
---


# `cross-domain-continuity` audit: `wave-3-commit-review`

## Scope

Wave-3 commit review covering W03.P14 (Modelo 200 pyme bracket temporal
coverage), W03.P15 (CLI bare-numeric casilla normalisation), and W03.P16
(M100 binding-to-schema agreement pin tests). Reviewed against the plan,
the corporate-entity calculation ADR, registry-authority-flow rule,
CLI-backend-boundary ADR, source-hygiene rule, and no-tautological-tests rule.
Each commit receives a verdict: ACCEPT, ACCEPT-WITH-FOLLOWUP, or REJECT.

---

## Findings

### W03.P14.S56 — 2024 pyme bracket backfill (e0606d819) — ACCEPT-WITH-FOLLOWUP

Bracket data correct: single-row `[2024-01-01, 2024-12-31]` window at
`marginal_rate = 0.23` added to `is.modelo-200.tipo-gravamen-pyme`. The
architectural decision (backfill within same revision rather than splitting)
is correct and consistent with the corporate-entity calculation ADR.

The S56 instruction required checking `is.modelo-200.cuota-integra-bracket-pyme`
and adding a 2024 row if it exists. Inspection confirms no such parameter
exists; the cuota-integra-bracket family covers only `general`,
`cooperative-protected`, `non-profit-special-regime`, and `new-entity`. The
pyme cuota flows through `tipo-gravamen-pyme` directly. Correctly left unmodified.

**FU-F (source-hygiene defect):** The TOML comment reads "Real Decreto-ley
4/**2004**" — transcription error for "Real Decreto-ley 4/**2024**"
(BOE-A-2024-7551). Wrong year in a legal citation is a defect under
`aeat-calculation-grounding`. Must be fixed in W09.

### W03.P14.S57 — Coverage validator (6d9a17d3a) — ACCEPT

`validate_bracket_table_temporal_coverage` correctly promotes runtime
`bracket_no_window` errors to load-time failures. The `_bracket_coverage_gaps`
algorithm handles sorted windows, open-ended revisions, open-ended bracket
windows (via `_FAR_FUTURE`), and day-boundary gaps with `timedelta(days=1)`.
Tail-gap logic is correct: only fires when `revision_to` is set, preventing
false positives on open-ended revisions. Scoped to `bracket_axis = "filing_period"`
only. Hexagonal placement correct.

### W03.P14.S55+S58 — Decision record + regression tests (fb4900e75) — ACCEPT

Step Record correctly cites LIS Art. 29 and AEAT Manual de Sociedades 2024.
Four regression tests satisfy the anti-tautology mandate: the cuota assertion
(`Decimal("23000.00")`) is derived from LIS Art. 29 2024 external authority.
Anti-tautology probe (`test_coverage_validator_fires_on_deliberate_gap`)
constructs a gapped fixture using `model_construct` and confirms the detector
fires — correctly documented. False-positive guard present.

### W03.P15.S59+S60 — Casilla normalisation + helpful error (c73d60493) — ACCEPT-WITH-FOLLOWUP

`_normalise_casilla_key` handles the three cases (one match, multiple matches,
no match) correctly with numeric-equality comparison. `_casilla_revision_for_work_unit`
is a read-only service call, consistent with CLI-backend-boundary ADR.
S60 improved error lists available prefixes. Locale keys scaffolded across
all four languages.

**FU-G (convention note):** S49 modality wiring code (W02.P12) was co-landed
in this W03.P15 commit. Code is correct; the one-Step-per-commit convention
is violated. Document in W09 as a historical note, no code change needed.

### W03.P15.S61 — Casilla normalisation tests (d39dc4328) — ACCEPT

Three real-adapter tests with `isolated_runtime_profile`, no mocks. Covers:
bare `69` normalises to `iva.resultado`; unknown `99999` surfaces `BadParameter`;
qualified key passes through unchanged. Seeding approach is consistent with
Wave-1 boundary test pattern.

### W03.P16.35e19b7d5 — Pre-alignment (35e19b7d5) — ACCEPT

Pure data correction: 18 M100 2025 binding TOML selector keys aligned from
legacy flat aliases to wizard-canonical namespaced form. No logic changed.
Test assertions updated to match. Correct per registry-authority-flow rule.

### W03.P16.S65 — M100 binding pin tests (e337c6af4) — ACCEPT

8 tests covering all 30 M100 2025 profile-sourced bindings. Correctly calls
`_profile_fact_index` and `_resolve_one` directly (not `resolve_profile_sourced_bindings`
which filters output). Anti-tautology: death-date deliberately absent, `_resolve_one`
returns `None`. Structural sentinel (count pinned at 30) acceptable.

**FU-H (minor):** The binding count sentinel needs a comment clarifying it
must be updated when bindings are intentionally added, not treated as a
permanence assertion.

---

## Summary Table

| SHA | Steps | Verdict |
|---|---|---|
| e0606d819 | S56 | ACCEPT-WITH-FOLLOWUP |
| 6d9a17d3a | S57 | ACCEPT |
| fb4900e75 | S55, S58 | ACCEPT |
| c73d60493 | S59, S60 (+ S49 co-land) | ACCEPT-WITH-FOLLOWUP |
| d39dc4328 | S61 | ACCEPT |
| 0bb8f1553 | exec records + plan closure | ACCEPT |
| 35e19b7d5 | P16 pre-alignment | ACCEPT |
| e337c6af4 | S65 | ACCEPT |
| 4b6b8e71b | exec record + plan closure | ACCEPT |

0 REJECT · 2 ACCEPT-WITH-FOLLOWUP · 7 ACCEPT.

---

## Recommendations

Wave-3 is structurally sound. Registry authority respected; no hexagonal leaks;
no shims; test quality high with proper anti-tautology probes. FU-F (legal
citation typo) is the most important item — in a production TOML file under
`aeat-calculation-grounding` rules. Add FU-F, FU-G, FU-H as Steps in W09.P41.

**Follow-up Steps for W09.P41:**

- **FU-F** — Fix "Real Decreto-ley 4/2004" → "Real Decreto-ley 4/2024"
  (BOE-A-2024-7551) in the comment block of
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`
  line 53. Source-hygiene defect in a legal citation.
- **FU-G** — Add W09 documentation note for S49 + S59/S60 co-landing in
  commit `c73d60493`. Convention violation recorded; no code change.
- **FU-H** — Add clarifying comment to the binding count sentinel (30) in
  `src/aeat/application/modelo/test_profile_binding_real_path.py`. One-line
  comment addition.
