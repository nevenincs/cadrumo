# How to run the shortest Modelo lifecycle

This is the shortest path from a ready local workspace to an exported modelo
file. It assumes you already have `aeat` installed, an active profile, and an
imported and classified ledger.

- No profile yet? See [Set up your taxpayer profile](profile-setup.md).
- Not installed, or no ledger yet? [Get started](../getting-started.md) installs
  the tool, and the [tutorial](../tutorials/index.md) walks through a sample
  ledger.

`aeat` produces a local file and never submits it. You upload it yourself to the
Agencia Estatal de Administración Tributaria (AEAT).

## Produce the file

This example builds Modelo 130 for the first quarter of 2024.

1. Create or reuse the work unit for the filing:

   ```bash
   aeat app modelo work create --modelo 130 --year 2024 --period 1T
   ```

   The command prints the visible target and internal audit IDs. Use `--revision`
   only when you need an exact registry revision instead of the default selected
   from the year and period.

2. Calculate the figures for the same filing:

   ```bash
   aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
   ```

   On success, the command prints the casilla table and saves a calculation
   revision under the work unit. If it reports missing figures, find the field
   numbers with `aeat app modelo casillas 130`, then supply each value and run
   the same visible target again:

   ```bash
   aeat app modelo work calculate --modelo 130 --year 2024 --period 1T --casilla NUMBER=VALUE
   ```

   A value passed with `--casilla` overrides the ledger-derived value for that
   field.

3. Verify the selected calculation revision for the filing:

   ```bash
   aeat app modelo work verify --modelo 130 --year 2024 --period 1T
   ```

   Verification uses the command's revision selector default for this filing
   target. It does not mean "latest" for every command.

4. Export the verified filing:

   ```bash
   aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.txt
   ```

   `aeat` writes the file and prints its path, size, and content hash.

Pass exact work-unit or calculation-revision IDs only when an automation already
has them, or when you need to resolve an ambiguity explicitly.

Upload the exported file yourself at the AEAT electronic portal.

## Where next

- [Set up your taxpayer profile](profile-setup.md) - create profiles and switch
  between them.
- [Common filing recipes](index.md) - other modelos and tasks, such as 303, 390,
  and the censo update.
- [How filings, work units, and calculation revisions fit
  together](filing-spine.md) - the filing target and revision model.
- [Command reference](../cli/index.rst) - every flag and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here.
- Report a problem or ask a question on the
  [issue tracker](https://github.com/wgergely/aeat/issues).
