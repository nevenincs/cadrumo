---
tags:
  - '#research'
  - '#operator-workflows-expansion'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-operator-workflows-expansion-adr]]"
  - "[[2026-04-25-operator-workflows-expansion-plan]]"
---

# `operator-workflows-expansion` research: cli-integration-coverage

Research backing the implementation of issue wgergely/aeat#340, child of
EPIC #316. Goal: extend `tests/integration/test_kent_workflows.py` so that
every Tier-L modelo with a landed extractor and ruleset is exercised end-
to-end through the `aeat filing import` CLI surface.

## Findings

### Existing template — Modelo 130

`tests/integration/test_kent_workflows.py` ships one CLI-integration class
today, `TestKentImportsModelo130Declaracion`, with three cases:
`test_happy_path_english`, `test_happy_path_spanish_default`,
`test_partial_extraction_needs_review`. Every case uses
`typer.testing.CliRunner` and the dedicated `Modelo130GenParams` /
`generate` factory in
`tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py`.

The module marker is:

```
pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_financial_input,
    pytest.mark.fixture_tier_l3,
]
```

NOTE — handover-prompt drift: the handover prompt asserts the module
marker is `[unit, domain_submission]`. The file on disk is
`[unit, domain_financial_input, fixture_tier_l3]`. **Codebase reality
governs**; preserving the existing markers prevents a CI marker mismatch.

### Synthetic generators on disk

```
tests/fixtures/pdf_corpus/l3_synthetic/_generators/
  modelo_100_generator.py        — Modelo 100 (Renta) summary block
  modelo_130_generator.py        — Modelo 130 (template)
  modelo_303_generator.py        — Modelo 303 IVA (33 casillas)
  _generic_quarterly_generator.py — universal quarterly + annual generator
                                    consumed by every other landed extractor
```

The generic generator `QuarterlyGenParams(modelo, año, template_revision,
tax_id, ejercicio, period_printed, labels, casilla_values, csv,
presented_at, thousands_sep)` accepts an arbitrary modelo + label map +
casilla-value map. It is exactly the surface used by
`src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py` to exercise Modelos
111 / 115 / 123 / 131 / 180 / 190 / 193 / 200 / 202 / 347 / 349 / 369 /
390 / 720 / 840 at the parser level. The label maps for every modelo in
scope of #340 are already authored in that ruleset-test module; reusing
them keeps the integration tests aligned with parser-test ground truth.

NO new synthetic generator is required for this issue. The audit gap
this issue closes is at the CLI integration layer, not the synthetic-PDF
layer.

### CLI handler shapes

`aeat filing import --from-declaracion <pdf>` → `_handle_declaracion_import`
in `src/aeat/entrypoints/cli/filing/__init__.py`:

1. `parse_declaracion(path, modelo_override, año_override)` →
   `DeclaracionFiling`.
2. `typer.echo("Parsed Modelo {M} {period} declaración (template ...). N of M
    casillas extracted.")`.
3. `typer.echo("Extraction status: {status}")` — stable marker.
4. Per warning: `"  - casilla {id}: {translated message}"`.
5. `_resolve_ruleset_for_filing(...)` → `Ruleset | None`.
6. `verify_declaracion(filing, ruleset=ruleset)` → `VerificationVerdict`.
7. `typer.echo("Verification status: {status.value}")` — stable marker.
8. `typer.echo("  {translated narrative}")`.
9. Per discrepancy: `"  - casilla {id}: expected {e}, actual {a},
    cause={cause.value} — {translated rationale}"`.

Stable markers usable for assertions:
- `"Extraction status: COMPLETE"` / `"PARTIAL"` / `"FAILED"` /
  `"UNVERIFIABLE"`.
- `"Verification status: VERIFIED"` / `"NEEDS_REVIEW"` / `"UNVERIFIABLE"`.
- `"cause=CORRECTNESS_DIVERGENCE"` / `"EXTRACTION_UNRELIABLE"` /
  `"UNMODELLED_RULE"` / `"ROUNDING"`.
- Warning lines: `"casilla {id}"` substring for missing-casilla
  diagnostics.

i18n narrative substrings that confirm the language path:
- `"verified"` (en), `"verificado"` (es) — VERIFIED narrative.
- `"needs review"` (en), `"revisar"` (es) — NEEDS_REVIEW narrative.

### Modelo 100-summary special case — `--from-borrador`

Modelo 100 (Renta) artefacts are NOT routed through `--from-declaracion`.
The dedicated CLI flag is `--from-borrador`, dispatched to
`_handle_borrador_import`, which calls `parse_borrador` (NOT
`parse_declaracion`) and audits against `MODELO_100_SUMMARY_2025` directly
via `Engine.audit_against` (NOT `verify_declaracion`).

CLI output shape for Modelo 100 differs:
- `"Parsed Modelo 100 Renta {ejercicio} ({artefact_kind})."` — no
  "Extraction status:" prefix.
- `"Verification status: VERIFIED (ruleset=modelo_100.summary.2025)"` or
  `"Verification status: NEEDS_REVIEW — N discrepancies"` — same
  marker root, suffixes differ.
- `"Tarifa progresiva: cuota íntegra estatal consistent with IRPF
   {ejercicio} scale"` — additional invariant the borrador path emits.

