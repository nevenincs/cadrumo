---
tags:
  - "#audit"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-fixture-corpus-plan]]"
  - "[[2026-04-21-declaracion-extractor-plan]]"
  - "[[2026-04-21-calc-verification-plan]]"
  - "[[2026-04-21-real-pdf-import-execution-wave-1-audit]]"
---

# real-pdf-import execution waves 2/3/4 — code review audit

## Scope

Three consecutive execution waves of EPIC #305, reviewed together:

- **Wave 2** (`fbde5d2`) — cluster C scaffolding: `src/aeat/adapters/inbound/pdf/_scrub.py`, synthetic generator primitives, L1 manifest fetcher, pytest marker registration.
- **Wave 3** (`398ef82`) — cluster D phase 1: `src/aeat/adapters/inbound/declaracion/` module family + Modelo 130 v2025 extractor + synthetic L3 generator + `aeat filing import --from-declaracion` CLI.
- **Wave 4** (`1723119`) — cluster E: `src/aeat/application/verification/` module + discrepancy classifier + verification chaining from the import CLI.

The reviewer persona (`vaultspec-code-reviewer`) returned a structured inline report; findings distilled below with resolutions recorded per project policy.

## Findings + resolutions

### H1 — Extractor silently trusts every regex hit (HIGH, **fixed**)

`Modelo130V2025Extractor` hard-coded `extraction_confidence=1.0` for every hit and emitted no `ambiguous-label` warnings. Real AEAT PDFs with slightly different spacing could silently mis-extract non-derived casillas (01 / 02 / 05 / 06) and route the wrong value through verification as "VERIFIED". Additionally `casilla-not-found` was absent from the verification classifier's `_UNRELIABLE_WARNING_CODES` set, so missing casillas did not downgrade the verdict.

**Resolution**:

- The extractor now runs `pattern.findall(text)` per casilla; hits > 1 drop confidence to `0.5` + emit `ambiguous-label`.
- New `_structural_integrity_check_01_minus_02` helper asserts the Modelo 130 identity `03 = 01 - 02` within 0.02 €; violations downgrade casilla 03's confidence to `0.3` + emit `ambiguous-label` so the verification classifier flags EXTRACTION_UNRELIABLE.
- `_UNRELIABLE_WARNING_CODES` in `src/aeat/application/verification/_verify.py` gains `"casilla-not-found"` so partial extractions downgrade to `NEEDS_REVIEW`.

### H2 — Template-revision detector fabricates an unsupported revision (HIGH, **fixed**)

`detect_template_revision` always returned `revision=f"{ejercicio}.01"` — a 303 post-HAC/819/2024 PDF would silently label as `2024.01`, fail at the registry with a misleading "no extractor" error, and read to Kent as "we don't support 303 at all."

**Resolution**:

- Detector now looks for an `Orden HAC/N/YYYY` stamp in the header/footer and returns `revision=f"{año}.orden-{number}"` when present.
- When no stamp is found, falls back to the `"{ejercicio}.01"` sentinel. Registry refusal → clean `NoExtractorRegisteredError` rather than silent mis-extraction.
- The registry's error message already enumerates supported revisions, so the fallback path's failure mode remains Kent-readable.

### M1 — Scrub name regex eats AEAT section headings (MEDIUM, **fixed**)

`_NAME_RE` matched any 2–4-word uppercase span — including `RESULTADO A INGRESAR`, `AGENCIA TRIBUTARIA`, `DECLARACIÓN MODELO`. Passing a real declaración through the scrubber would rewrite every section heading to `DEMO AUTÓNOMO`, destroying the extractor's label anchors.

**Resolution**:

- `_NAME_RE` now requires a `Apellidos y nombre | Apellidos | Nombre | Declarante | Titular | Razon social | Razón social | Empresa` prefix before matching the name tokens.
- Replacement preserves the prefix and only rewrites the trailing name span: `Apellidos y nombre: PERSONA PRUEBA` -> `Apellidos y nombre: DEMO AUTONOMO`.
- New tests (`TestNamePrefixGuard`) assert `RESULTADO A INGRESAR` and `AGENCIA TRIBUTARIA` survive the scrub and that prefixed names are properly rewritten.

