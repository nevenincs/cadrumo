# Read live AEAT data

When you configure authentication, `aeat` can read your data from the Agencia
Estatal de Administración Tributaria (AEAT). It never writes, files, or submits
anything. Every live command is a read that saves a local copy for you to review.
You remain the only one who files. To understand that boundary, see
[Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md).

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- configured AEAT authentication for read access; see
  [Authenticate with AEAT](authenticate-with-aeat.md)

Authentication grants read access only. It does not let `aeat` submit filings;
you upload your filings yourself at the AEAT portal. See
[Upload your exported modelo at the AEAT portal](file-at-aeat.md).

## What you can read

Each source has its own guide with the exact commands:

- Census (*censo*) facts for your profile - see
  [Link Modelo 036 census information](censo-update.md).
- Official notifications, your declaration history, filed returns, and the IVA
  (Value Added Tax) compensation balance - see
  [Check AEAT notifications and live observations](check-aeat-notifications.md).
- Filing receipts (*justificante*) for periods you filed - see
  [Pull and keep your filing receipts](justificante-receipts.md).

## How a live read works

Every live read works the same way. It uses your configured authentication,
reads from the AEAT sede read-only, and saves an encrypted local copy in your
profile. It applies nothing automatically.

For example, pull your censo into a local snapshot:

```bash
aeat config profile censo pull
```

This reads your censo from AEAT and saves a snapshot. It changes nothing in your
profile until you review and apply it.

The `aeat app live` command group collects the read-only commands, such as
`aeat app live justificante pull`, `aeat app live notifications pull`, and
`aeat app live filed pull`. Run `aeat app live --help` to see them, or follow the
per-surface guides for each one.

## Downloaded facts change only your local records

Reading is separate from applying. A pull saves a local copy; applying a
downloaded fact updates only your local profile or records, and only after you
review it. For example, `aeat config profile censo apply` writes the reviewed
censo facts into your local profile. Nothing is sent back to AEAT.

## You don't set the live-tests variable

`AEAT_LIVE_TESTS_ENABLED` is a developer setting. It gates the project's own live
integration test suite and has no role in normal use. Do not set it to use live
reads. A live read in your shell needs only configured authentication and an
active profile.

## If a live read fails

A live read needs configured authentication and a current session. If a read
reports that authentication is missing or the session expired, re-check it with
[Authenticate with AEAT](authenticate-with-aeat.md), then see
[Diagnose and repair your local setup](troubleshooting.md). When the
troubleshooting steps don't resolve it, follow the privacy-safe support request
on that page before you take the issue to the project's issue tracker.

## Next steps

- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Link Modelo 036 census information](censo-update.md)
- [Check AEAT notifications and live observations](check-aeat-notifications.md)
- [Pull and keep your filing receipts](justificante-receipts.md)
- [Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md)
- [CLI reference](../cli/index.rst)
