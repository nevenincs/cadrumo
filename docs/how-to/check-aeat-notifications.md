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
  one at a terminal so you can record and verify its one-time recovery phrase:

  ```{cli-sequence} check-notifications-profile
  :verify: Confirm profile creation requires the interactive recovery handoff and leaves a selected profile active.
  ```

- the taxpayer's fiscal ID (generalized as NIF, CIF, DNI, NIE, or NII) saved in that profile
- the profile passphrase that unwraps this profile's independent encryption
  key; the tool prompts for it.
- AEAT live-read authentication configured; see [Authenticate with AEAT](authenticate-with-aeat.md)

---

## 1. Official AEAT notifications (DEHu)

DEHu is the official AEAT electronic inbox for notifications (comunicaciones
and notificaciones). The card shows the notification reads: pull downloads and
saves them locally, list shows your current DEHu notifications, view opens a
saved download by its reference number, and latest shows the most recent
snapshot in the active profile.

```{cli-sequence} check-notifications-dehu
```

---

## 2. Read documents from notifications you already opened

Read a notification document only after you have personally opened that
notification in the AEAT sede. Opening an unread electronic notification is a
legally consequential act: it serves the notification and starts its appeal and
payment periods. The tool therefore refuses to pull a document unless AEAT
already reports its notification as read. Open an unread notification yourself
when you decide that those periods should begin.

Pull one eligible document into encrypted local custody, view a stored document
without contacting AEAT, or list the figures reported by each parsed document:

```{cli-sequence} check-notifications-documents
```

Treat history as a document record, not as a balance. It does not total the
figures, state what is currently payable, or replace the recaudación register
shown by the `aeat app live deudas` commands. A document alone does not establish
whether its amount was paid, appealed, reduced, or superseded.

---

## 3. Declaration history (expedientes)

Expedientes are the official AEAT record of your past declarations: each
filed return for each modelo and year, with its status and filing date.

The card shows the expedientes reads: pull downloads the history for one form
and year, pull with a year range covers several years at once (leave out
`--modelo` to download history for all your registered forms), list shows saved
downloads, view opens one download's details (individual declarations, status,
dates, and links to justificantes), and latest shows the most recent snapshot.

```{cli-sequence} check-notifications-expedientes
```

---

## 4. Filed declaration detail

Download the box-by-box values from a return you have already filed with AEAT.

The card shows the filed-detail reads. `filed list` lists the filed returns
AEAT holds without saving their box values (it still reads from AEAT live, so it
needs configured authentication like any other live command). `filed pull`
downloads and saves the full box values from one return or across a year range,
and `filed pull-sources` downloads the source declarations a target filing
depends on (for example, the Modelo 303 returns a Modelo 390 annual summary
needs).

```{cli-sequence} check-notifications-filed
```

---

## 5. NIF and EU VAT verification

Verify whether a NIF is registered for intra-EU VAT purposes (the VIES
register), or check a Spanish NIF in the Spanish ROI register.

The card shows the verification reads. `verify nif-iva` checks whether a foreign
EU VAT number is valid, and `verify tgvi` checks whether a Spanish NIF or NIE
appears in the Spanish ROI register (add `--expected valid|invalid|unknown` to
compare against an expected result). `verify list` shows past verifications,
`verify view` opens one by its observation id, and `verify latest` shows the
latest observation for a NIF.

```{cli-sequence} check-notifications-verify
```

---

## 6. Official AEAT portal catalogue

The card shows the portal-catalogue reads. `portals list` shows the official
AEAT online portals the tool knows about and their authentication requirements;
narrow it to one form with `--modelo` or to one category with `--category` (the
accepted categories are `auth`, `filing`, `censo`, `consultation`, `borrador`,
`payment`, and `calendar_reference`). Use `--modelo` or `--category`, not both:
they are mutually exclusive. `portals view` opens one portal's details.

```{cli-sequence} check-notifications-portals
```

---

## 7. Borrador (draft Modelo 100)

The borrador is the pre-calculated Modelo 100 IRPF draft that AEAT makes
available to wage earners. The card shows the borrador reads: list shows the
snapshots, view opens one borrador's box values, and latest shows the latest
active draft for a filing year.

```{cli-sequence} check-notifications-borrador
```

---

## 8. IVA compensation balance

Your IVA compensation balance (saldo a compensar) is the amount of overpaid
IVA from prior quarters that can be deducted from future Modelo 303 filings.
The card shows the IVA-wallet reads. `pull` downloads and tracks your current
balance, `pull-history` reconstructs past compensation decisions from prior
Modelo 303 filings, `pull-evidence` captures past returns and the current IVA
evidence in a single read-only run, and `history` lists the persisted balances
and decisions held locally.

```{cli-sequence} check-notifications-iva-wallet
```

---

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Reconcile filing justificantes](reconcile.md)
