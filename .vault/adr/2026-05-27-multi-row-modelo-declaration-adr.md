---
tags:
  - '#adr'
  - '#multi-row-modelo-declaration'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
  - '[[2026-06-04-multi-row-modelo-declaration-research]]'
---


# `multi-row-modelo-declaration` adr: Multi-row modelo declaration mechanism | (**status:** `accepted`)

## D1 — Context

Four modelos require the operator to supply repeating structured records
rather than a flat set of scalar casilla values:

- **M184** (atribución de rentas): each partícipe in an entidad en atribución
  de rentas is a separate row with NIF, share percentage, and attributed
  income. Blocked for Núria (round-17, F1+F2 atribución).
- **M232** (operaciones vinculadas): each related-party transaction is a row
  with NIF, vinculación type, amount, transfer pricing method, and country.
  Blocked for Sergio (round-13, C4 director-SL loan).
- **M349** (operaciones intracomunitarias): each EU trading partner is a row
  with EU VAT NIF, clave (E/S/T/R/A/I/M per Orden HAC/174/2020), and amount.
  Confirmed for Pedro (round-18 #2).
- **M347** (operaciones con terceros): each counterparty above the €3,005.06
  threshold (RD 1065/2007 art. 31.1) is a row with NIF, quarterly breakdowns,
  clave, and country. Confirmed for Ramón (round-24).

The M303 calculation engine and the existing `work calculate` CLI surface
assumed a single flat set of `binding_values`. All four of the above modelos
were completely blocked because no mechanism existed to supply repeating
record sets through the CLI. Audit round-17 classified M184 as a SHOW-STOPPER;
round-18 triple-confirmed the pattern.

## D2 — Decision

### D2.1 — Introduce `--row TYPE FIELD=value ...` CLI flag

Add `--row TYPE FIELD=value` as a repeatable option on `work calculate`. Each
`--row` invocation supplies one record of the given `TYPE`. The CLI parser
`_parse_row_spec` in `src/aeat/entrypoints/cli/_modelo.py` dispatches to the
appropriate pydantic row model based on `TYPE`.

### D2.2 — Introduce `ModeloDetailRow` strict pydantic discriminated union

Add `ModeloDetailRow` as a `Annotated[..., Discriminator("row_type")]`
union in `src/aeat/domain/modelos/_row_models.py` with members:
- `Modelo184MemberRow` — fields: `row_type="miembro"`, `nif`, `share:
  Decimal` (0–100), `importe: Decimal`.
- `Modelo232VinculadaRow` — fields: `row_type="vinculada"`, `nif`,
  `tipo_vinculacion`, `importe`, `metodo`, `pais`.
- `Modelo349OperadorRow` — fields: `row_type="operador"`, `codigo_pais`,
  `nif_comunitario` (per-country EU VAT regex per Directive 2006/112/EC
  Annex XI), `razon_social`, `clave_operacion` (7-value closed set per
  Orden HAC/174/2020 Annex II), `importe`.
- `Modelo347ContraparteRow` — fields: `row_type="contraparte"`, `nif`,
  `nombre`, `importe_Q1/Q2/Q3/Q4`, `clave_operacion` (9-value closed set
  per Orden EHA/3012/2008), `pais_codigo`.

All row models use `strict=True, frozen=True, extra="forbid"`.

### D2.3 — Per-type validation in the CLI layer

The CLI `work calculate` path validates:
- M184: `_validate_m184_share_sum` enforces that the sum of `share` across
  all `miembro` rows equals 100%.
- M347: `_validate_m347_threshold` enforces that each contraparte's
  `importe_total` exceeds the €3,005.06 RD 1065/2007 threshold.
- M349: `validate_m349_nif_format` dispatches to per-country EU VAT NIF
  patterns; falls back to the generic `^[A-Z]{2}[A-Z0-9]{2,15}$` pattern.

## D3 — Alternatives considered

**Alternative A: per-modelo dedicated subcommands.** Separate `work calculate-
m184`, `work calculate-m232`, etc. subcommands with modelo-specific flags.
Rejected: the CLI root surface rule caps the surface to `config` and `app`;
proliferating per-modelo subcommands would breach this constraint and prevent
the unified `work calculate` workflow from handling mixed-modelo filings for
the same period.

**Alternative B: JSON file input.** Accept `--rows-file path/to/rows.json`
with a structured JSON payload. Rejected as the primary mechanism: it
requires file management by the operator and defeats the interactive
`work calculate` shell workflow. The `--row` flag is composable and shell-
friendly. JSON file input may be added as a convenience in a future step.

**Alternative C: treat M184/M232/M349/M347 as fundamentally different CLI
surfaces.** All four modelos were blocked at persona audit rounds; deferring
the cross-cutting mechanism to per-modelo campaigns would leave all four
blocked indefinitely. The unified `--row TYPE` flag amortises the
implementation cost across the four modelos.

## D4 — Trade-offs

- **Union discrimination.** The `row_type` discriminator field is a string
  literal on each row model. This produces verbose but inspectable CLI
  invocations (`--row operador codigo_pais=DE ...`). The alternative of
  positional type detection was rejected because it requires the parser to
  infer type from the field set, which is ambiguous when fields overlap.
- **NIF validation complexity.** EU VAT NIF formats differ significantly
  across member states. Per-country regex patterns (DE, FR, IT, PT, NL, BE,
  AT, IE, PL, SE, DK, FI, LU) are maintained in `_row_models.py`. This
  creates a maintenance obligation as formats evolve; however, the fallback
  generic pattern accepts any well-formed EU NIF, so validation failures
  affect only countries with a dedicated pattern.
- **M349 threshold vs M347.** M349 has no monetary threshold per Orden
  HAC/174/2020 (every intracomunitario operator must be declared regardless
  of amount). M347's €3,005.06 threshold is enforced in the CLI. This
  asymmetry is correct per the respective normatives.

## D5 — Consequences

- `src/aeat/domain/modelos/_row_models.py` is the canonical definition point
  for all row types. The CLI `_modelo.py` imports from it for parsing and
  validation.
- All four modelos (M184, M232, M349, M347) are unblocked in the CLI `work
  calculate` surface.
- The `ModeloDetailRow` union is extensible: adding a new row type requires a
  new pydantic model with a unique `row_type` literal and a corresponding
  `_parse_row_spec` branch.
- 24 tests in `test_row_models.py` and `test_work_calculate_row_flag.py`
  verify row construction, NIF validation, threshold enforcement, and share-
  sum invariants.
