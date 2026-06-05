# How to run the shortest Modelo lifecycle

This is the shortest path from a ready local workspace to an exported modelo
file. It assumes you already have `aeat` installed, an active profile, and an
imported and classified ledger.

- If you do not have a profile, see
  [Set up your taxpayer profile](profile-setup.md).
- If you have not installed `aeat` or imported a ledger, start with
  [Get started](../getting-started.md). The
  [tutorial](../tutorials/index.md) walks through a sample ledger.

`aeat` produces a local file and never submits it. You upload it yourself to the
Agencia Estatal de Administración Tributaria (AEAT).

## Produce the file

This example builds Modelo 130 for the first quarter of 2024.

1. Start the local workspace for the filing:

   ```bash
   aeat app modelo work create --modelo 130 --year 2024 --period 1T
   ```

   `aeat` chooses the rule set from the modelo, year, and period. Ignore
   printed internal IDs unless the command asks you to resolve an ambiguity.

2. Calculate the figures for the same filing:

   ```bash
   aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
   ```

   On success, the command prints the casilla table and saves the draft. If it
   reports missing figures, find the field numbers with
   `aeat app modelo casillas 130`, then supply each value and run the same
   filing target again:

   ```bash
   aeat app modelo work calculate --modelo 130 --year 2024 --period 1T --casilla NUMBER=VALUE
   ```

   A value passed with `--casilla` overrides the ledger-derived value for that
   field.

3. Verify the draft for the filing:

   ```bash
   aeat app modelo work verify --modelo 130 --year 2024 --period 1T
   ```

   Verification selects the current draft for this filing target unless you pass
   a different selector. This does not create a generic "latest revision" rule
   for every command.

4. Export the verified filing:

   ```bash
   aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.boe
   ```

   `aeat` writes the file and prints its path, size, and file fingerprint.

Pass exact work-unit or calculation-revision IDs only when an automation already
has them, or when the command asks you to resolve an ambiguity explicitly.

Upload the exported file yourself at the AEAT electronic portal.

## Next steps

- [Set up your taxpayer profile](profile-setup.md) - create profiles and switch
  between them.
- [Common filing recipes](index.md) - other modelos and tasks, such as 303, 390,
  and the censo update.
- [How filings, work units, and calculation revisions fit
  together](filing-spine.md) - the advanced filing workspace and revision model.
- [Command reference](../cli/index.rst) - every flag and exit code.
- [Diagnose and repair your local setup](troubleshooting.md) - fix local setup
  or readiness problems.
