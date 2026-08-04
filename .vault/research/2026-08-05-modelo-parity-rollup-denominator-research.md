---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:abfb2aa78d8053086e06ae13190a27ccb509ac6f233bfe4a1831eeb525c075f1'
related:
  - "[[2026-08-04-modelo-100-casilla-implementation-audit]]"
  - "[[2026-07-28-conformance-cli-first-conformance-measurement-audit]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-06-03-executable-parity-evidence-tier-contract-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-07-01-modelo-131-eo-modulos-engine-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---

# `modelo-parity-rollup` research: `Modelo revision parity denominator and bounded campaign`

The current registry can support an evidence-led parity campaign, but “full parity” cannot be reduced to one count. The validated portfolio is 73 modelos and 90 revision rows; the safe next step is a five-axis ledger with exact modelo/exercise/period coordinates, followed by a decision ADR before any production-wide parity changes.

## Findings

### The registry already exposes a portfolio-wide measurement boundary

The conformance surface renders one row per modelo revision and separates calculation, verification, evidence grounding, export, and authorization signals in `dev/registry/conformance/manager.py:224` and `dev/registry/conformance/manager.py:957`. A live measurement on 2026-08-05 found 73 modelos and 90 revisions. It measured 52 revisions with a non-empty calculation grade, 51 with verification expectations, and 39 that reconcile nothing; these are coverage facts, not correctness scores.

The model-law coverage implementation separately validates every revision through a validated snapshot and requires legal authority, official source guidance, and layout authority. It reports executable parity gaps when a formula-bearing revision lacks safe executable evidence: `src/cadrumo/domain/calculations/registry/_coverage.py:103` and `src/cadrumo/domain/calculations/registry/_coverage.py:121`. The current screen found no required evidence-tier gaps across the 90 revisions, but that floor does not establish formula correctness or complete behavioral parity.

### “Full parity” has five non-interchangeable denominators

The evidence supports measuring five dimensions separately; the authorizing ADR must decide whether and how to make this contract binding.

- Schema parity compares each exact `(modelo, ejercicio, period)` coordinate with the official form/layout for that year. The denominator is the year-specific form, not the newest or largest revision. This follows the schema-completeness boundary in `casilla-schema-completeness` and the revision-local identity rules in `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`.
- Formula and provenance parity asks whether each legally deterministic casilla with authoritative inputs has exactly one typed producer, a matching formula back-reference, and preserved legal/source provenance. Manual or upstream values are not failures when their reason is explicit.
- Legal/source parity asks whether every formula, parameter, binding, and relation cites the applicable authoritative corpus. Revision-level evidence-tier presence is a floor, not a per-casilla proof.
- Cross-model handoff parity asks whether every legally required dependency has one canonical relation or aggregation path, correct period applicability, clean-state behavior, and provenance. The relevant mechanism taxonomy is `calculation-aggregation-taxonomy`.
- Behavioral verification parity asks for real registry/runtime proof of every claimed producer or handoff. Numeric correctness requires an independent AEAT, BOE, workbook, or live-oracle expected value; structural wiring tests prove wiring only.

A single scalar over all printed casillas would combine different populations and would hide the distinction between form inventory, deterministic calculations, upstream observations, and independent checking. A latest-revision proxy would also misstate historical forms. The evidence therefore favors dimension-specific coverage over a composite percentage.

### The portfolio denominator must be paired with a finite annual matrix

The portfolio denominator is the validated 73-modelo/90-revision inventory. It is useful for structural and governance coverage, but it is not an annual behavioral denominator. An open-ended revision such as `y-siguientes` cannot stand in for every future year.

The behavioral denominator should be an explicit finite set of exact `(modelo, filing_year, period)` coordinates. For each coordinate, the ledger must retain the selected law-determined revision, official form/layout source, declared casilla population, deterministic producer population, handoff population, and verification population. Missing or unsupported coordinates must be classified rather than silently omitted.

### `D2025` is not a canonical repository coordinate