Implication: the Modelo 100 test class assertions match on
`"Verification status: VERIFIED"` (substring) and `"Parsed Modelo 100
Renta"`. NO `"Extraction status:"` assertion. The class is named
`TestKentImportsModelo100SummaryBorrador` to honour Kent-observable CLI
surface naming; this is a deliberate departure from the handover
prompt's literal class name (`...Declaracion`) and is documented in
the ADR.

### Year coverage — extractor × ruleset matrix

| Modelo | Extractor years registered     | Ruleset years registered     | Verifiable in CLI today |
| ------ | ------------------------------ | ---------------------------- | ----------------------- |
| 100    | 2021/2022/2023 (renta variants)| `summary.2025` only          | YES (via `--from-borrador`) |
| 111    | 2025                           | 2024 + 2025                  | YES at 2025             |
| 115    | 2025                           | 2024 + 2025                  | YES at 2025             |
| 123    | 2025                           | 2024 + 2025                  | YES at 2025             |
| 131    | 2025                           | 2024 + 2025                  | YES at 2025             |
| 180    | 2025                           | 2024 + 2025                  | YES at 2025             |
| 200    | 2025                           | **2024 only**                | **NO**: produces UNVERIFIABLE for any 2025-rendered PDF; no 2024 extractor exists for Modelo 200 |
| 202    | 2025                           | 2025 only                    | YES at 2025             |
| 303    | 2024 (Orden 819) + 2025        | 2024 + 2025                  | YES at 2025             |
| 390    | 2025                           | 2025 only                    | YES at 2025             |

NOTE — Modelo 200 limitation: the codebase ships a 2025-template
extractor but only a 2024-period ruleset. A 2025-rendered Modelo 200 PDF
extracts cleanly but cannot be ruleset-verified — `verify_declaracion`
returns a verdict with `status=UNVERIFIABLE` and the narrative "no
ruleset registered; verification unavailable". This is a real Kent-
observable behaviour today and the integration test for Modelo 200
locks it in — closing the audit's regression gap with the verdict
that production actually emits.

### PARTIAL threshold

`src/aeat/adapters/inbound/declaracion/_generic_extractor.py:_derive_status` returns:
- `COMPLETE` when every required casilla is reliably resolved.
- `PARTIAL` when `coverage >= 0.5`.
- `FAILED` otherwise.

For each modelo, a partial PDF with 50–95% of required casillas present
will yield `PARTIAL` and emit `casilla-not-found` warnings for the
missing ids — exercising the same Kent-readable warning chain as the
130 template.

### Discrepancy classifier (4th case)

A material delta on a computed casilla (`abs(delta) >= 10 * tolerance` =
≥ 0.10 €) is classified as `CORRECTNESS_DIVERGENCE`. To reliably trigger
this in the 4th case, the PDF prints a value for a computed casilla
that disagrees by ≥ 1 € with the engine-derived value. Since the
verdict downgrades to `NEEDS_REVIEW` whenever any
`CORRECTNESS_DIVERGENCE` is present, the 4th case asserts:
- `"Verification status: NEEDS_REVIEW"`.
- `"cause=CORRECTNESS_DIVERGENCE"`.
- The affected casilla id appears on a discrepancy line.

The 4th case is included for every modelo whose ruleset has at least one
`computed=True` casilla and a non-trivial input set. From the formula
catalogue:
- 111 — 4 computed (09, 12, 28, 30) — INCLUDED
- 115 — 2 computed (03, 06) — INCLUDED
- 123 — 4 computed (03, 06, 09, 11) — INCLUDED
- 131 — 6 computed (04, 06, 07, 10, 13, 15) — INCLUDED
- 180 — 1 computed (03) — INCLUDED
- 200 — 3 computed but no ruleset for 2025 → SKIPPED with documented
  reason; 4th case unavailable
- 202 — 3 computed (18, 32, 34) — INCLUDED
- 303 — 12 computed — INCLUDED
- 390 — 3 computed (104, 105, 190) — INCLUDED
- 100-summary — 4 computed (0595, 0630, 0698, 0720) — INCLUDED

### Forward-compat with #398 / #399

#398 wraps Typer callbacks with an error-emission decorator that may
prefix stderr lines with stable codes (e.g. `ERROR:` / `REFUSED:`). #399
adds `--json` plus a stable JSON envelope. Neither has merged to main
yet, but to forward-compat:
- All assertions are substring matches on stable state markers
  (`"VERIFIED"`, `"PARTIAL"`, `"NEEDS_REVIEW"`, `"COMPLETE"`,
  `"CORRECTNESS_DIVERGENCE"`, casilla ids).
- No assertions on full multi-line output equality.
- No assertions on ordering of warnings or discrepancies.
- No `--json` invocations and no `--help` assertions about `--json`.

### Chosen years per modelo

| Modelo | Year tested | Rationale                                              |
| ------ | ----------- | ------------------------------------------------------ |
| 100-S  | 2025        | Only landed; Renta summary block                       |
| 111    | 2025        | Most recent landed; matches existing Q1 fixtures       |
| 115    | 2025        | Most recent landed                                     |
| 123    | 2025        | Most recent landed                                     |
| 131    | 2025        | Most recent landed                                     |
| 180    | 2025        | Most recent landed                                     |
| 200    | 2025        | Only year with a registered extractor; locks in known UNVERIFIABLE behaviour |
| 202    | 2025        | Only landed                                            |
| 303    | 2025        | Most recent landed                                     |
| 390    | 2025        | Only landed                                            |
