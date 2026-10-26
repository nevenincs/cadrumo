# Terms of service

**Last updated: 5 October 2026**

These terms cover your use of Cadrumo: the `aeat` command-line program, the
other programs installed with it, and the optional sign-in with Google that
Cadrumo offers.

**Publisher:** Neve Nincs ("we"), the legal entity behind
[neve.md](https://neve.md) and the publisher of the Cadrumo project. Contact:
<hello@neve.md> or the
[issue tracker](https://github.com/nevenincs/cadrumo/issues).

By using Cadrumo you accept these terms. If you do not accept them, do not use
it.

## Cadrumo is licensed software, not a hosted service

Cadrumo is open-source software under the [Apache License 2.0](LICENSE). That
licence sets out your rights to use, copy, modify, and distribute it. These
terms add to the licence and do not take away any right it gives you. Where
the two disagree about the software itself, the licence prevails.

Cadrumo runs on your own computer. We do not host it for you, hold an account
for you, or store your data. There is no subscription and no fee. The
[privacy policy](PRIVACY.md) describes how Cadrumo handles data.

## Cadrumo is not advice and does not file

Cadrumo is a software utility, not a tax advisor. It gives no tax, legal,
accounting, or financial advice and creates no advisory relationship. It is
not affiliated with, endorsed by, or connected to the Agencia Estatal de
Administración Tributaria (AEAT).

No calculation, draft, check, or export guarantees that a figure, form, or
filing is correct, complete, or compliant with current law. Cadrumo never
submits a declaration to the AEAT. You file your own declarations through the
AEAT's official channels. See the [full disclaimer](docs/disclaimer.md).

## What you are responsible for

- The accuracy, completeness, and legality of every figure you enter and every
  declaration you file.
- Reviewing every output before you rely on it, and consulting a qualified
  professional where your situation calls for one.
- Keeping your passphrase, certificates, and other access details safe. If you
  lose your passphrase and have no recovery code, nobody can recover your
  encrypted data, including us.
- Using Cadrumo only for data you are entitled to process, and in line with
  the law that applies to you.

## Services run by others

Some features connect to services we do not operate. You use each of them
under that provider's own terms, with your own account or access details:

- the AEAT's portals, for read-only access to your own tax records;
- Google, for the optional workbooks and the encrypted copy of your profile's
  records in your Google Drive;
- a hosted AI provider, if you choose to configure one.

We are not responsible for those services, their availability, or what they do
with data you send them.

### Sign in with Google

Signing in with Google is optional. When you do, Cadrumo asks Google for two
things: your account's email address, and permission to create files in your
Google Drive and manage the files it created. It does not ask for access to
your other files. The
[privacy policy](PRIVACY.md#google-sign-in-and-google-user-data) describes
what happens to that information.

Signing out with `aeat config google logout` removes the sign-in from your
computer. It does not withdraw the permission at Google; you can do that at
any time in your Google Account. Files Cadrumo created in your Google Drive
remain yours. Signing out deletes nothing there. Cadrumo changes or removes
its own files only while it runs an export or a copy that you started.

Sign-in depends on Google, and Google can limit, suspend, or end it. We can
also switch sign-in off for everyone, because it is registered with Google
under a project we operate, for example to protect users if that registration
is misused. We cannot see or switch off an individual account. If sign-in is
unavailable, the features that use Google stop and the rest of Cadrumo keeps
working on your computer.

## No warranty

Cadrumo is provided "as is", without warranty of any kind, express or implied,
as set out in the Apache License 2.0. We do not promise that it is free of
errors, that it reflects current law, or that any connected service will be
available.

## Liability

To the extent the law allows, we and the contributors accept no liability for
any loss, penalty, interest, or other damage arising from the use of Cadrumo.
The Apache License 2.0 sets out the same limit. Nothing in these terms limits
a right you have under law that cannot be waived by agreement.

## Changes

We publish every change to these terms in Cadrumo's public source repository,
where the full history stays visible. The "Last updated" date shows the latest
change.
