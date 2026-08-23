# Privacy policy

**Last updated: 12 July 2026**

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
  - when an AI assistant operates the toolkit, your chosen chat provider sees
    the conversation and the figures discussed in it — governed by that
    provider's terms, not by us.
  None of these paths route through infrastructure we operate, and none of
  them reports anything back to us.
- The software **never files taxes** and never writes to the AEAT.

## The website

- [cadrumo.neve.md](https://cadrumo.neve.md) is a static site. It has no
  accounts, no forms, no analytics, no advertising, no tracking pixels, and
  no fingerprinting. Every asset, including fonts, is served first-party from
  the same domain; visiting the site triggers no third-party requests.
- One functional first-party cookie, `cadrumo_lang`, is set **only if you
  explicitly pick a language**, stores that choice for up to one year, and is
  read by nothing but the site itself. Dismissing the privacy notice bar
  stores a similar flag (`cadrumo_notice_ack`) in your browser's
  localStorage. Under Article 22.2 of Spain's LSSI-CE and the AEPD's cookie
  guidance, such preference cookies set at the user's explicit request are
  exempt from prior consent; they are disclosed on the site's
  [legal page](https://cadrumo.neve.md/#/legal) regardless.
- The site is delivered from Amazon Web Services infrastructure (S3 and
  CloudFront). Our configuration enables **no access logging**: connection
  data such as your IP address is processed transiently by that
  infrastructure only as technically necessary to deliver the page, and we
  neither enable, receive, nor store access logs.

## GDPR position

Because neither the software nor the website transmits personal data to us,
we process no personal data within the meaning of Article 4(1) GDPR and hold
no records on which data-subject rights (Articles 15–22 GDPR) could operate.
Data processed locally by the software on your machine, for your own tax
affairs, is your household/business activity — you are the only controller of
it. If you believe we hold personal data about you despite the above (for
example, in a GitHub issue you filed), contact us through the repository and
we will respond.

## Changes

Any change to this policy lands as a commit to this file in the public
repository, with its full history preserved in git.
