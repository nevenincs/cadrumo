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

Every command on this page needs your master-key passphrase. The tool prompts
for it, or set `AEAT_SECRET_PASSPHRASE` to run non-interactively. The tool's
messages are in Spanish.

If you have no profile yet, create one non-interactively with `--quiet` (a bare
`profile create NAME` opens an interactive wizard instead):

```bash
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria"
```

## Pull a receipt

Fetch the justificante for one filed period and store it in your profile:

```bash
aeat app live justificante pull --modelo 130 --year 2026 --period 1T
```

`pull` is live-only: it reads from AEAT and needs the configured authentication
session. `--modelo`, `--year`, and `--period` are all required. When auth is
not set up, the pull refuses before contacting AEAT with a Cl@ve identity
message (`La identidad de Cl@ve Móvil no coincide...`); on a first run the real
cause is usually that no AEAT session is configured yet - set one up with
[Authenticate with AEAT](authenticate-with-aeat.md). To work from a receipt PDF
you already downloaded by hand, parse it locally instead with `aeat app modelo
reconcile file --file PATH` (see
[Reconcile a filed modelo against its justificante](reconcile.md)).

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
