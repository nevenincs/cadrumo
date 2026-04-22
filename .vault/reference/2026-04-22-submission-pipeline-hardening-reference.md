---
name: submission-pipeline-hardening
description: Reference catalogue for the wave 89-129 autonomous hardening cycle on the fichero-BOE submission pipeline — perpetual regression guards, E2E coverage, CLI surface, and schema-module contracts.
type: reference
tags:
  - "#reference"
  - "#submission-pipeline-hardening"
date: 2026-04-22
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-22-aeat-fichero-boe-export-adr]]"
---

# submission-pipeline-hardening

Capstone reference for the autonomous-loop cycle spanning **waves 89–129** on `src/aeat/submission/_formats/` and `src/aeat/cli/submission/`. Written at wave 130 as the full-repo milestone.

## scope

Kent's produce → verify → export journey shipped from zero to:

- **Modelo 130** ejercicio 2024 + 2025 (single-record 878-byte, cp1252)
- **Modelo 303** ejercicio 2024 + 2025 (8-segment 7994-byte envelope, iso-8859-1)

Across every `(modelo, ejercicio, tipo)` combination plus devolución (SEPA IBAN), produce/verify/diff work end-to-end with byte-exact golden SHAs pinned per ejercicio.

## new CLI surface (cycle deliverables)

| Command | Wave | Purpose |
|---|---|---|
| `aeat submission export <draft>` | 81 (pre-cycle) + 92/94/101 | Byte-exact fichero-BOE writer, env elope + record dispatch, devolución IBAN |
| `aeat submission verify <file>` | 95 | Re-parse + pretty-print (+ `--json`) |
| `aeat submission diff <a> <b>` | 98 | Byte + semantic comparison (+ `--json`) |
| `aeat submission schemas` | 104 | Registry discovery (+ `--json`) |
| `aeat submission check-nif <id>` | 107 | Spanish NIF/NIE/CIF check-letter validator (+ `--json`) |

All five share the factored `_schema_registry.py` dispatch (wave 97) with filename auto-detection on `verify`/`diff`.

## perpetual regression surfaces (the 15-invariant lattice)

**Stream A — citation accuracy:**
- A1 Schema-module docstring provenance (Orden + BOE-ID + DR xlsx) across all 4 shipped modules — waves 117/118.
- A2 Ruleset metadata alignment (ruleset_id / modelo / effective_from / effective_to) per schema — wave 120.

**Stream B — rule adherence:**
- B1 RESERVED literal/length match declared length — wave 112.
- B2 Ruleset↔schema casilla coverage with `_EXPECTED_GAPS` — wave 113.
- B3 Module public surface canonical set — wave 115.
- B4 `_SEGMENT_*` ↔ ENVELOPE identity parity — wave 116.
- B5 `REQUIRED_HEADER_FIELDS` resolvable + non-RESERVED — wave 119.
- B6 Golden SHA256 per modelo/ejercicio + clone-parity — waves 93/99/105.
- B7 Import-time `validate_segment_specs` / `validate_record_specs`.
- B8 303 gap-story 4-surface cross-artifact lock — waves 121/122.

**CLI contracts:**
- C1 SCHEMA_REGISTRY entry shape (kind × module × build_headers coverage) — wave 123.
- C2 Parametrised smoke: every `(modelo, ejercicio, tipo)` round-trips export → verify → diff-self — waves 124/125.
- C3 `--json` output shape pinned for every emitter (verify, diff, schemas, check-nif) — wave 126.

**Cross-track E2E:**
- E1 Ruleset → serialise → golden-SHA for 130 2024 — wave 108.
- E2 Ruleset → serialise → golden-SHA for 303 2024 — wave 109.
- E3 2024 vs 2025 clone-parity via same-input invariant (both modelos) — wave 110.
- E4 Registry-parametrised produce/verify/diff smoke — waves 124/125.

**Encoder edge cases (wave-127–129 matrix):**
- ALPHANUMERIC non-ASCII round-trip per encoding (cp1252 vs iso-8859-1) — wave 127.
- CURRENCY unsigned + INLINE_SIGN, zero / 1-cent / typical / max / overflow / ROUND_HALF_UP — wave 128.
- DATE YYYYMMDD + DDMMYYYY calendar-boundary + garbage-rejection — wave 129.

## numeric summary

- **41 waves landed** across `src/aeat/submission/` and `src/aeat/cli/submission/`
- **402 tests passing** (4 intentional kind-filtered skips)
- **13 test files authored** with perpetual-guard invariants
- **4 schema modules** pinned per ejercicio
- **15 regression surfaces** in the lattice above

## kent-visible outcomes

1. `aeat submission schemas --json` lists what can be exported.
2. `aeat submission export <draft>` writes a byte-exact fichero-BOE file with a canonical filename.
3. `aeat submission verify <file>` decodes the file back and pretty-prints the casillas.
4. `aeat submission diff <a> <b>` compares two files at byte and semantic level.
5. `aeat submission check-nif <id>` validates an identifier before a filing attempt.

Every path above has both a rich-formatted and `--json` output variant for downstream pipeline integration.

## known gaps deferred to follow-up waves

- **Modelo 390 bootstrap** — requires DR390e24.xlsx extraction, external-tooling blocked.
- **Modelo 303 casilla 45 / 64 / 67 / 71 schema fields** — ruleset declares, schema doesn't (wave 113/114 documented; `_2`-suffixed CURRENCY slots in DP30303/DP30304 are the likely carriers pending DR303 PDF cross-reference).
- **Live AEAT submission** — deliberately deferred to 1.0.0 per the 2026-04-18 live-submit excision ADR.
- **Rectificativa rulesets** — wave-120's cross-year guard will relax when #234 lands.

## handoff notes

A future contributor should:

1. Run `uv run pytest src/aeat/submission/ src/aeat/cli/submission/` — 402 tests is the baseline.
2. Read `.claude/rules/aeat-project-mandates.md` and `.vault/adr/2026-04-17-export-first-adr.md`.
3. For a new modelo, follow the 303 pattern: JSON fixture in `tests/fixtures/dr_specs/`, run the generator, register in `_schema_registry.py`, add golden SHA, add the ruleset metadata lock entry.
4. When closing the 303 casilla gap, update `_EXPECTED_GAPS`, the fixture's `source.notes`, and regenerate — the wave-121/122 consistency tests will guide the edits.
