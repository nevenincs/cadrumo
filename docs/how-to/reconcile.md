# Reconcile a filed modelo against its justificante

After you file through the AEAT portal, AEAT issues a {term}`justificante` —
the signed receipt that proves what was filed. Reconciliation compares that
receipt against your local filing record, so a typo at the portal, a wrong
period, or a stale local value surfaces now instead of during a later review.

There are two ways to supply the justificante:

- **Pull it from AEAT** with `reconcile pull` — the tool fetches the receipt
  from the AEAT sede (read-only), stores an encrypted copy in your profile,
  and reconciles in one step.
- **Use a local PDF** with `reconcile file --file` — you downloaded the
  justificante yourself; the check is local and never contacts AEAT.

## Before you start

You need:

- an active profile
- a locally filed work unit (you have run `aeat app modelo work file` for this
  filing)
- for `reconcile pull`: working AEAT authentication — see
  [Authenticate with AEAT](authenticate-with-aeat.md)
- for `reconcile file`: the justificante PDF on disk

To create a profile, see [Set up your taxpayer profile](profile-setup.md). For
the filing workflow, see the [quickstart](quickstart.md).

## Pull the justificante from AEAT and reconcile

Fetch the receipt for the filing and reconcile in one command:

```bash
aeat app modelo reconcile pull --modelo 303 --year 2026 --period 1T
```

Replace `303`, `2026`, and `1T` with the modelo, year, and period of your
actual filing. You can also name the work unit directly as a positional
argument instead of the `--modelo --year --period` selectors.

The pull is read-only at AEAT. The fetched receipt is stored as an encrypted
capture in your profile, so the official evidence stays available after the
command finishes. To list or inspect stored captures later, see
[Pull and keep your filing receipts](justificante-receipts.md).

## Reconcile against a local PDF instead

If you already downloaded the justificante from the portal, compare your local
filing record against that file:

```bash
aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file ./justificante.pdf
```

This check is local. It reads the PDF you supply and never contacts AEAT.

## Read the result

Both transports report one of three verdicts:

- **matches** — the justificante matches the local filing record.
- **mismatches** — one or more fields differ. The report names each field and
  shows the local value next to the value found in the PDF.
- **evidence_invalid** — the PDF could not be read. Check that the file is the
  actual AEAT justificante and not a different document.

Fields checked include the modelo code, the filing year, and the taxpayer
identifier (NIF, CIF, DNI, NIE, or NII).

## Handle a mismatch

If the verdict is `mismatches`:

1. Check that the justificante is the correct one for this filing (not a
   different period or a different taxpayer).
2. If the justificante is correct and your local record has the wrong value,
   use the amendment workflow. See
   [Review and supply calculation inputs](review-calculation-values.md).
3. If the justificante itself appears wrong, contact your asesor or AEAT
   directly.

## Review past reconciliations

Each reconciliation is recorded in the profile's event history. List the past
reconciliations recorded for the active profile:

```bash
aeat app modelo reconcile history
```

Add `--work-unit-id <id>` to narrow the list to a single work unit. Each row
shows when the reconciliation ran, the work unit, the evidence source, the
verdict, and how many fields differed. Reconciliation is repeatable on demand
from the justificante, so this is a convenience read-back rather than a separate
stored record.

## Next steps

- [Pull and keep your filing receipts](justificante-receipts.md) — store and
  inspect AEAT receipts independently of reconciliation.
- [Quickstart](quickstart.md) — the end-to-end filing workflow.
- [Review and supply calculation inputs](review-calculation-values.md) — amend
  a filing if reconciliation finds a mismatch.
- [CLI reference](../cli/index.rst) — full option reference.
- [Diagnose and repair your local setup](troubleshooting.md) — fix local
  readiness problems.
