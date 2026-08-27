---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:3ba2833e17362b704d4c8be2fb76c32abea9fdafd7b99acd7783c5404cbb08eb'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `modelo 210 annual grouped renta export fidelity determination`

## Scope

S295: establish whether modelo 210 annual grouped-renta rows (`Modelo210AgrupacionRentaRow`,
`_m210_agrupacion_renta.py`) are correctly represented in what is exported, given the module
states the rows are accepted for legal evidence and validation only and are never summed into
an input or computed casilla. Determination Step, no code changed. Covers
`src/cadrumo/application/modelo/_m210_agrupacion_renta.py`, the modelo 210 annual (`0A`) export
record, and the existing multi-row worked-example e2e test.

## Findings

**Determination: no defect. The scalar casillas the export record carries represent the
declared value faithfully; the annual aggregate is not under-computed, because it was never
meant to be derived from the grouped-renta rows.** This is a deliberate, ADR-ruled and
test-guarded design, not an oversight.

### The rows are a legal-evidence gate, never an arithmetic input

`_m210_agrupacion_renta.py`'s own module docstring states the design directly: "The registry
formula continues to calculate M210 from its declared casillas... it accepts the persisted
typed rows, never sums them into an input or computed casilla." Its only two functions,
`validate_m210_agrupacion_renta_rows_for_calculation` and
`m210_agrupacion_renta_verification_findings`, check Article-2 grouping compatibility (same
tipo/rate/payer) and code-match against `m210_official_tipo_renta_code`; neither reads or
totals `importe`. A repository-wide grep for any code summing `detail_rows`, `agrupacion_renta`
importes, or cross-checking them against a casilla returns zero hits outside these two
validation-only call sites.

### The design is an explicit ADR ruling, not an accident

`2026-07-10-m210-irnr-phase-2-engine-adr.md` (status `accepted`) rules that implementation
"must not broaden grouped rows into an alternate sum path, bind the computed base casilla...",
reasoning: "Filtering a manually entered computed base after calculation, or merging manual
and ledger values, would create a parallel write path and lose provenance." This matches the
codebase's own "no parallel write paths" / "one canonical mechanism per calculation type"
architecture rules: the manual casilla is the sole writer of `base_imponible` for the paths
the branching formula engine does not compute, and the rows are a separate provenance channel.

### The registry declares the target casilla manual, by design, for exactly this path

`base_imponible_directa_i` (casilla `[4]`, feeding `base_imponible` for the arrendamiento/type-01
path used in the worked example) is `input_kind = "manual"` in the bundled 2025 revision TOML,
with an authoring comment stating it is "declared as operator-input boxes for the paths the
branching engine does not compute." There is no computed-casilla counterpart this Step's rows
could feed into for this income type.

### An existing, already-committed e2e test proves the property directly

`test_annual_grouped_rentas_persist_without_becoming_a_second_arithmetic_path`
(`src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py:83`) builds two
`Modelo210AgrupacionRentaRow` rows totalling EUR 300.00, declares `rendimientos_integros` =
EUR 900.00 through `casilla_inputs`, calculates a real `0A` revision, and asserts
`revision.casilla_values["base_imponible"] == Decimal("900.00")` — the manual declared value,
not the rows' sum. Its own docstring states: "A result that followed the rows rather than the
registry formula's manual casilla input would therefore fail this integration proof." A
sibling assertion in the same test (`m210_official_tipo_renta_code="35"` against rows coded
`"01"`) proves the code-mismatch guard raises `ModeloError`. This is a real, non-tautological,
already-shipped regression test guarding exactly the property this Step was asked to
determine, run against the production `calculate_modelo_revision` entry point with a real
secure-storage backend, not a mock.

### The export record carries the manual value through the ordinary scalar path, faithfully

`src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/export/0001-record-m210-autoliquidacion.toml:1290`
declares `base_imponible` as an ordinary scalar `kind = 'casilla'` export field (offset 1442,
`decimal`, `padding = 'left_zero'`) — the same mechanism every other scalar casilla in the
autoliquidación uses, with no `repeat` marker and no row-indexed counterpart anywhere in the
export layout. Because `revision.casilla_values["base_imponible"]` already carries the manual
declared value (proven by the e2e test above), and the export field reads that same scalar
casilla through the standard export path, the exported figure is exactly what the operator
declared. There is no separate export-layer gap: the fidelity question collapses to the
calculation-layer question already answered.

### Why "faithful, not under-computed" rather than "incomplete"

The Step's own phrasing anticipates the rows might need to feed the aggregate; the evidence
says the opposite is correct by design. M210's annual regime is a manual autoliquidación for
the income types the branching engine does not compute (confirmed at the `base_imponible_directa_i`
casilla level); summing the grouped-renta rows into that casilla would create exactly the
parallel write path the ADR forbids, and would silently override an operator's own declared
figure with a value derived from a DIFFERENT evidentiary source (the grouping rows exist to
prove Article-2 compatibility for combining several rentas onto one declaration, not to state
the taxable base itself).

## Recommendations

None. No defect found; no code change proposed. The rows-are-evidence-only design is
correctly implemented, ADR-grounded, registry-grounded, and already covered by a real,
non-tautological worked-example regression test. Close S295 as a documented "no defect"
determination.
