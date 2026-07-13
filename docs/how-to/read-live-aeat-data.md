# Read live AEAT data

When you configure authentication, Cadrumo's `cadrumo` command can read your data
from the Agencia Estatal de Administración Tributaria (AEAT). Cadrumo never
writes, files, or submits anything. Every live command is a read that saves a
local copy for you to review. You remain the only one who files. To understand
that boundary, see
[Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md).

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- configured AEAT authentication for read access; see
  [Authenticate with AEAT](authenticate-with-aeat.md)

Authentication grants read access only. It does not let Cadrumo submit filings;
you upload your filings yourself at the AEAT portal. See
[Upload your exported modelo at the AEAT portal](file-at-aeat.md).

## What you can read

Each source has its own guide with the exact commands:

- Official notifications, your declaration history, filed returns, and the IVA
  (Value Added Tax) compensation balance - see
  [Check AEAT notifications and live observations](check-aeat-notifications.md).
- Filing receipts (*justificante*) for periods you filed - see
  [Pull and keep your filing receipts](justificante-receipts.md).

## How a live read works

Every live read works the same way. It uses your configured authentication,
reads from the AEAT sede read-only, and saves an encrypted local copy in your
profile. It applies nothing automatically.

The `cadrumo app live` command group collects the read-only commands. Each one
takes the arguments that scope the read. For example:

- `cadrumo app live justificante pull --modelo 303 --year 2026 --period 1T` — all
  three of `--modelo`, `--year`, and `--period` are required.
- `cadrumo app live filed pull --modelo 303 --year 2026` — `--year` is required;
  add `--period` to narrow to one period, or use `--from-year`/`--to-year` for a
  range.
- `cadrumo app live notifications pull` — needs no scope arguments.

Run `cadrumo app live --help` to see the full set, or follow the per-surface guides
for each one.

## Downloaded facts change only your local records

Reading is separate from applying. A pull saves a local copy; applying a
downloaded fact updates only your local profile or records, and only after you
review it. Nothing is sent back to AEAT.

Census (*censo*) facts are not a live read: AEAT publishes no read-only census
view, so you enter census facts by hand - see
[Maintain Modelo 036 census facts in your profile](censo-update.md).

## You don't set the live-tests variable

`CADRUMO_LIVE_TESTS_ENABLED` is a developer setting. It gates the project's own live
integration test suite and has no role in normal use. Do not set it to use live
reads. A live read in your shell needs only configured authentication and an
active profile.

## If a live read fails

A live read needs configured authentication and a current session. Before it
contacts AEAT it runs an authentication preflight. If you have not configured a
provider yet, the read refuses at that preflight. The refusal text mentions a
Cl@ve identity check, but the underlying cause is that authentication is not
configured (the preflight reports `auth_configured=False`). Configure a provider
first; see [Authenticate with AEAT](authenticate-with-aeat.md).

The `cadrumo` command prints its messages in Spanish. A typical refusal reads `Refused. La
identidad de Cl@ve Móvil no coincide...` followed by a `-> Run` next step.

If a read reports that the session expired, re-check authentication with
[Authenticate with AEAT](authenticate-with-aeat.md), then see
[Diagnose and repair your local setup](troubleshooting.md). When the
troubleshooting steps don't resolve it, follow the privacy-safe support request
on that page before you take the issue to the project's issue tracker.

## Next steps

- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Maintain Modelo 036 census facts in your profile](censo-update.md)
- [Check AEAT notifications and live observations](check-aeat-notifications.md)
- [Pull and keep your filing receipts](justificante-receipts.md)
- [Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md)
- [CLI reference](../cli/index.rst)
