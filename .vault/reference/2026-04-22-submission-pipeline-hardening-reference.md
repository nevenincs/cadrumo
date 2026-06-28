---
name: submission-pipeline-hardening
description: Reference catalogue for the wave 89-148 autonomous hardening cycle on the fichero-BOE submission pipeline — perpetual regression guards, E2E coverage, CLI surface, input validation, structural layout locks, and schema-module contracts.
type: reference
tags:
  - "#reference"
  - "#submission-pipeline-hardening"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-22-aeat-fichero-boe-export-adr]]"
---

# submission-pipeline-hardening

Capstone reference for the autonomous-loop cycle spanning **waves 89–148** on `src/aeat/adapters/outbound/aeat/export/_formats/` and `src/aeat/entrypoints/cli/submission/`. First written at wave 130; extended at wave 140 (50-wave milestone) and wave 149 (this revision) to cover the waves 141–148 structural-layout locks.

## scope

Kent's produce → verify → export journey shipped from zero to:

- **Modelo 130** ejercicio 2024 + 2025 (single-record 878-byte, cp1252)
- **Modelo 303** ejercicio 2024 + 2025 (8-segment 7994-byte envelope, iso-8859-1)

Across every `(modelo, ejercicio, tipo)` combination plus devolución (SEPA IBAN), produce/verify/diff work end-to-end with byte-exact golden SHAs pinned per ejercicio.

## new CLI surface (cycle deliverables)

| Command | Wave | Purpose |
|---|---|---|
| `aeat submission export <draft>` | 81 (pre-cycle) + 92/94/101 | Byte-exact fichero-BOE writer, envelope + record dispatch, devolución IBAN |
| `aeat submission verify <file>` | 95 | Re-parse + pretty-print (+ `--json`) |
| `aeat submission diff <a> <b>` | 98 | Byte + semantic comparison (+ `--json`) |
| `aeat submission schemas` | 104 | Registry discovery (+ `--json`) |
| `aeat submission check-nif <id>` | 107 | Spanish NIF/NIE/CIF check-letter validator (+ `--json`) |

All five share the factored `_schema_registry.py` dispatch (wave 97) with filename auto-detection on `verify`/`diff`.

## perpetual regression surfaces

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
- C4 Exit-code contract (0=ok, 1=diff, 2=unsupported/corrupt, 3=draft-refused) — wave 131.
- C5 `--help` shape per subcommand (verb + key flags discoverable) — wave 132.
- C6 Live-submit deferral surfaced at `aeat --help` + engine default `live_transport_supported=False` — wave 133.
- C7 Safety 4-factor-gate documentation lock (ADR + ROADMAP) — wave 134.

**Input validation:**
- V1 NIF check-letter (AEAT algorithm) at export boundary — wave 106.
- V2 Standalone `check-nif` command — wave 107.
- V3 Payload-length pre-flight on verify/diff (Kent-facing message naming expected vs actual bytes) — wave 135.
- V4 `--modelo` / `--ejercicio` flag-shape validators (3-digit / 4-digit enforcement) — wave 136.
- V5 IBAN / SWIFT flag-shape validators with normalisation — wave 137.
- V6 IBAN normalisation E2E byte-identity (six paste-format variants → identical bytes) — wave 138.
- V7 `--nombre` / `--apellidos` preserve-case contract (intentional; typos must surface) — wave 139.

**Cross-track E2E:**
- E1 Ruleset → serialise → golden-SHA for 130 2024 — wave 108.
- E2 Ruleset → serialise → golden-SHA for 303 2024 — wave 109.
- E3 2024 vs 2025 clone-parity via same-input invariant (both modelos) — wave 110.
- E4 Registry-parametrised produce/verify/diff smoke — waves 124/125.

**Encoder edge cases:**
- ED1 ALPHANUMERIC non-ASCII round-trip per encoding (cp1252 vs iso-8859-1) — wave 127.
- ED2 CURRENCY unsigned + INLINE_SIGN, zero / 1-cent / typical / max / overflow / ROUND_HALF_UP — wave 128.
- ED3 DATE YYYYMMDD + DDMMYYYY calendar-boundary + garbage-rejection — wave 129.

**Structural-layout locks (byte-shape lattice):**
- SL1 CLI export determinism: 2 runs + 5 runs produce byte-identical files per schema — wave 141.
- SL2 303 envelope inter-segment cumulative layout (8 segments × start × length) — wave 142.
- SL3 DP30301 intra-segment header block (10 fields, TIPO/NIF/APELLIDOS_Y_NOMBRE/EJERCICIO/PERIODO) — wave 143.
- SL4 DP303DID SEPA page layout (SWIFT/IBAN/BANK/COUNTRY/MARCA_SEPA) — wave 144.
- SL5 Modelo 130 record header block (11 fields per dr130.09.pdf) with wave-77c miscite guards — wave 145.
- SL6 DP30301 régimen-general rate rows (4% / 5% / 10% / 21% triples) — wave 146.
- SL7 DP30301 recargo-equivalencia rate rows (1.75% / 1.40% / 5.20%) + casilla-17 observed-state — wave 147.