Repository-wide exact-token search found no standalone `D2025` document, symbol, revision, or modelo identifier. The actual declaration coordinate is the tuple of modelo, exercise, period, template revision, and law-selected registry revision. The declaration schema exposes template revision identity in `src/cadrumo/adapters/inbound/declaracion/_schema.py:31`; the M100 annual revision declares `id = "2025"` in `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml:2`.

For this research, the surrounding M100 evidence permits the provisional interpretation “Modelo 100, ejercicio 2025, annual period `0A`, registry revision `2025`.” That interpretation must not be generalized to all modelos, to Anexo D, or to a global revision class without an explicit user-facing qualification.

### M100 is a bounded example of why count equalization is unsafe

The M100 audit covers six annual revisions from 2020 through 2025 and records 11,337 revision-casilla records. After schema and reverse formula-wiring repairs, 2025 contains 2,239 casillas, 215 formulas, and 64 bindings; 2024 contains 2,093 casillas, 187 formulas, and 65 bindings. The 2024-to-2025 drift is therefore a real measured change, not evidence that one year should be cloned into the other: `.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:113`.

Three inherited 2025 rows remain semantically bounded gaps rather than safe copy targets. Casilla `0150` changes from a 2024 tiered formula to a 2025 manual row and depends on a 2024-only profile selector; `0613` depends on monthly family facts that the current profile cannot represent outside 2024; `1481` is a 2024 Modelo 131 relation-prefill whose 2025 aggregation semantics are unresolved. The focus-row evidence is recorded in `.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:186`. These rows require focused legal/profile/aggregation decisions and external numeric proof before any manual-to-computed or cross-model transition.

### Existing independent oracle evidence can be enrolled only by exact mapping

The current conformance screen reports 59 independently checked casillas out of a 1,261-casilla reconciliation population and 39 revisions that reconcile nothing. Existing bundled oracle evidence can improve that numerator only when the modelo, revision, casilla identity, input coordinate, and expected output map one-to-one without changing formulas, profiles, relations, or legal interpretation. The conformance audit warns that independent checking is coverage of checking, never a correctness score: `dev/registry/conformance/manager.py:248`.

An exact enrollment tranche is therefore safe when it only records an already-proven observation and adds real tests around that mapping. Ambiguous oracle mappings, inferred values, newly invented scenarios, or any change to a producer remain outside this tranche.

### The decision boundary has three implementation options

- Bulk cloning or count equalization would be fast but would conflate form evolution with calculation depth and can silently create false producers. It is rejected by the M100 evidence.
- Treating the newest revision as the canonical parity baseline would simplify comparison but would erase legal historical differences and misclassify intentional manual/upstream rows. It is rejected.
- A five-axis ledger over the 73/90 portfolio plus a finite annual matrix preserves the exact official denominator, makes divergences measurable, and routes semantic gaps to focused ADRs. It is the evidence-favored option for the roll-up decision.

The research does not decide the project-wide acceptance threshold, finite annual matrix, oracle-enrollment storage contract, or the producer semantics for M100 `0150`, `0613`, and `1481`. Those decisions belong in the roll-up ADR and its focused addenda.

## Sources

- `src/cadrumo/domain/calculations/registry/_coverage.py:103`
- `src/cadrumo/domain/calculations/registry/_coverage.py:121`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`
- `src/cadrumo/adapters/inbound/declaracion/_schema.py:31`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml:2`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_drift_detection.py`
- `dev/registry/conformance/manager.py:224`
- `dev/registry/conformance/manager.py:248`
- `dev/registry/conformance/manager.py:957`
- `dev/registry/conformance/manager.py:1239`
- `.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:113`
- `.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:186`
- `.vault/adr/2026-04-21-casilla-schema-completeness-adr.md`
- `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`
- `.vault/adr/2026-07-01-modelo-131-eo-modulos-engine-adr.md`
- `uv run --no-sync python -m dev.registry.conformance coverage` (run 2026-08-05)
