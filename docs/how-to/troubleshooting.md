# Diagnose and repair your local setup

Every check on this page runs locally unless it explicitly says otherwise.
The optional connectivity probe opens the public AEAT Sede landing page and
checks reachability. It does not submit taxpayer data.

Find the error in the headings below and follow its steps. If it is not listed,
jump to [Prepare a privacy-safe support request](#prepare-a-privacy-safe-support-request).

Profile-scoped commands need an active taxpayer profile and may ask for that
profile's passphrase to unwrap its independent encryption key. See [Set up your
taxpayer profile](profile-setup.md) if you have none. Output can be English,
Spanish, Catalan, or Hungarian.

## "This operation requires an active profile"

The command needs a taxpayer profile and none is active. First inspect what
the tool thinks is active, then run the repair check without changing
anything. A healthy profile reports `ready`; a broken local pointer reports
the repair action you can take:

```{cli-sequence} troubleshooting-active-profile
:verify: Confirm the repair check reports the active profile's current status without changing it.
```

If the repair check says the active setting points at unreadable profile
state, clear that broken local pointer, then switch to a good profile:

```{cli-sequence} troubleshooting-clear-active
:verify: Confirm the profile list supplies the exact login name and the repair commands require real operator state.
```

The clear command is destructive repair and is appropriate only after the
inspection reports an unreadable active pointer. Login then asks for that
profile's passphrase; a headless caller must use an explicit machine secret
channel instead of placing the passphrase on the command line.

If no profile exists yet, create one first - see [Set up your taxpayer profile](profile-setup.md).

If a profile loads but the numbers look wrong, see the next symptom.

## The numbers or facts look like someone else's

The wrong profile is active. Each profile keeps its own ledger, calculations, and filings, so a command run under the wrong one shows someone else's data. See which profile is active:

```{cli-sequence} troubleshooting-wrong-profile
:verify: Confirm the active profile is the one you expect to be working under.
```

Log in to the right profile with `aeat config login <profile-name>` - [Set up your taxpayer profile](profile-setup.md) covers creating profiles and moving between them.

## A calculation refuses because the ledger is not ready

The refusal looks like this:

```text
ledger preflight blocks modelo calculation: transaction <id> <reason>: <detail>. Run `aeat app ledger preflight --period <TOKEN>` before calculating.
```

The calculation reads your imported transactions, and some rows aren't ready. Run the preflight check for the period you're calculating - `ledger preflight` takes an AEAT token (`1T`-`4T`, `0A`, `01`-`12`) and also requires `--year`, so add it even though the message above omits it:

```{cli-sequence} troubleshooting-ledger-ready
:verify: Confirm the ledger preflight and status run for the period you are calculating.
```

The preflight report names the rows that block the calculation. Fix them by completing the import and review steps in [Import and manage transactions](import-bank-statements.md), then run the calculation again.

## A required value is missing

The refusal names the missing item:

```text
Binding <id> has no supplied value
Required casilla <id> is not present in the calculation revision inputs
```

A casilla is a numbered box on the official form. A binding is a rule that fills one. List which values are still missing for your form:

```{cli-sequence} troubleshooting-missing-values
:verify: Confirm the tool lists the values still missing for the form.
```

Replace the modelo, year, and period with your own. The full workflow for supplying and reviewing values lives in [Review and supply calculation inputs](review-calculation-values.md).

## The period token is rejected

