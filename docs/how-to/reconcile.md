# Reconcile a filed modelo against its justificante

After you file through the AEAT portal, download the justificante (the official
receipt AEAT issues after you sign and submit). Use this guide to check that the
justificante matches your local filing record.

This check is local. It reads the PDF you supply and never contacts AEAT.

## Before you start

You need:

- an active profile
- a locally filed work unit (you have run `aeat app modelo work file` for this
  filing)
- the justificante PDF on disk

To create a profile, see [Set up your taxpayer profile](profile-setup.md). For
the filing workflow, see the [quickstart](quickstart.md).

## Run the reconciliation

Compare your local filing record against the justificante:

```bash
aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file ./justificante.pdf
```

Replace `303`, `2026`, and `1T` with the modelo, year, and period of your
actual filing.

## Read the result

The command reports one of three verdicts:

- **matches** — the justificante matches the local filing record.
- **mismatches** — one or more fields differ. The report names each field and
  shows the local value next to the value found in the PDF.
- **evidence_invalid** — the PDF could not be read. Check that the file is the
  actual AEAT justificante and not a different document.

Fields checked include the modelo code, the filing year, and the taxpayer
identifier (NIF, CIF, DNI, NIE, or NII).

## Handle a mismatch

If the verdict is `mismatches`:

1. Check that the justificante PDF is the correct one for this filing (not a
   different period or a different taxpayer).
2. If the PDF is correct and your local record has the wrong value, use the
   amendment workflow. See
   [Review and supply calculation inputs](review-calculation-values.md).
3. If the PDF appears wrong, contact your asesor or AEAT directly.

## Review past reconciliations

Each reconciliation is recorded in the profile's event history. List the past
reconciliations recorded for the active profile:

```bash
aeat app modelo reconciliation-history
```

Add `--work-unit-id <id>` to narrow the list to a single work unit. Each row
shows when the reconciliation ran, the work unit, the evidence source, the
verdict, and how many fields differed. Reconciliation is repeatable on demand
from the justificante, so this is a convenience read-back rather than a separate
stored record.

## Next steps

- [Quickstart](quickstart.md) — the end-to-end filing workflow.
- [Review and supply calculation inputs](review-calculation-values.md) — amend
  a filing if reconciliation finds a mismatch.
- [CLI reference](../cli/index.rst) — full option reference.
- [Diagnose and repair your local setup](troubleshooting.md) — fix local
  readiness problems.
