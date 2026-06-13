---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-ruleset-architecture-adr]]"
---

# real-pdf-import — wave 53 exhaustive audit

## Scope

Second cycle of the exhaustive-audit pattern. Four parallel streams
verify the wave 49-52 remediations actually addressed wave-48
findings without regressions, and deep-scan for gaps exposed by the
remediation.

Commit range audited: `987422b..HEAD` (waves 49-52, plus the Modelo
115 casing fix committed live as `78b4687`).

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 Remediation re-verification | PASS | 0 | 0 | 1* |
| 2 Primitive safety + regression | REVISION REQUIRED | 1 | 1 | 1 |
| 3 Coverage matrix + docs | REVISION REQUIRED | 3 | 1 | 2 |
| 4 Test quality + tautology | REVISION REQUIRED | 3 | 4 | 2 |

*Stream 1 LOW landed live in commit `78b4687` (Modelo 115 casing alignment).

**Total open findings: 7 HIGH, 6 MEDIUM, 5 LOW.**

## Closure status (updated 2026-04-22, wave 61b per wave 60 stream 3 H2)

| Finding | Status | Closing wave |
|---|---|---|
| H1 synthetic NBSP rendering | PARTIAL | wave 56 (`38cbe6c`) added format_amount opt-in; wave 61d completes end-to-end threading |
| H2 coverage matrix 2024 backfills | CLOSED | wave 54 (`086b1dd`) |
| H3 Modelo 130 colocated tests | CLOSED | wave 55 (`f441e2f`) |
| H4 audit closure markers | PARTIAL | wave 54 added wave-48 closure table; wave 61b adds same to wave 53/58 |
| H5 test tautology residual | PARTIAL | wave 57a/b + 59c anchored 11/14 rulesets; 130_2025 + 100_summary remain (wave 61c) |
| H6 provenance citations | PARTIAL | 11 external-anchored tests cite BOE/LIRPF/LIS/LIVA; wave 61c completes |
| H7 zero-boundary tests | CLOSED | wave 59b (`7f678a9`) — all 18 rulesets covered |

## HIGH findings

### H1 (stream 2) — Wave 51 NBSP fix not end-to-end tested

The synthetic PDF generator (`tests/fixtures/pdf_corpus/l3_synthetic/
_generators/_generator_shared.py::format_amount`) only emits `.`
thousands. Grep confirms zero `\xa0` / ` ` token anywhere in the
`_generators/` tree. Wave 51's fix is exercised only by the module-
level primitive test at `src/aeat/adapters/inbound/pdf/test_label_regex.py:57`;
the round-trip corpus never sees it.

**Fix**: opt-in `thousands_sep` parameter to `format_amount`, thread
through `_generic_quarterly_generator.py`, add one NBSP-rendered
round-trip per modelo.

### H2 (stream 3) — Coverage matrix under-reports 2024 backfill rulesets

`docs/coverage/modelos.md:12-17` shows Modelos 111, 115, 123, 131,
180 as `✅ (2025 ...)` even though the 2024 backfill rulesets have
shipped and register via `_rulesets/__init__.py`. Only Modelo 130
(row 15) correctly reads `✅ (2024 + 2025)`. Provenance line 35 is
still stamped "2026-04-21 / wave 17".

**Fix**: update rows 12/13/14/16/17 to `✅ (2024 + 2025 ...)`, refresh
provenance date.

### H3 (stream 3) — Modelo 130 2024 + 2025 lack colocated tests

Wave 52 claimed to close the "7 untested rulesets" gap but only
shipped tests for 5 backfills (111/115/123/131/180) + the summary
ruleset. `modelo_130_2024.py` and `modelo_130_2025.py` still have no
colocated test file; they're exercised only via smoke tests in
`test_engine.py` / `test_ruleset.py` / `test_registry.py`.

**Fix**: add a `test_modelo_130_2024.py` + `test_modelo_130_2025.py`
with happy + mutation + shape tests per the wave-52 pattern.

### H4 (stream 3) — Wave 48 audit doc missing closure markers

