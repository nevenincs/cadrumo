---
tags:
  - "#adr"
  - "#calc-verification"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-calc-verification-research]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---

# `calc-verification` adr: `classify-discrepancies-then-produce-kent-readable-verdict` | (**status:** `accepted`)

## Problem Statement

Calc-verification must turn the formula-engine's raw `AuditReport` into a Kent-readable verdict classified by cause, persisted alongside the draft, and surfaced via the CLI. It must handle the cases where the ruleset is incomplete (`unverifiable`), partial (coverage %), or fully authoritative (`verified` or `needs_review`).

## Considerations

- `Engine.audit_against` already produces discrepancy tuples; only classification + narrative remain.
- `ExtractedCasilla.extraction_confidence` (cluster A record) is the main signal for cause 1 (extractor unreliability).
- Kent cares about a single verdict word first, a readable breakdown second, a machine-processable record third — in that order.
- Verdicts persist so future amendment flows can reference "this filing was calc-verified at timestamp T against ruleset vR".
- Project mandate: Translatable narratives; pydantic v2 strict+frozen; no bare dicts.

## Constraints

- **No new formula engine**. Cluster E is a consumer, not a producer, of the formula engine.
- **Strict+frozen pydantic records** per ADR §3 of the research.
- **Deterministic verdict**: given identical `(draft, declaracion, ruleset)` inputs, the verdict is byte-identical (modulo `verified_at`).
- **Errors**: `VerificationError < AeatError` for catastrophic failures; not-verifiable ruleset gaps are a normal status, not errors.

## Implementation

### 1. Module layout

```
src/aeat/application/verification/
    __init__.py       # public API: verify_declaracion, VerificationVerdict,
                      # DiscrepancyCause, ClassifiedDiscrepancy, VerificationError
    _schema.py        # records
    _errors.py
    _verify.py        # verify_declaracion(draft, declaracion, ruleset) -> Verdict
    _classify.py      # classify_discrepancy(ad, declaracion.warnings, ruleset)
    test_verify.py
    test_classify.py
```

### 2. `verify_declaracion` function

```python
def verify_declaracion(
    draft: FilingDraft,
    declaracion: DeclaracionFiling,
    ruleset: Ruleset | None,       # None → status=unverifiable
    *,
    tolerance: Decimal = Decimal("0.01"),
) -> VerificationVerdict: ...
```

Flow:

1. If `ruleset is None` → return `VerificationVerdict(status=unverifiable, coverage=0.0, ...)`.
2. Compute `provided = {c.casilla_id: c.value for c in draft.values if c.value is not None}`.
3. `report = engine.audit_against(ruleset, provided, tolerance)`.
4. For each `report.discrepancies` entry → `classify_discrepancy(...)` → `ClassifiedDiscrepancy`.
5. Compute coverage = `|ruleset.casilla_ids ∩ provided.keys()| / |ruleset.casilla_ids|`.
6. Derive status per the research §`status rules`.
7. Compose narrative: trilingual, 2–3 sentences.

### 3. Classifier

`classify_discrepancy(discrepancy, declaracion_warnings, ruleset) -> (DiscrepancyCause, Translatable)`:

- If the discrepant casilla appears in `declaracion_warnings` with `code in {"bbox-fallback", "ambiguous-label"}` → `EXTRACTION_UNRELIABLE`.
- Elif `|discrepancy.delta| < 10 * tolerance` AND casilla is computed → `ROUNDING`.
- Elif discrepancy.casilla_id NOT in `ruleset.casilla_ids` → `UNMODELLED_RULE`.
- Else → `CORRECTNESS_DIVERGENCE`.

Each branch produces a Spanish + English + Hungarian rationale, with a suggested action ("Revisa manualmente el PDF en casilla 04." / "Review casilla 04 in the PDF manually.").

### 4. CLI wiring

Extend `aeat filing import --from-declaracion` to chain verification automatically when a ruleset exists; add `aeat filing verify <draft-id>` for on-demand re-verification.

CLI output example (English):

```
Imported draft 75a6bb365c8d0ee7 from declaración (Modelo 130, 2025Q1).
19 of 19 casillas extracted.
Verified against ruleset modelo_130_2025: every computed casilla re-derived within 0.01 €.
Status: verified
```

With discrepancies:

```
Imported draft 75a6bb365c8d0ee7 from declaración (Modelo 303, 2025Q1).
86 of 88 casillas extracted; 2 extraction warnings.
Verified against ruleset modelo_303_2025: 3 discrepancies.
  - casilla 44: expected 1234.00, actual 1234.56 — EXTRACTION_UNRELIABLE (bbox fallback used)
  - casilla 71: expected 2100.00, actual 2100.03 — ROUNDING (accepted)
  - casilla 80: expected 500.00, actual 505.00 — CORRECTNESS_DIVERGENCE (review)
Status: needs_review
```

### 5. Persistence

`aeat filing import` writes three JSON files per imported filing: `{filename}.json` (FilingDraft), `{filename}_declaracion.json` (DeclaracionFiling), `{filename}_verdict.json` (VerificationVerdict). All strict+frozen round-trippable.

### 6. Tests

- `test_verify_all_literals_no_discrepancies` — synthetic draft matching ruleset output exactly → `verified`.
- `test_verify_rounding_classification` — seeded delta of 0.03€ on a computed casilla → classified `ROUNDING`.
- `test_verify_extraction_unreliable_propagation` — declaracion has bbox-fallback warning → classified `EXTRACTION_UNRELIABLE`.
- `test_verify_no_ruleset_unverifiable` — passing `ruleset=None` → `status=unverifiable`.
- `test_verify_partial_coverage_needs_review` — half the ruleset casillas in the draft → `coverage ≈ 0.5`, `status=needs_review`.

Markers: `@pytest.mark.unit`, `@pytest.mark.domain_financial_input`, `@pytest.mark.fixture_tier_l3`.

### 7. Out of scope

- No changes to `Engine.audit_against` itself.
- No changes to the `FilingDraft` hash.
- No submission/amendment coupling.

## Consequences

- Kent gets a single-word status + a Kent-readable narrative for every imported filing.
- Discrepancies are categorised so Kent knows which ones need action.
- Verdicts persist; amendment flows (#234, #235) can reference them.
- The classifier is isolated — new cause categories are cheap to add.
