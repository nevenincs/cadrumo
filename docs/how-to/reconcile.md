# Reconcile a filing against its justificante

After you file with the Agencia Estatal de Administración Tributaria (AEAT) and
download the justificante (the receipt PDF the AEAT issues), reconcile it against
your work unit to confirm the figures match. This check is local: it reads the
PDF you supply and never contacts the AEAT.

You need an active profile, a work unit you've already calculated, and the
justificante PDF on disk. To set up a profile, see
[Set up your taxpayer profile](profile-setup.md); to build a work unit, see the
[quickstart](quickstart.md).

## Run the reconciliation

Find the work-unit id with `aeat app modelo work list`, then pass it with the
path to the justificante PDF:

```
aeat app modelo reconcile <work-unit-id> --from-justificante ./justificante.pdf
```

It compares the work unit's figures against the PDF and reports the matches and
any divergences. Add `--by "<actor>"` to record who ran the check.

## Read the result

On a clean match, the report confirms the figures agree. If they diverge, the
report names which casillas (the numbered boxes on the form) differ. Investigate the source - recalculate the work
unit, or recheck the justificante - before you rely on the filing.

## Where next

- [Quickstart](quickstart.md) - build and export a modelo.
- [Common filing recipes](index.md) - other modelos and tasks.
- [CLI reference](../cli/index.rst) - every reconcile flag and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here.
- Report a problem on the [issue tracker](https://github.com/wgergely/aeat/issues).