### M2 — Scrub missing canonical Spanish PII patterns (MEDIUM, **fixed**)

NIE, phone, email, postal-code regex gaps meant the library would scrub NIF+amount+CSV+IBAN but leave NIE / teléfono / correo / CP untouched.

**Resolution**:

- Added `_NIE_RE`, `_PHONE_RE` (9-digit Spanish leading 6/7/8/9 + optional +34), `_EMAIL_RE`, `_CP_RE` (prefixed "CP " or "C.P. " to avoid false positives on arbitrary 5-digit numbers).
- Corresponding sentinel constants (`_SCRUB_NIE`, `_SCRUB_PHONE`, `_SCRUB_EMAIL`, `_SCRUB_CP`).
- Scrub pipeline order reshuffled so IBAN passes before phone (IBAN leading digits don't get misread as a phone prefix).
- New `TestNieRedaction`, `TestPhoneRedaction`, `TestEmailRedaction`, `TestPostalCodeRedaction` classes cover each field.

### M3 — Presentation-ID regex ordering edge case (MEDIUM, **accepted with caveat**)

Tracked for phase-2 follow-up; the regex still runs over the full text blob and could re-randomise already-scrubbed CSV tokens on a second pass. Mitigation: scrub is idempotent by design (deterministic RNG seeded from filename), and guard tests catch any residual leakage. Documenting without a code change this wave.

### M4 — Missing exec summary for waves 2/3/4 (MEDIUM, **fixed**)

This file itself + the phase summary accompanying this commit address the gap; future waves get their own summary per vaultspec pipeline discipline.

### M5 — Trilingual contract violation in CLI output (MEDIUM, **fixed**)

`_handle_declaracion_import` hardcoded `Language.EN` for every `get_translation` call, violating the `AEAT_OUTPUT_LANGUAGE=es` default.

**Resolution**:

- New `_output_language()` helper reads `load_settings().aeat_output_language` and maps to `Language` (falling back to `ES` on parse error).
- Both `_handle_declaracion_import` and `_handle_justificante_import` now route through `_output_language()`.
- Smoke-verified: `AEAT_OUTPUT_LANGUAGE=es aeat filing import --from-declaracion ...` now prints the Spanish narrative: *"Modelo 130 2025Q1: verificado. Cobertura 37%. 0 discrepancias no bloqueantes (redondeo / reglas no modeladas)."*

### L1 / L2 / L3 / L4 — minor / style (LOW, **deferred**)

Branch-order drift vs. ADR, broad exception catches in the ruleset resolver, `coverage=0.0` on unverifiable, and the `noqa: S311` annotation are all minor. Captured in this audit for traceability; no code changes this wave.

### I1 / I2 / I3 — Kent UX + coverage + good-things (INFORMATIONAL)

Kent narration reads coherent in all three paths (happy / partial / unverifiable). Coverage matrices accurate vs. plan. Strict+frozen models, relative imports, no mocks, deterministic RNG, SHA-256 pinning, round-trip JSON — all clean.

## Test + lint results post-fix

- `uv run pytest -m unit src/aeat/adapters/inbound/pdf/ src/aeat/adapters/inbound/declaracion/ src/aeat/application/verification/ src/aeat/entrypoints/cli/filing/` → 54 passed (47 prior + 7 new scrub tests).
- `uv run ruff check` + `uv run ty check` on every touched module — clean.
- Kent UX smoke: `AEAT_OUTPUT_LANGUAGE=es` now produces Spanish verdict; default language path covered.

## Decision

Waves 2/3/4 **ready to merge** once the H1/H2/M1/M2/M4/M5 fixes commit (applied in the same working tree as this audit). Next wave: cluster H (integration tests + CI surface) + cluster F MVP (Renta summary block) + cluster B phase 2 (schema casilla completion).
