# Privacy policy

**Last updated: 5 October 2026**

This policy covers the Cadrumo `aeat` software and this repository at
[github.com/nevenincs/cadrumo](https://github.com/nevenincs/cadrumo).

**Responsible party:** Neve Nincs, the legal entity behind
[neve.md](https://neve.md) and the publisher of the Cadrumo project. Contact:
<hello@neve.md>, the [issue tracker](https://github.com/nevenincs/cadrumo/issues),
or the private channel in [`SECURITY.md`](SECURITY.md) for sensitive reports.

## The short version

**We never collect, receive, store, or share your data. There is nothing to
opt out of, because nothing is sent to us in the first place.**

## The software

- Your financial records — ledger rows, invoices, evidence bytes, taxpayer
  profiles — persist **inside encrypted storage on your own machine**,
  unlocked through your OS keychain or a passphrase. There is no cloud
  backend, no account, and no server of ours involved. They leave your machine
  only through a feature you start yourself, to a destination listed below.
- The software sends **no analytics, no crash reports, and no usage data** to
  the authors or to anyone else.
- Network connections happen **only when you invoke a feature that needs
  one**, and only to the counterparty you direct them to:
  - read-only AEAT pulls (justificantes, notifications, censo data) go to the
    AEAT's own portals under your credentials, per profile capability opt-in;
  - the optional Google sign-in, workbook export, and encrypted copy go to
    your own Google account under the permissions you grant, as described in
    [Google sign-in and Google user data](#google-sign-in-and-google-user-data);
  - installing Cadrumo and its optional components, such as local AI models
    and the browser it uses to reach the AEAT, downloads them from the servers
    that host them, as any software installation does;
  - optional hosted AI processing sends the transaction fields or the evidence
    document you consent to send to the provider you configure, under that
    provider's terms.
  None of these paths route through infrastructure we operate, and none of
  them reports anything back to us.
- The software **never files taxes** and never writes to the AEAT.

## Google sign-in and Google user data

In this section, "Cadrumo" means the program running on your computer, and
"we" means its publisher, Neve Nincs.

Cadrumo can connect to your Google account for two purposes:

- to write the calculation workbooks it generates to your Google Drive, so you
  can review them, and to read those workbooks back when you ask;
- to keep an encrypted copy of your profile's records in your Google Drive.

The connection is optional. Cadrumo does not contact your Google account until
you run `aeat config google login` in a terminal. Nothing is stored or written
until you approve the request in your browser.

Google's permission screen shows the app name Cadrumo. Sign-in happens
directly between your computer and Google. None of our servers is involved.

### What Cadrumo asks Google for

| Permission | What it allows | Why Cadrumo asks |
| --- | --- | --- |
| `openid` and `userinfo.email` | Read the primary email address of your Google account. | To record and show you which Google account a profile is connected to. |
| `drive.file` | Create files and folders in your Google Drive, and read, change, or delete the ones Cadrumo created. | To write workbooks and the encrypted copy, and to read workbooks back. |

Cadrumo asks for nothing else. It does not ask for access to the rest of your
Google Drive, or to Gmail, Calendar, or contacts. Under the `drive.file`
permission, Google does not let Cadrumo see, list, or change files that
Cadrumo did not create, and Cadrumo itself refuses any spreadsheet it did not
create.

### How Cadrumo uses and stores Google data

- **Sign-in token.** Google gives Cadrumo a sign-in token. It is not your
  Google password, which Cadrumo never sees. Cadrumo stores the token in the
  profile's encrypted storage on your computer and presents it only to Google.
- **Sign-in record.** In the same encrypted storage, Cadrumo keeps your email
  address, the permissions you granted, the time you signed in, and the
  identifier of the Google Drive folder it created. `aeat config google
  status` shows your email address.
- **Folder.** Signing in creates one folder in your Google Drive, named
  Cadrumo plus a short profile identifier. Everything Cadrumo writes goes
  inside it.
- **Workbooks.** Workbooks are not encrypted. They are ordinary Google Sheets
  files that hold the calculations you asked Cadrumo to export or verify. You,
  anyone you share them with, and Google (under its own terms) can read them.
- **Reading workbooks back.** When you ask, Cadrumo reads a workbook it
  created from your Google Drive and processes it on your computer.
- **Encrypted copy.** `aeat config profile archive push` uploads each record
  of your profile, including the sign-in token and sign-in record, in the
  encrypted form it has on your computer. It also uploads an unencrypted index
  that lists record categories, sizes, hashes, and timestamps, and the file
  names carry a category label. Cadrumo cannot currently restore a profile
  from this copy alone.

### What we receive

We receive none of your Google data. Your email address, your sign-in token,
and your files never reach us.

Sign-in is registered with Google under a Google Cloud project that we
operate. Google shows us aggregate figures for that project, such as the
number of requests and the number of accounts that have signed in. Those
figures do not identify you.

### Sharing and other uses

Cadrumo does not send your email address or your sign-in token to anyone other
than Google. We do not sell Google user data, use it for advertising, or use
it to train AI models. We never receive it.

Cadrumo's use and transfer to any other app of information received from
Google APIs will adhere to the [Google API Services User Data
Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

### Retention and deletion

Cadrumo keeps the sign-in token and sign-in record until you sign out or
delete the profile.

- **Signing out.** `aeat config google logout` deletes the sign-in token and
  the sign-in record from the profile, except the identifier of the Google
  Drive folder. Encrypted records of earlier Google commands in the profile
  may still contain your email address. Deleting the profile removes all of
  it from your computer.
- **Signing out does not withdraw the permission at Google** and deletes
  nothing from your Google Drive. The workbooks and the encrypted copy are
  your files. Delete them in Google Drive when you no longer want them.
- **Withdrawing access.** Remove Cadrumo on the
  [third-party connections page](https://myaccount.google.com/connections) of
  your Google Account. The token stored on your computer stops working from
  then on.

## GDPR position

The software does not transmit personal data to us. Data processed locally by
the software on your machine, for your own tax affairs, remains under your
control. If you send personal data through a repository service such as a
GitHub issue, that separate submission is processed under the service's terms;
contact us through the repository if you need help with data you submitted.

## Changes

Any change to this policy lands as a commit to this file in the public
repository, with its full history preserved in git.
