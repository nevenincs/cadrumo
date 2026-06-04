# How to reconcile a filed Modelo against its justificante

After you file with the Agencia Estatal de Administración Tributaria (AEAT),
download the justificante. Reconcile it against your local work unit to confirm
that the receipt belongs to the expected modelo and filing year. This check is
local: it reads the Portable Document Format (PDF) file you supply and never
contacts AEAT.

You need an active profile, a local work unit, and the justificante PDF on disk.
To set up a profile, see [Set up your taxpayer profile](profile-setup.md). To
create a local work unit, see the [quickstart](quickstart.md).

## Run the reconciliation

Pass the same visible filing target you used for the lifecycle commands, plus
the path to the justificante PDF:

```bash
aeat app modelo reconcile --modelo 303 --year 2026 --period 1T --from-justificante ./justificante.pdf
```

The command resolves the active-profile work unit for that modelo, year, and
period, then parses the justificante and checks its filing metadata against the
selected local work unit. Add `--by "<actor>"` to record who ran the check.

If more than one registry revision could match the same visible target, the CLI
refuses to guess. Re-run the command with `--revision` after choosing the
candidate you intend to reconcile. Exact work-unit IDs remain available as an
advanced option when an automation already holds one.

## Read the result

On a clean match, the report confirms that the justificante modelo and filing
year agree with the selected local work unit. If it diverges, check that you
selected the right modelo, year, and PDF before relying on the receipt.

## Next steps

- [Quickstart](quickstart.md) - build and export a modelo.
- [Common filing recipes](index.md) - other modelos and tasks.
- [Command reference](../cli/index.rst) - every reconcile flag and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here.
- Report a problem on the [issue tracker](https://github.com/wgergely/aeat/issues).
