# How to prepare the annual Modelo 390 summary

This guide shows you how to build, verify, and export Modelo 390, the annual
value-added tax (VAT), or impuesto sobre el valor añadido (IVA), summary, using
your local quarterly Modelo 303 history.

Before you begin:

- Confirm you have an active taxpayer profile. If not, see
  [Set up your taxpayer profile](profile-setup.md).
- Calculate and file all four quarterly Modelo 303 returns for the target year
  first. See [How to prepare a Modelo 303 quarterly filing](modelo-303.md).

## Confirm quarterly Modelo 303 history

Check each quarter before starting the annual summary:

```bash
aeat app modelo work status --modelo 303 --year 2025 --period 1T
aeat app modelo work status --modelo 303 --year 2025 --period 2T
aeat app modelo work status --modelo 303 --year 2025 --period 3T
aeat app modelo work status --modelo 303 --year 2025 --period 4T
```

Scan the full work-unit list:

```bash
aeat app modelo work list
```

## Create the annual work unit

Create Modelo 390 for the target year. The period code for annual returns is
`0A`:

```bash
aeat app modelo work create --modelo 390 --year 2025 --period 0A
```

The correct regulatory revision resolves automatically. On success, the command
returns the visible annual filing target and the internal audit IDs.

## Calculate the draft

Calculate by visible target:

```bash
aeat app modelo work calculate --modelo 390 --year 2025 --period 0A
```

The command pulls data from your local quarterly Modelo 303 filings and saves a
calculation revision under the annual work unit.

## Verify the draft

Verify the selected calculation for the annual filing:

```bash
aeat app modelo work verify --modelo 390 --year 2025 --period 0A
```

On success, the selected revision transitions to verified-complete.

## Export the fichero-BOE file

Export the verified return:

```bash
aeat app modelo export --modelo 390 --year 2025 --period 0A --output ./modelo-390-annual.boe
```

The command writes a local AEAT-compatible fichero-BOE file. Upload this file
manually to the official AEAT electronic filing portal.

Exact IDs remain available when you need advanced revision selection or
automation, but the normal annual workflow should use modelo, year, and period.