Use one period grammar everywhere: the AEAT tokens. `0A` is the annual period, `1T` through `4T` are the quarters, and `01` through `12` are the months. Every command takes the year separately with `--year`. [Period tokens and dates](filing-calendar.md#period-tokens-and-dates) explains which form uses which period.

Modelo and ledger commands share the same shape - the AEAT token with `--year`:

```{cli-sequence} troubleshooting-period-grammar
:verify: Confirm the AEAT token plus --year is accepted across ledger and modelo commands.
```

The ledger `--period` commands are `ledger preflight`, `ledger status`,
`ledger export`, `ledger import`, and `overview status`. Where the year is
optional, a bare period token is refused with a correction:

```text
El token de periodo '1T' necesita un año en este comando. Añada --year (e.g. --period 1T --year 2024).
```

On `ledger preflight` and `ledger export`, `--year` is a required option, so omitting it is refused before the token is read:

```text
Missing option '--year'.
```

A modelo token that is not valid for the form lists the accepted tokens:

```text
--period '<token>' is not a valid period token for modelo <modelo>. ... Valid tokens: ...
```

Calendar shapes such as `2026Q1`, `2026-03`, or `2026` are not accepted; use the AEAT token with `--year`.

## An export refuses because no verified calculation exists

Exports only work from a calculation that passed verification. Run the verification first - [Verify a draft filing](verification-reports.md) owns that workflow and explains what the report tells you.

## Recording a filing refuses because the filing window is not open

This refusal applies to `aeat app modelo work file` only - exporting works at any time. See [File your modelo at the AEAT portal](file-at-aeat.md) for the recording workflow and [Plan your filing calendar](filing-calendar.md) for when each window opens.

## Output appears in the wrong language

Add `--language` to the command. Accepted values are `en`, `es`, `ca`, and `hu`. The flag changes both command output and help text:

```{cli-sequence} troubleshooting-language
:verify: Confirm the --language flag renders a command's output in the chosen language.
```

The `--language` flag applies to that one command. A profile also carries
a default output language - set it with `--output-language` at profile
creation, as described in [Set up your taxpayer profile](profile-setup.md).

## A live read from AEAT refuses

Live reads need a registered digital certificate, Cl@ve Móvil, or Cl@ve
Permanente. Check your authentication:

```{cli-sequence} troubleshooting-auth-check
:verify: Confirm the tool reports what authentication is configured and probes it locally.
```

`auth test` checks stored credentials without contacting AEAT. An expired
certificate, or one within the 14-day critical window, blocks authenticated
work. The earlier 60-day warning is advisory. If expiry is close, follow
[Renew your certificate before it expires](authenticate-with-aeat.md#renew-your-certificate-before-it-expires).

Check that the tool can reach the AEAT website:

```{cli-sequence} troubleshooting-connectivity
```

If authentication was never set up, follow [Authenticate with AEAT](authenticate-with-aeat.md).

When a live login fails, the tool captures an encrypted diagnostic of the failure. List and inspect them:

```{cli-sequence} troubleshooting-auth-diagnostics
:verify: Confirm the tool lists saved login diagnostics.
```

`list` shows when each failure happened, the reason, and which login method and profile were involved. `show` prints one diagnostic with sensitive content redacted. Configured credentials appear only as present/absent flags and fingerprints, never as values.

For Cl@ve failures, the missing piece is often what happened on your phone, something the tool cannot see. Record what you observed so the diagnostic is complete:

```{cli-sequence} troubleshooting-diagnostics-report
```

Accepted states are `app_prompted_and_accepted`, `app_prompted_not_accepted`, `app_did_not_prompt`, and `operator_did_not_check`.

## The diagnostic toolbox

Use these when no single symptom matches, or before asking for help. Run the
read-only diagnostics in order: overall status, active profile, recent logs,
and both integrity checks.

```{cli-sequence} troubleshooting-toolbox
:verify: Confirm the read-only diagnostics all run and report on your setup and data.
```

`overview status` reports your profile, ledger, and modelo readiness; `profile status` reports the active profile. Together they tell you whether the problem is your setup or your data. `repair logs` prints the log file path and the most recent lines. Use `--lines` to control how many. `integrity objects` checks the security seals on your encrypted records, and `integrity registry` checks the tax rule definitions. If either fails, the report names the affected item. Take that report to the issue tracker rather than editing stored data by hand.

When unreadable encrypted records block other commands, move them aside. Preview first, then apply:

```{cli-sequence} troubleshooting-quarantine
:verify: Confirm the quarantine preview and the real run both complete.
```

The preview lists how many records would move, per storage area, without changing anything. The real run requires `--yes`. Quarantine does not delete anything: each unreadable record is moved, still encrypted, into a quarantine archive inside the same storage, and readable records are untouched. If the cause was a missing key that you later restore, the archived records still exist. See [Protect access to your data](protect-data-access.md).

To find which finalized calculations and filings used a transaction, query the
participation index. Rebuild it first if the lookup appears incomplete:

```{cli-sequence} troubleshooting-participation
:verify: Confirm the participation index rebuilds from the finalized records.
```

The index is a derived cross-reference, safe to regenerate at any time: `rebuild` rescans the finalized calculation records and rewrites it. Run it if a participation lookup looks incomplete. Rebuilding changes no ledger or filing data.

Both `participation` verbs read the active profile's encrypted bucket, so they need an unlocked profile session. If either refuses with `No hay una sesion de bucket activa`, log in to the profile first with `aeat config login <profile-name>`.

When nothing else recovers the problem, and only then, clear the saved progress of interrupted commands. This command is destructive:

```{cli-sequence} troubleshooting-reset-progress
:verify: Confirm the saved interrupted-command progress is cleared for the unlocked profile.
```

It removes saved interrupted-command progress and requires `--yes`. Like the participation verbs, it reads the active profile's bucket, so switch to the profile first if it refuses with `No hay una sesion de bucket activa`.

(prepare-a-privacy-safe-support-request)=
## Prepare a privacy-safe support request

When the steps on this page don't resolve the problem, gather this before asking for help:

- The exact command you ran.
- The error lines the command printed.
- The log path and the relevant recent lines from `aeat config repair logs`.
- Any report or work-unit IDs the output shows.

Remove personal data first: tax identifiers (NIF, CIF, DNI, NIE, NII), names, addresses, and file paths that embed your user name. Log lines can contain personal data - read them before pasting.

Take the request to the [project issue tracker](https://github.com/nevenincs/cadrumo/issues).

If a term in an error message is unfamiliar, look it up in the {doc}`glossary </_generated/glossary>`.

## Next steps

- [Quickstart: produce a modelo file](quickstart.md) - follow the first local filing path.
- [Set up your taxpayer profile](profile-setup.md) - create and switch profiles.
- [Authenticate with AEAT](authenticate-with-aeat.md) - check read-only live access setup.
- [Check AEAT notifications](check-aeat-notifications.md) - inspect saved DEHu notification snapshots.
- [Pipeline explanation](../explanation/index.md) - what the registry, secure storage, and workflow state are.
- [CLI reference](../cli/index.rst) - every repair command, flag, and exit code.
