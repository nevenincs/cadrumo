# Quickstart: produce a modelo file

This is the shortest path to an exported modelo (a Spanish tax form) file. It
assumes you've already installed `aeat`, have an active profile, and have
imported and classified your ledger. The calculation draws its figures from that
ledger. If you're missing a piece:

- No profile yet? See [Set up your taxpayer profile](profile-setup.md) to create
  one and switch between several.
- Not installed, or no ledger yet? [Get started](../getting-started.md) installs
  the tool, and the [tutorial](../tutorials/index.md) walks through importing and
  classifying your ledger.

`aeat` produces a local file and never submits it. You upload it yourself to the
Agencia Estatal de Administración Tributaria (AEAT).

## Produce the file

This example builds Modelo 130, the quarterly income-tax instalment, for the
first quarter of 2024.

First, find the revision - the rule version the form follows. List the revisions
and copy the identifier that covers your period:

```
aeat app modelo describe 130
```

Then run these four steps. Each step prints one identifier you paste into the
next.

1. Create the work unit, the handle for one form, year, and period. Use the
   revision id from describe:

   ```
   aeat app modelo work create --modelo 130 --year 2024 --period 1T --revision <revision>
   ```

   It prints a work-unit id.

2. Calculate the figures. This pulls them from your classified ledger and fills
   the casillas, the numbered fields on the form:

   ```
   aeat app modelo work calculate <work-unit-id>
   ```

   On success it prints the casilla table and a new calculation-revision id. If it
   reports missing figures instead, find the field numbers with
   `aeat app modelo casillas 130`, then supply each one and run it again:

   ```
   aeat app modelo work calculate <work-unit-id> --casilla NUMBER=VALUE
   ```

   A value you pass with `--casilla` overrides the ledger-derived value for that
   field.

3. Verify the calculation against the form's rules. Pass the calculation-revision
   id, not the work-unit id:

   ```
   aeat app modelo work verify <calculation-revision-id>
   ```

4. Export the file. Pass the work-unit id and an output path:

   ```
   aeat app modelo export <work-unit-id> --output ./modelo-130-2024-1T.txt
   ```

   `aeat` writes the file and prints its path, size, and content hash.

Upload that file yourself at the AEAT electronic portal (the sede electrónica).

## Where next

- [Set up your taxpayer profile](profile-setup.md) - create profiles and switch
  between them.
- [Common filing recipes](index.md) - other modelos and tasks, such as 303, 390,
  and the censo update.
- [Pipeline explanation](../explanation/index.md) - how figures trace to the law,
  and why `aeat` never files.
- [CLI reference](../cli/index.rst) - every flag and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here, including *modelo*,
  *casilla*, *revision*, and *work unit*.
- Report a problem or ask a question on the
  [issue tracker](https://github.com/wgergely/aeat/issues).
