# Pull and keep your filing receipts

When you file at the AEAT portal, AEAT issues a {term}`justificante` — the
signed PDF receipt that proves what was filed, when, and under which
verification code. Keep that receipt with your records: it is the official
evidence behind every filed period.

Use this guide to pull the receipt for a filed period from AEAT, store it as
an encrypted capture in your profile, and find it again later.

## Before you start

You need:

- an active profile
- a filing already presented at AEAT for the modelo, year, and period you
  want the receipt for
- working AEAT authentication — see
  [Authenticate with AEAT](authenticate-with-aeat.md)

## Pull a receipt

Fetch the justificante for one filed period and store it in your profile:

```bash
aeat app live justificante pull --modelo 130 --year 2026 --period 1T
```

The pull is read-only at AEAT. The output reports the stored capture: its
snapshot id, the expediente it belongs to, the CSV verification code printed
on the receipt, the PDF's content fingerprint, and when it was captured.

The PDF bytes are stored encrypted inside your profile. You do not need to
keep a separate downloaded copy.

Pulling again for the same modelo, year, and period stores a fresh capture
and marks the earlier one as superseded, so the latest receipt is always the
active one.

## List stored receipts

See every capture stored in the active profile:

```bash
aeat app live justificante list
```

Each row shows the snapshot id, modelo, year, period, and capture time. Note
the snapshot id of the capture you want to inspect.

## View one receipt

Show the full provenance of one capture:

```bash
aeat app live justificante view <snapshot-id>
```

An unambiguous prefix of the snapshot id is enough. The view reports the
expediente id, the CSV verification code, the PDF fingerprint, whether the
capture is still active or superseded, and when it was captured.

## Use a receipt to check your local record

The stored receipt is the evidence the reconciliation workflow reads. To
compare a receipt against your local filing record in one step, run
`aeat app modelo reconcile pull` — it fetches and reconciles together. See
[Reconcile a filed modelo against its justificante](reconcile.md).

## Next steps

- [Reconcile a filed modelo against its justificante](reconcile.md) — check
  your local filing record against the receipt.
- [Upload your exported modelo at the AEAT portal](file-at-aeat.md) — the
  filing handoff that produces the justificante.
- [Authenticate with AEAT](authenticate-with-aeat.md) — set up the
  read-only AEAT session the pull needs.
- [CLI reference](../cli/index.rst) — full option reference.