Total: **32 perpetual-guard surfaces**.

## numeric summary

- **59 waves landed** across `src/aeat/adapters/outbound/aeat/export/` and `src/aeat/entrypoints/cli/submission/` since cycle start (wave 89)
- **543 tests passing** (4 intentional kind-filtered skips)
- **29 test files authored** with perpetual-guard invariants
- **4 schema modules** pinned per ejercicio
- **32 regression surfaces** in the invariant lattice

## input-handling philosophy

The CLI splits inputs into two categories with opposite normalisation contracts:

- **Canonical inputs** (IBAN, NIF, modelo, ejercicio) — normalised at the typer-callback boundary. Kent's paste-format variations (spaces, hyphens, case) produce byte-identical exports. Wave 106/136/137/138 implementations.
- **Identity inputs** (NOMBRE, APELLIDOS) — preserve-case byte-identically. A silent `.upper()` would hide typos Kent wants to catch at verify time; AEAT convention is upper-case but we nudge via `--help` rather than enforce. Wave 139 implementation.

## kent-visible outcomes

1. `aeat submission schemas --json` lists what can be exported.
2. `aeat submission check-nif <id>` validates an identifier before a filing attempt.
3. `aeat submission export <draft>` writes a byte-exact fichero-BOE file with a canonical filename.
4. `aeat submission verify <file>` decodes the file back and pretty-prints the casillas.
5. `aeat submission diff <a> <b>` compares two files at byte and semantic level.

Every path above has both a rich-formatted and `--json` output variant for downstream pipeline integration. Exit codes follow the wave-131 contract (0/1/2/3) so shell pipelines can script around them.

## known gaps deferred to follow-up waves

- **Modelo 390 bootstrap** — requires DR390e24.xlsx extraction, external-tooling blocked.
- **Modelo 303 casilla 45 / 64 / 67 / 71 schema fields** — ruleset declares, schema doesn't (wave 113/114 documented; `_2`-suffixed CURRENCY slots in DP30303/DP30304 are the likely carriers pending DR303 PDF cross-reference).
- **Live AEAT submission** — explicitly disabled. Deferred to 1.0.0 per the 2026-04-18 live-submit excision ADR. Wave 133/134 documentation locks + the wave-80c `test_no_submit_command` guards keep the excision in place.
- **Rectificativa rulesets** — wave-120's cross-year guard will relax when #234 lands.

## byte-shape lattice for Modelo 303

Any fixture shift affecting Kent's bytes now fails at the most localized layer with a targeted message:

| Layer | Wave | What fails first |
|---|---|---|
| Total envelope length = 7994 | 89 | sum of `segment.total_length` |
| `_SEGMENT_*` ↔ ENVELOPE parity | 116 | generator-convention mismatch |
| Inter-segment cumulative offsets | 142 | segment reorder / insert |
| DP30301 intra-segment header | 143 | Kent-ID field shift |
| DP303DID SEPA fields | 144 | IBAN / SWIFT shift |
| DP30301 rate rows (régimen general) | 146 | rate-row insert / reorder |
| DP30301 recargo-equivalencia | 147 | recargo-row shift |
| Golden SHA | 93 / 99 | any byte change |
| CLI determinism (2+5 runs) | 141 | non-pure dependency leak |

The analogous structure for Modelo 130 is locked by wave 145 (11-field header + wave-77c miscite guards).

## handoff notes

A future contributor should:

1. Run `uv run pytest src/aeat/adapters/outbound/aeat/export/ src/aeat/entrypoints/cli/submission/` — 543 tests is the baseline.
2. Read `.claude/rules/aeat-project-mandates.md` and `.vault/adr/2026-04-17-export-first-adr.md`.
3. For a new modelo, follow the 303 pattern: JSON fixture in `tests/fixtures/dr_specs/`, run the generator, register in `_schema_registry.py`, add golden SHA, add the ruleset metadata lock entry. The wave-124 registry-parametrised smoke test picks up the new entry automatically.
4. When closing the 303 casilla gap, update `_EXPECTED_GAPS`, the fixture's `source.notes`, and regenerate — the wave-121/122 consistency tests will guide the edits.
5. When adding a new CLI flag, lock its shape + help-text presence in `test_help_text_contract.py` (wave 132) and, if it takes user-pasted canonical data, add a typer callback with normalisation + a flag-validation test mirroring wave 136/137.
