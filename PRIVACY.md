# Privacy policy

**Last updated: 23 August 2026**

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
  profiles — persist **only inside encrypted storage on your own machine**,
  unlocked through your OS keychain or a passphrase. There is no cloud
  backend, no account, and no server of ours involved.
- The software sends **no telemetry, no analytics, no crash reports, and no
  usage data** to the authors or to anyone else.
- Network connections happen **only when you invoke a feature that needs
  one**, and only to the counterparty you direct them to:
  - read-only AEAT pulls (justificantes, notifications, censo data) go to the
    AEAT's own portals under your credentials, per profile capability opt-in;
  - the optional Google Drive / Sheets export goes to your own Google account
    under OAuth scopes you grant;
  - package installation contacts PyPI like any Python tool;
  - optional cloud classification sends the transaction fields you confirm to
    the provider you configure, under that provider's terms.
  None of these paths route through infrastructure we operate, and none of
  them reports anything back to us.
- The software **never files taxes** and never writes to the AEAT.

## GDPR position

The software does not transmit personal data to us. Data processed locally by
the software on your machine, for your own tax affairs, remains under your
control. If you send personal data through a repository service such as a
GitHub issue, that separate submission is processed under the service's terms;
contact us through the repository if you need help with data you submitted.

## Changes

Any change to this policy lands as a commit to this file in the public
repository, with its full history preserved in git.
