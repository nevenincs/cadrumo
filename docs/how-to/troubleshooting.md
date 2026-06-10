# Diagnose and repair your local setup

Every check on this page runs locally and the tool never submits anything to AEAT - building, validating, and exporting all happen on your machine. The only network step is the optional connectivity probe, which checks reachability and reads nothing. Find the error you see in the headings on this page and follow the steps under it. If your error is not listed, jump to [Prepare a privacy-safe support request](#prepare-a-privacy-safe-support-request).

## "This operation requires an active profile"

The command needs a taxpayer profile and none is active. Check what the tool thinks is active:

```bash
aeat config profile status
```

If a profile exists but the active setting won't load, repair it:

```bash
aeat config repair profile
```

If the active setting points at unreadable profile state, clear it and switch to a good profile:

```bash
aeat config repair profile --clear-active --yes
aeat config switch <profile-name>
```

If no profile exists yet, create one first - see [Set up your taxpayer profile](profile-setup.md).

If a profile loads but the numbers look wrong, see the next symptom.

## The numbers or facts look like someone else's

The wrong profile is active. Each profile keeps its own ledger, calculations, and filings, so a command run under the wrong one shows someone else's data. See which profile is active:

```bash
aeat config profile status
```

Switch to the right profile with `aeat config switch <profile-name>` - [Set up your taxpayer profile](profile-setup.md) covers creating and switching profiles.

## A calculation refuses because the ledger is not ready

The refusal looks like this:

```text
ledger preflight blocks modelo calculation: ... Run `aeat app ledger preflight --year <YEAR> --period <TOKEN>` before calculating
```

The calculation reads your imported transactions, and some rows aren't ready. Run the preflight check for the period you're calculating - the ledger preflight takes an AEAT token (`1T`-`4T`, `0A`, `01`-`12`) with `--year`:

```bash
aeat app ledger preflight --year 2026 --period 1T
aeat app ledger status
```

The preflight report names the rows that block the calculation. Fix them by completing the import and review steps in [Work with transactions](import-bank-statements.md), then run the calculation again.

## A required value is missing

The refusal names the missing item:

```text
Binding <id> has no supplied value
Required casilla <id> is not present in the calculation revision inputs
```

A casilla is a numbered box on the official form. A binding is a rule that fills one. List which values are still missing for your form:

```bash
aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing
```

Replace the modelo, year, and period with your own. The full workflow for supplying and reviewing values lives in [Review and supply calculation inputs](review-calculation-values.md).

## The period token is rejected

Use one period grammar everywhere: the AEAT tokens. `0A` is the annual period, `1T` through `4T` are the quarters, and `01` through `12` are the months. Every command takes the year separately with `--year`. [Filing periods](filing-periods.md) explains which form uses which period.

Modelo and ledger commands share the same shape - the AEAT token with `--year`:

```bash
aeat app ledger preflight --year 2026 --period 1T
aeat app ledger status --year 2026 --period 0A
aeat app ledger preflight --year 2026 --period 03
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
```

The ledger `--period` commands are `ledger preflight`, `ledger status`, `ledger export`, `ledger import`, and `overview status`. A bare token with no `--year` is refused with the year fix:

```text
Period token '1T' needs a year on this command. Add --year (e.g. --period 1T --year 2024).
```

A modelo token that is not valid for the form lists the accepted tokens:

```text
--period '<token>' is not a valid period token for modelo <modelo>. ... Valid tokens: ...
```

Calendar shapes such as `2026Q1`, `2026-03`, or `2026` are not accepted; use the AEAT token with `--year`.

## An export refuses because no verified calculation exists

Exports only work from a calculation that passed verification. Run the verification first - [Verify a draft filing](verification-reports.md) owns that workflow and explains what the report tells you.

## Recording a filing refuses because the filing window is not open

This refusal applies to `aeat app modelo work file` only - exporting works at any time. See [Upload your exported modelo at the AEAT portal](file-at-aeat.md) for the recording workflow and [Plan your filing calendar](filing-calendar.md) for when each window opens.

## Output appears in the wrong language

Add `--language` to the command. Accepted values are `en`, `es`, `ca`, and `hu`. The flag changes both command output and help text:

```bash
aeat --language en config profile create --help
```

To set the language for a whole shell session, set the environment variable `AEAT_OUTPUT_LANGUAGE` before running commands.

In PowerShell:

```powershell
$env:AEAT_OUTPUT_LANGUAGE = 'en'
```

In bash:

```bash
export AEAT_OUTPUT_LANGUAGE=en
```

The `--language` flag wins over the environment variable for that command. A profile also carries a default output language - set it with `--output-language` at profile creation, as described in [Set up your taxpayer profile](profile-setup.md).

## A live read from AEAT refuses

Live reads need a registered digital certificate or Cl@ve PIN (the digital identity system Spain uses for citizens to log in to government services online). Check your authentication:

```bash
aeat config auth status
aeat config auth test
```

`auth test` is a local probe - it checks your stored credentials without contacting AEAT. Check that the tool can reach the AEAT website (Sede Electrónica, the official online portal):

```bash
aeat config repair connectivity
```

If authentication was never set up, follow [Authenticate with AEAT](authenticate-with-aeat.md).

## The diagnostic toolbox

Use these when no single symptom matches, or to gather context before asking for help.

When you don't know where to start, check overall status:

```bash
aeat app overview status
aeat config profile status
```

`overview status` reports your profile, ledger, and modelo readiness; `profile status` reports the active profile. Together they tell you whether the problem is your setup or your data.

When a command fails and you want the details, read the logs:

```bash
aeat config repair logs --lines 50
```

It prints the log file path and the most recent lines. Use `--lines` to control how many it prints.

When a command reports corrupt or unreadable data, check integrity:

```bash
aeat config repair integrity objects
aeat config repair integrity registry
```

`integrity objects` checks the security seals on your encrypted records; `integrity registry` checks the tax rule definitions. If either fails, the report names the affected item. Take that report to the issue tracker rather than editing stored data by hand.

When nothing else recovers the problem, and only then, reset the saved progress of interrupted commands. This command is destructive:

```bash
aeat config repair reset-progress --yes
```

It removes the saved progress state for interrupted commands and requires `--yes`.

## Prepare a privacy-safe support request

When the steps on this page don't resolve the problem, gather this before asking for help:

- The exact command you ran.
- The error lines the command printed.
- The log path and the relevant recent lines from `aeat config repair logs`.
- Any report or work-unit IDs the output shows.

Remove personal data first: tax identifiers (NIF, CIF, DNI, NIE, NII), names, addresses, and file paths that embed your user name. Log lines can contain personal data - read them before pasting.

Take the request to the [project issue tracker](https://github.com/wgergely/aeat/issues).

If a term in an error message is unfamiliar, look it up in the [glossary](../glossary.md).

## Next steps

- [Quickstart: produce a modelo file](quickstart.md) - follow the first local filing path.
- [Set up your taxpayer profile](profile-setup.md) - create and switch profiles.
- [Authenticate with AEAT](authenticate-with-aeat.md) - check read-only live access setup.
- [Check AEAT notifications](check-aeat-notifications.md) - inspect saved DEHu notification snapshots.
- [Pipeline explanation](../explanation/index.md) - what the registry, secure storage, and workflow state are.
- [CLI reference](../cli/index.rst) - every repair command, flag, and exit code.