`.vault/audit/2026-04-22-real-pdf-import-wave-48-exhaustive-audit.md`:
only H6 carries a "Closed via wave 50" marker. H1/H2/H4/H5/H7 need
explicit closure stamps. H3 should carry a "deferred to wave 57+"
marker.

### H5 (stream 4) — 12/14 ruleset tests are tautological

Wave 52's "inline arithmetic independent of the ruleset" claim is
inaccurate for 12/14 test files. The arithmetic reuses the SAME rate
constants (0.19, 0.21, 0.02, 0.25) that the ruleset formulas use. A
rate-swap bug in the ruleset would require the fixture to be edited
in lockstep; unit tests pass for any internally-consistent pair.
Fully mitigated only in `test_modelo_303_ruleset.py` (true
cross-source verification) and the 303_2024 cross-year parity test.

**Fix**: add one `test_external_worked_example` per priority ruleset
citing a BOE Orden / AEAT Manual Práctico page number with inputs +
expected outputs sourced from that publication.

### H6 (stream 4) — Zero provenance citations in any test

No test file references a BOE URL, Manual Práctico chapter, or AEAT
instrucciones PDF. Future contributors treat fixtures as
authoritative when they're actually just prior-author mental
arithmetic.

### H7 (stream 4) — Zero negative-result / boundary tests for 5 rulesets

Modelos 111, 115, 123, 180, 390 have no zero-value boundary tests,
no negative-compensation path tests, no large-value (>1M) overflow
checks. Rounding-boundary tests exist only in `test_modelo_303_2025
::test_boundary_rounding`.

## MEDIUM findings

- **M1 (stream 2)**: `_normalise_pdf_text` uses blind `.replace("-\n", "")`.
  Any leading bullet-dash `-\nitem` is silently merged. Narrow with
  a lookaround like `(?<=\w)-\n(?=\w)`.
- **M2 (stream 3)**: ADR `.vault/adr/2026-04-22-ruleset-architecture-adr.md`
  §implications lines 134-142 still frame the variant axis as future
  work despite §decision stating wave 47 already landed it.
- **M3 (stream 4)**: `test_modelo_303_2025::test_audit_against_clean`
  is explicit derive-then-feed-back tautology. Rename to
  `test_engine_round_trip_deterministic` or remove.
- **M4 (stream 4)**: Mutation tests are operand-blind. A `sub_op(a, b)`
  vs `sub_op(b, a)` swap in any subtract formula would pass every
  current test when fixtures use zeros for one operand.
- **M5 (stream 4)**: No zero-boundary test on 111/115/123/131/200/
  202/390.
- **M6 (stream 4)**: No large-value (>1M) coverage anywhere.

## LOW findings

- **L1 (stream 1)**: Modelo 115 comment casing — fixed live in `78b4687`.
- **L2 (stream 2)**: `parse_spanish_decimal` tolerates `sign + space +
  digits`. Gated upstream by the regex; defensive parser slack only.
- **L3 (stream 3)**: `kent-capabilities.md` provenance date stale.
- **L4 (stream 3)**: `modelos.md:23` Modelo 303 `Formula ruleset`
  column still reads `⏳ #221` despite 2024+2025 rulesets shipped.
- **L5 (stream 4)**: Inconsistent fixture styling (inline dict vs
  `_provided()` factory). Normalise.

## Remediation plan — waves 54-57

- **Wave 54** (docs): H2 coverage matrix refresh, H4 audit closure
  markers, M2 ADR implications, L3/L4 cosmetic dates + column.
- **Wave 55** (test coverage): H3 Modelo 130 colocated tests.
- **Wave 56** (primitives): H1 synthetic NBSP rendering end-to-end,
  M1 soft-hyphen narrowing.
- **Wave 57+** (tautology): H5 + H6 provenance-backed external
  fixtures for Modelos 303/100/111/131/130, M3 rename, M4 operand-
  swap mutation tests, M5/M6 boundary tests.

Each wave ships with its own audit-loop per the established
exhaustive-audit contract.
