# Read AEAT notifications and other live data

This page covers the live read-only AEAT surfaces: official notifications,
declaration history, filed returns, NIF verification, the portal catalogue,
the borrador, and your IVA compensation balance. All commands in this
section download data and save it locally. None of them file anything or
change your AEAT records.

## How a live read works

Every live read works the same way. It uses your configured authentication,
reads from the AEAT sede read-only, and saves an encrypted local copy in
your profile. It applies nothing automatically: a pull saves a local copy,
and applying a downloaded fact updates only your local profile or records,
and only after you review it. Nothing is ever sent back to AEAT. You remain
the only one who files. To understand that boundary, see
[Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md).

Two live surfaces have their own guides: censo facts are covered in
[Link Modelo 036 census information](censo-update.md), and filing receipts
(justificantes) in
[Pull and store the justificante](reconcile.md#pull-and-store-the-justificante).

Before contacting AEAT, every live read runs an authentication preflight. If
no provider is configured, the read refuses at that preflight; the refusal
text mentions a Cl@ve identity check (`La identidad de Cl@ve Móvil no
coincide...`), but the underlying cause is that authentication is not
configured. Configure a provider first. See
[Authenticate with AEAT](authenticate-with-aeat.md).

## Before you start

You need:
- an [active profile](profile-setup.md#what-the-active-profile-means). Create
  one non-interactively:

  ```bash
  aeat config profile create me --quiet --tax-id <NIF/CIF/DNI/NIE> \
    --name "Ana" --surnames "Garcia Lopez"
  ```

- the taxpayer's fiscal ID (generalized as NIF, CIF, DNI, NIE, or NII) saved in that profile
- the master-key passphrase that protects your local store; the tool
  prompts for it.
- AEAT live-read authentication configured; see [Authenticate with AEAT](authenticate-with-aeat.md)

---

## 1. Official AEAT notifications (DEHu)

DEHu is the official AEAT electronic inbox for notifications (comunicaciones
and notificaciones). Download your notifications and save them locally:
```bash
aeat app live notifications pull
```
Download your current DEHu notifications:
```bash
aeat app live notifications list
```

View a specific saved download by its reference number:
```bash
aeat app live notifications view <snapshot-id>
```

Show the most recent snapshot in the active profile:
```bash
aeat app live notifications latest
```

---

## 2. Declaration history (expedientes)

Expedientes are the official AEAT record of your past declarations: each
filed return for each modelo and year, with its status and filing date.

Download the declaration history for a specific form and year:
```bash
aeat app live expedientes pull --modelo 100 --year 2026
```

Download history for a range of years:

```bash
aeat app live expedientes pull --from-year 2020 --to-year 2026 --modelo 303
```

Leave out `--modelo` to download history for all your registered forms.

List saved downloads:
```bash
aeat app live expedientes list
```

View a specific download's details (individual declarations, status, dates, and links to justificantes):
```bash
aeat app live expedientes view <snapshot-id>
```

Show the most recent expedientes snapshot:
```bash
aeat app live expedientes latest
```

---

## 3. Filed declaration detail

Download the box-by-box values from a return you have already filed with AEAT.

List the filed returns AEAT holds, without saving their full box values. This
still reads from AEAT live, so it needs configured authentication like any other
live command:
```bash
aeat app live filed list --modelo 303 --from-year 2020 --to-year 2026
```

Download and save the full box values from a specific filed return:
```bash
aeat app live filed pull --modelo 303 --year 2026 --period 1T
```

Download all filed returns across a year range:
```bash
aeat app live filed pull --from-year 2020 --to-year 2026
```

Download the source declarations that a target filing depends on (for example,
download the Modelo 303 returns that a Modelo 390 annual summary needs):
```bash
aeat app live filed pull-sources --modelo 303 --year 2026 --period 1T
```

---

## 4. NIF and EU VAT verification

Verify whether a NIF is registered for intra-EU VAT purposes (the VIES
register), or check a Spanish NIF in the Spanish ROI register.

Check whether a foreign EU VAT number is valid:
```bash
aeat app live verify nif-iva ESB12345678
```

Check whether a Spanish NIF or NIE appears in the Spanish ROI register:
```bash
aeat app live verify tgvi 12345678A
```
Use `--expected valid|invalid|unknown` to compare against an expected result.

List past verifications you have run:
```bash
aeat app live verify list --surface tgvi
```

View details of a specific verification:
```bash
aeat app live verify view <observation-id>
```

Show the latest verification observation for a NIF:
```bash
aeat app live verify latest --surface nif_iva --nif ESB12345678
```

---

## 5. Official AEAT portal catalogue

View the list of official AEAT online portals the tool knows about and their
authentication requirements:
```bash
aeat app live portals list
```

Narrow the list to the portals for one form with `--modelo`:
```bash
aeat app live portals list --modelo 303
```

Or narrow it to one category with `--category`. The accepted categories are
`auth`, `filing`, `censo`, `consultation`, `borrador`, `payment`, and
`calendar_reference`:
```bash
aeat app live portals list --category filing
```

Use `--modelo` or `--category`, not both. They are mutually exclusive.

### View portal details
```bash
aeat app live portals view <portal-id>
```

---

## 6. Borrador (draft Modelo 100)

The borrador is the pre-calculated Modelo 100 IRPF draft that AEAT makes
available to wage earners. Download and view borrador snapshots:

```bash
aeat app live borrador 100 list --state active
```

View a specific borrador's box values:
```bash
aeat app live borrador 100 view <snapshot-id>
```

Show the latest active draft for a filing year:
```bash
aeat app live borrador 100 latest --filing-year 2026
```

---

## 7. IVA compensation balance

Your IVA compensation balance (saldo a compensar) is the amount of overpaid
IVA from prior quarters that can be deducted from future Modelo 303 filings.
Download and track your current balance:

```bash
aeat app live iva-wallet pull --year 2026 --period 4T
```

Reconstruct the history of past IVA compensation decisions from prior Modelo
303 filings:
```bash
aeat app live iva-wallet pull-history --from-year 2020 --to-year 2026
```

Capture past returns and pull the current IVA evidence in a single read-only run:
```bash
aeat app live iva-wallet pull-evidence --from-year 2020 --to-year 2026 --target-year 2026 --target-period 4T
```

### View local history
List persisted compensation balances and decisions:
```bash
aeat app live iva-wallet history --as-of-year 2026
```

---

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Reconcile filing justificantes](reconcile.md)
