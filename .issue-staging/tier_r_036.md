**Kent success moment:** Kent has the declaración PDF of his Modelo 036 filing. He runs `aeat filing import --from-declaracion <pdf>`. The tool extracts every required declarative field (named fields, not computed casillas) deterministically and presents them as a structured filing record.

## Tier — R (Registration / Declaration form)

This is a **registration / informative declaration form**, not a liquidation. There is no formula engine output — only named-field extraction against a BOE template. No calc-verification applies.

## Scope

Modelo 036 — declaración censal de alta, modificación o baja (IAE, IVA, IRPF regímenes). Named fields: causa, epígrafe IAE, regímenes.

## Current state (2026-04-22 audit)

Declaración extractor MVP (5 named fields). No L2 fixture — regex patterns are best-effort. No integration test. Critical for Kent autónomo onboarding.

## Definition of Done — pass criteria

### Named-field schema

- [ ] Pydantic v2 frozen model `Modelo036Filing` with **every** BOE-mandated declarative field (enumerate every field in PR body, each with BOE / Orden Ministerial citation specifying the exact page/box)
- [ ] Current 3–5 field MVP is explicitly replaced with the full field inventory — document the delta
- [ ] Enum types for all closed catalogues (`CausaPresentacion`, `RegimenIVA`, `RegimenIRPF`, epígrafes IAE, etc.)
- [ ] Values that carry `PENDIENTE_VERIFICACION` / `SOSPECHOSO` markers flagged by the extractor

### Extractor

- [ ] `src/aeat/declaracion/_extractors/modelo_036_v2025.py` named-field patterns verified against a **real L2 fixture** (not speculative regex)
- [ ] Extractor confidence ≥ 0.8 on every named field for the L2 fixture
- [ ] Deterministic output on repeat extraction (no confidence drift)

### Real-PDF fixture

- [ ] At least one L2 scrubbed-private PDF committed to `tests/fixtures/pdf_corpus/l2_scrubbed_private/modelo_036/` with consent-log entry in `_consent_log.jsonl`
- [ ] **OR** an L1 public-anchor PDF hash-pinned from an AEAT-published sample
- [ ] **OR** explicit `.vault/reference/` waiver stating why neither is obtainable

### Synthetic round-trip

- [ ] L3 synthetic generator via `QuarterlyGenParams` (or inline canvas if named-field shape requires it)
- [ ] Round-trip test `generator(fields) → PDF → extractor == fields`

### Per-year completeness

- [ ] Extractor tested against 2024, 2025, 2026 templates
- [ ] Template-drift warnings when fields rename / move / deprecate
- [ ] `.vault/reference/2026-036-rule-delta.md` manifest

### Test discipline

- [ ] `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`
- [ ] No mocks / fakes / stubs / skips

### Closure evidence

- [ ] `.vault/exec/YYYY-MM-DD-modelo-036-registration-extract/…-summary.md`
- [ ] `docs/coverage/modelos.md` row flipped in applicable columns
- [ ] PR body lists every extracted field with its BOE citation

---

**Parent EPIC:** #316
