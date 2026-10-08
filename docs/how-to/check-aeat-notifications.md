# Read AEAT notifications and other live data

This page covers the live read-only AEAT surfaces: official notifications, declaration history, filed returns, NIF checks, and your VAT compensation balance. It also covers the local portal catalogue and the borrador, which you import from a PDF you download yourself. The `pull`, `verify`, and `filed list` commands contact AEAT and save what they read locally. The `list`, `view`, `latest`, and `history` commands read only your saved copies. None of them file anything or change your AEAT records.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you [choose another
language](profile-setup.md#choose-the-output-language).

## How a live read works

Every live read works the same way. It uses your configured authentication,
reads from the AEAT sede read-only, and saves an encrypted local copy in
your profile. It applies nothing automatically: a pull saves a local copy,
and applying a downloaded fact updates only your local profile or records,
and only after you review it. Nothing is ever sent back to AEAT. You remain
the only one who files. To understand that boundary, see
[Recording a filing, and why the tool never files for you](../explanation/recording-a-filing-and-the-boundary.md).

Two live surfaces have their own guides: censo facts are covered in [Maintain
Modelo 036 census facts in your profile](censo-update.md), and AEAT receipts
(justificantes) in {ref}`Pull and store the AEAT receipt <pull-and-store-the-justificante>`.

Before contacting AEAT, the notification, expediente, AEAT receipt, filed declaration, and VAT compensation balance reads run an authentication check and print redacted `auth_*` status lines. The read refuses if no provider is configured, if the certificate file is missing, or if the Cl@ve identity does not match your profile's tax ID. Configure a provider first. See [Authenticate with AEAT](authenticate-with-aeat.md).

## Before you start

You need:
- an [active profile](profile-setup.md#what-the-active-profile-means). Create
  one at a terminal so you can choose its passphrase:

  ```{cli-sequence} check-notifications-profile
  :verify: Confirm profile creation prompts for the passphrase at a terminal and leaves a selected profile active.
  ```

- the taxpayer's fiscal ID (NIF or NIE) saved in that profile
- the profile passphrase that unwraps this profile's independent encryption
  key; the tool prompts for it.
- AEAT live-read authentication configured; see [Authenticate with AEAT](authenticate-with-aeat.md)

---

## 1. Official AEAT notifications (DEHú)

DEHú (Dirección Electrónica Habilitada única) is the official electronic
address for notifications. Cadrumo reads the notificaciones and comunicaciones
that AEAT has served you, from AEAT's electronic notification service in its
sede. It does not read notifications from other public bodies.
The example shows the notification reads: pull downloads your notifications and
saves them as a snapshot, list shows your saved snapshots,
view opens a saved snapshot by its ID (or an unambiguous prefix of it), and
latest shows the most recent snapshot in the active profile.

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

Identify a document by the `certificado` number AEAT gives its notification.
Pull one eligible document into encrypted local custody, view a stored document
without contacting AEAT, or list the figures reported by each parsed document:

```{cli-sequence} check-notifications-documents
```

Treat history as a document record, not as a balance. It does not total the
figures, state what is currently payable, or replace the recaudación register
reported by AEAT's debts consulta. A document alone does not establish
whether its amount was paid, appealed, reduced, or superseded.

---

## 3. Declaration history (expedientes)

Expedientes are the official AEAT record of your past declarations: each
filed return for each modelo and year, with its status and filing date.

The example shows the expedientes reads: pull downloads the history for one form and year, pull with a year range covers several years at once (leave out `--modelo` to download history for all your registered forms), list shows saved downloads, view opens one download's details (individual declarations, status, dates, and links to AEAT receipts), and latest shows the most recent snapshot.

```{cli-sequence} check-notifications-expedientes
```

---

## 4. Filed declaration detail

Download the box-by-box values from a return you have already filed with AEAT.

The example shows the filed-detail reads. `filed list` lists the filed returns
AEAT holds without saving their box values (it still reads from AEAT live, so it
needs configured authentication like any other live command). `filed pull`
downloads and saves the full box values from one return or across a year range,
and `filed pull-sources` downloads the source declarations a target filing
depends on (for example, the Modelo 303 returns a Modelo 390 annual summary
needs).

```{cli-sequence} check-notifications-filed
```

---

(5-nif-and-eu-vat-verification)=
## 5. NIF and EU VAT checks

Check whether a NIF is registered for intra-EU VAT purposes (the VIES register),
or look up a Spanish NIF in the Spanish ROI register.

The example shows the check reads. `verify nif-iva` checks whether a foreign EU VAT number is valid, and `verify tgvi` checks whether a Spanish NIF or NIE appears in the Spanish ROI register (add `--expected valid|invalid|unknown` to compare against an expected result). `verify list` shows past checks, `verify view` opens one by its observation id, and `verify latest` shows the latest observation for a NIF.

```{cli-sequence} check-notifications-verify
```

---

## 6. Official AEAT portal catalogue

The portal catalogue is built into Cadrumo, so these commands work offline and
never contact AEAT. The example shows the portal-catalogue reads. `portals list`
shows the official
AEAT online portals the tool knows about and their authentication requirements;
narrow it to one form with `--modelo` or to one category with `--category` (the
accepted categories are `auth`, `filing`, `censo`, `consultation`, `borrador`,
`payment`, and `calendar_reference`). Use `--modelo` or `--category`, not both:
they are mutually exclusive. `portals view` opens one portal's details.

```{cli-sequence} check-notifications-portals
```

---

## 7. Borrador (draft Modelo 100)

The borrador is the pre-calculated Modelo 100 IRPF draft that AEAT makes available to taxpayers who meet its conditions. Cadrumo does not download it. Download the borrador PDF from the AEAT sede yourself, then import it with `aeat app live borrador 100 import`, passing the file with `--file` and its year with `--filing-year`, as the first command in the example shows. Import refuses a PDF that yields too few of the expected boxes, and stores nothing. The example shows the stored-snapshot reads, which never contact AEAT: list shows the snapshots (`--state` filters them), view opens one borrador's box values, and latest shows the latest active draft for a filing year.

```{cli-sequence} check-notifications-borrador
```

---

(8-iva-compensation-balance)=
## 8. VAT compensation balance

Your VAT compensation balance (saldo a compensar) is the amount of overpaid VAT from prior quarters that can be deducted from future Modelo 303 filings. The example shows the VAT compensation balance reads. `pull` downloads and tracks your current balance, `pull-history` reconstructs past compensation decisions from prior Modelo 303 filings, `pull-evidence` captures past returns and the current VAT data as proof in a single read-only run, and `history` lists the persisted balances and decisions held locally.

```{cli-sequence} check-notifications-iva-wallet
```

---

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Reconcile a filed modelo against its AEAT receipt](reconcile.md)
