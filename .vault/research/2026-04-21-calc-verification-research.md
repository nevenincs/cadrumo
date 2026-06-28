---
tags:
  - "#research"
  - "#calc-verification"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---

# calc-verification research

## Problem

Extraction (cluster D) produces `(casilla_id, printed_value)` tuples. Calc-verification runs the project's formula engine over those inputs and compares computed casilla outputs against the values AEAT's printed. Discrepancies identify one of four causes: (a) extractor bug, (b) formula bug on our side, (c) un-modelled AEAT rule, (d) rounding drift. Kent wants a "verified / needs review" verdict with a structured list of divergences; we want the verdict itself to be a product surface cluster E owns.

## The primitive is already built

`src/aeat/domain/formulas/_engine.py` — `Engine.audit_against(ruleset, provided: Mapping[str, Decimal], tolerance: Decimal = Decimal("0.01")) -> AuditReport`. The function:

- Derives every computed casilla from the supplied literals.
- Diffs computed against `provided`.
- Returns a report enumerating `Discrepancy(casilla_id, expected, actual, delta)` records.

This is almost exactly what cluster E needs. What's missing:

1. **Cause classification** — `audit_against` reports "casilla 04 expected 250, got 255" but doesn't say whether the 5€ gap is an extraction bug (OCR misread) or a rounding issue.
2. **Extraction-adjacent warnings** — if extraction warned that casilla 04 was recovered via bbox fallback (lower confidence), that context should propagate into the verdict.
3. **Kent-readable verdict** — the `AuditReport` is machine-shaped; we need a trilingual `Translatable`-based narrative.
4. **CLI surface** — `aeat filing verify` doesn't exist yet.

## Discrepancy cause classifier

Four causes, detected in order:

1. **Extractor low-confidence**: if the discrepant casilla's `ExtractedCasilla.extraction_confidence < 0.9`, classify as `EXTRACTION_UNRELIABLE`. Kent's remedy: re-check the PDF manually.
2. **Rounding drift**: if `|delta| < 10 * tolerance` AND the discrepancy is on a casilla with `formula_inputs` (a computed one), classify as `ROUNDING`. Kent's remedy: accept.
3. **Formula gap**: if the ruleset doesn't know the casilla at all (not in its `casilla_ids`), classify as `UNMODELLED_RULE`. Kent's remedy: file a bug, accept the extracted value as-is.
4. **Correctness divergence** (default): classify as `CORRECTNESS_DIVERGENCE`. Kent's remedy: review — either the extractor misread the PDF, or we have a formula bug.

The classifier is pure; it reads the `AuditReport` + the `DeclaracionFiling.warnings` list + the ruleset metadata; it produces a `VerificationVerdict` record.

## `VerificationVerdict` record

```python
class DiscrepancyCause(StrEnum):
    EXTRACTION_UNRELIABLE = "extraction_unreliable"
    ROUNDING = "rounding"
    UNMODELLED_RULE = "unmodelled_rule"
    CORRECTNESS_DIVERGENCE = "correctness_divergence"

class ClassifiedDiscrepancy(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    casilla_id: str
    expected: Decimal
    actual: Decimal
    delta: Decimal
    cause: DiscrepancyCause
    cause_rationale: Translatable

class VerificationVerdict(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    modelo: str
    period: str
    ruleset_version: str
    status: Literal["verified", "needs_review", "unverifiable"]
    discrepancies: tuple[ClassifiedDiscrepancy, ...]
    coverage: float                     # % of printed casillas that had a ruleset formula
    narrative: Translatable             # Kent-readable verdict summary
    verified_at: datetime
```

`status` rules:

- `verified` — no discrepancies at severity `CORRECTNESS_DIVERGENCE`; all others classifiable as `ROUNDING` or `UNMODELLED_RULE`.
- `needs_review` — at least one `CORRECTNESS_DIVERGENCE` or `EXTRACTION_UNRELIABLE`.
- `unverifiable` — no ruleset registered for `(modelo, año)`; coverage below threshold (< 30 %).

## CLI flow

```
aeat filing import --from-declaracion <pdf>
    → parse_declaracion(path)
    → build_draft(modelo, period, profile, extracted_values, schema_provider)
    → verify_declaracion(draft, declaracion, ruleset) → VerificationVerdict
    → persist(draft, declaracion, verdict)
    → render to console
```

`aeat filing verify <draft-id>` re-runs verification on a persisted draft; useful when Kent updates a value manually and wants to re-audit.

## Persistence

Verdicts persist alongside drafts under `AEAT_DRAFTS_DIR`:

```
{drafts_dir}/
    130_2025Q1_75a6bb365c8d0ee7.json     # FilingDraft
    130_2025Q1_75a6bb365c8d0ee7_declaracion.json  # DeclaracionFiling
    130_2025Q1_75a6bb365c8d0ee7_verdict.json       # VerificationVerdict
```

The three-file triplet is the full audit trail for one imported filing.

## Cross-cluster dependency

- Cluster B's ruleset completion (phases 2 + 3) is the upstream constraint. Verdicts for Modelo 130 become high-coverage once Modelo 130 has 19 ruleset entries; Modelo 303 once it has ~88; 390 blocked on #221.
- Cluster D's `extraction_confidence` feeds the classifier; cluster E is friendly to D's output regardless of `extraction_status` (even `partial` extractions can be partially verified).

## Open questions (ADR)

1. **Default tolerance**: `Decimal("0.01")` (1 cent) matches AEAT's precision. Does any modelo need different tolerance? Answer: **not by default**; per-casilla overrides permitted via the ruleset's metadata.
2. **Rounding-mode alignment**: AEAT uses `ROUND_HALF_UP` for monetary totals. Confirm the Engine uses the same. `src/aeat/domain/formulas/_engine.py` already pins `Decimal` arithmetic; spot-check in the implementation phase.
3. **Multi-currency**: N/A — AEAT filings are EUR only.
4. **Kent override**: if Kent manually edits a casilla post-import, does verification re-run automatically? Answer: **no**, explicit `aeat filing verify <id>` — avoid surprise CPU cost.
