# How to prepare a Modelo 303 quarterly filing

This guide shows you how to prepare, verify, and export Modelo 303, the
quarterly value-added tax declaration. In Spanish, value-added tax is impuesto
sobre el valor añadido (IVA).

Before you begin:

- Confirm you have an active taxpayer profile. If not, see
  [Set up your taxpayer profile](profile-setup.md).
- Verify that your transaction ledger has been imported and classified for the
  target quarter. If you need a full example, follow the
  [tutorial](../tutorials/index.md).

## Create the work unit

Create the work unit for the target year and quarter:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
```

The correct regulatory revision resolves automatically unless you pass an exact
`--revision`. On success, the command returns the visible filing target and the
internal audit IDs.

## Calculate the draft

Calculate by repeating the same visible filing target:

```bash
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
```

The command maps ledger aggregates to form boxes (*casillas*) and saves a
calculation revision under the work unit. If you need to supply manual
adjustments or bindings, use `--casilla` and `--binding`, for example
`--casilla 01=12000.00`.

## Verify the return

Verify the selected calculation for this filing:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

On success, the selected revision transitions to verified-complete.

## Export the fichero-BOE file

Export the verified return to the official text format:

```bash
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

The command writes a local AEAT-compatible fichero-BOE file and prints its
location, size, and SHA-256 checksum. Upload this file manually to the official
AEAT portal.

## Helpful queries

- **Show filing status**:
  `aeat app modelo work status --modelo 303 --year 2026 --period 1T`
- **List form boxes**: `aeat app modelo casillas 303`
- **List missing bindings**:
  `aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`
- **List calculation revisions**:
  `aeat app modelo work revisions --modelo 303 --year 2026 --period 1T`

Exact IDs remain available for advanced recovery, automation, and ambiguity
resolution, but the common workflow should use modelo, year, and period.
