# Diagnose and repair your local setup

Every check on this page runs locally unless it explicitly says otherwise.
The optional connectivity probe opens the public Sede landing page of the
Agencia Estatal de Administración Tributaria (AEAT) and checks reachability. It
does not submit taxpayer data.

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

If no profile exists yet, create one first; see [Set up your taxpayer
profile](profile-setup.md).

If a profile loads but the numbers look wrong, see the next symptom.

## The numbers or facts look like someone else's

The wrong profile is active. Each profile keeps its own records, calculations,
and filings, so a command run under the wrong one shows someone else's data. See
which profile is active:

```{cli-sequence} troubleshooting-wrong-profile
:verify: Confirm the active profile is the one you expect to be working under.
```

Log in to the right profile with `aeat config login <profile-name>`. [Set up
your taxpayer profile](profile-setup.md) covers creating profiles and moving
between them.

(a-calculation-refuses-because-the-ledger-is-not-ready)=
## A calculation refuses because your records are not ready

The refusal looks like this:

```text
ledger preflight blocks modelo calculation: transaction <id> <reason>: <detail>. Run the ledger preflight for period <period> and resolve its findings before calculating.
```

The calculation reads your imported transactions, and some rows aren't ready. Run the preflight check for the period you're calculating - `ledger preflight` takes an AEAT period code (`1T`-`4T`, `0A`, `01`-`12`) and also requires `--year`:

```{cli-sequence} troubleshooting-ledger-ready
:verify: Confirm the check of your records and status run for the period you are calculating.
```

The preflight report names the rows that block the calculation. Fix them by completing the import and review steps in [Import and manage transactions](import-bank-statements.md), then run the calculation again.

## A required value is missing

The refusal or the issue from the check names the missing item:

```text
Binding <id> has no supplied value.
Required casilla <id> carries no value.
```

A box (casilla) is a numbered field on the official form. In the message, `Binding` is the rule that fills a box. List which values are still missing for your form:

```{cli-sequence} troubleshooting-missing-values
:verify: Confirm the tool lists the values still missing for the form.
```

Replace the modelo, year, and period with your own. The full workflow for supplying and reviewing values lives in [Review and supply calculation inputs](review-calculation-values.md).

(the-period-token-is-rejected)=
## The period code is rejected

Use one period grammar everywhere: the AEAT period codes. `0A` is the annual period, `1T` through `4T` are the quarters, and `01` through `12` are the months. Every command takes the year separately with `--year`. {ref}`Period codes and dates <period-tokens-and-dates>` explains which form uses which period.

Modelo and `ledger` commands share the same shape: the AEAT period code with `--year`:

```{cli-sequence} troubleshooting-period-grammar
:verify: Confirm the AEAT token plus --year is accepted across records and modelo commands.
```

The `ledger` commands that take `--period` are `ledger preflight`, `ledger
status`, `ledger export`, `ledger import`, and `overview status`. Where the year
is optional, a bare period code is refused with a correction:

```text
Period token '1T' needs a year on this command. Add --year (e.g. --period 1T --year 2024).
```

On `ledger preflight`, `overview pipeline`, and `overview prepare`, `--year` is a required option, so omitting it is refused before the token is read:

```text
Missing option '--year'.
```

A modelo token that is not valid for the form lists the accepted tokens:

```text
--period '<token>' is not a valid period token for modelo <modelo>. ... Valid tokens: ...
```

Calendar shapes such as `2026Q1`, `2026-03`, or `2026` are not accepted; use the AEAT period code with `--year`.

(an-export-refuses-because-no-verified-calculation-exists)=
## An export refuses because no checked calculation exists

Exports only work from a calculation that passed the check. Run the check first: [Check a draft declaration and act on the issues](verification-reports.md) owns that workflow and explains what the report tells you. The refusal reads `No calculation revision matched the requested selector`, or `The selected calculation revision is not in a usable state for this operation` when the current calculation is still a draft.

## An export refuses the output path

A local export refuses to overwrite an existing file unless you add `--replace`. It also refuses an `--output` path whose parent directory does not exist. This applies to `aeat app modelo export`, `aeat app modelo spreadsheet export`, and `aeat app modelo work report`. The message reads `The export output path is not valid` and ends with the reason, such as `path is an existing file` or `parent directory does not exist`. Add `--replace`, or create the folder first.

## Recording a filing refuses because the filing window is not open

This refusal applies to `aeat app modelo work file` only - exporting works at any time, and the refusal message names `aeat app modelo export` as the local finish line. See [File your modelo at the AEAT portal](file-at-aeat.md) for the recording workflow and [Plan your filing calendar](filing-calendar.md) for when each window opens.

## Output appears in the wrong language

`aeat` prints its messages in Spanish unless you choose another language. Add `--language` straight after `aeat`. Accepted values are `en`, `es`, `ca`, and `hu`. The flag changes both command output and help text:

```{cli-sequence} troubleshooting-language
:verify: Confirm the --language flag renders a command's output in the chosen language.
```

The `--language` flag applies to that one command. Without it, the
`CADRUMO_OUTPUT_LANGUAGE` environment variable applies, then the default output
language stored on your profile. Set the profile default with
`aeat config profile edit --output-language en`, as described in [Set up your
taxpayer profile](profile-setup.md). The examples in this documentation are
recorded in English.

## A live read from AEAT refuses

Live reads need a registered digital certificate, Cl@ve Móvil, or Cl@ve
Permanente. Check your authentication:

```{cli-sequence} troubleshooting-auth-check
:verify: Confirm the tool reports what authentication is configured and probes it locally.
```

`auth test` checks stored credentials without contacting AEAT. By default, an
expired certificate, or one within the 14-day critical window, blocks
authenticated work. The earlier 60-day warning is advisory. If expiry is close,
follow
[Renew your certificate before it expires](authenticate-with-aeat.md#renew-your-certificate-before-it-expires).

Check that the tool can reach the AEAT website:

```{cli-sequence} troubleshooting-connectivity
```

If authentication was never set up, follow [Authenticate with AEAT](authenticate-with-aeat.md).

When a live login fails, the tool captures an encrypted diagnostic of the failure. List and inspect them:

```{cli-sequence} troubleshooting-auth-diagnostics
:verify: Confirm the tool lists saved login diagnostics.
```

`list` shows when each failure happened, the reason, and which login method and profile were involved. `view` prints one diagnostic with sensitive content redacted. Configured credentials appear only as present/absent flags and fingerprints, never as values.

For Cl@ve failures, the missing piece is often what happened on your phone, something the tool cannot see. Record what you observed so the diagnostic is complete:

```{cli-sequence} troubleshooting-diagnostics-report
```

Accepted states are `app_prompted_and_accepted`, `app_prompted_not_accepted`, `app_did_not_prompt`, and `operator_did_not_check`.

## The diagnostic toolbox

Use these when no single symptom matches, or before asking for help. Run the
read-only diagnostics in order: overall status, active profile, recent logs,
the full local report, and the secure-object integrity check.

```{cli-sequence} troubleshooting-toolbox
:verify: Confirm the read-only diagnostics all run and report on your setup and data.
```

`overview status` reports your profile, records, and modelo readiness; `profile status` reports the active profile. Together they tell you whether the problem is your setup or your data. `repair logs` prints the log file path and the most recent lines. Use `--lines` to control how many. `integrity objects` checks the security seals on your encrypted records. `aeat config repair` with no subcommand prints the full local report: package and Python versions, profile and authentication state, the tax rule definitions, and the same secure-object check. If a check fails, the report names the affected item. Take that report to the issue tracker rather than editing stored data by hand.

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

The index is a derived cross-reference, safe to regenerate at any time:
`rebuild` rescans the finalized calculation records and rewrites it. Run it if a
participation lookup looks incomplete. Rebuilding changes no records or filing
data.

Both `participation` verbs read the active profile's encrypted storage, so they need an unlocked profile session. If either refuses because the profile is locked or none is active, log in to the profile first with `aeat config login <profile-name>`.

When nothing else recovers the problem, and only then, clear the saved progress of interrupted commands. This command is destructive:

```{cli-sequence} troubleshooting-reset-progress
:verify: Confirm the saved interrupted-command progress is cleared for the unlocked profile.
```

It removes saved interrupted-command progress and requires `--yes`. Like the participation verbs, it reads the active profile's storage, so log in to the profile first if it refuses because the profile is locked or none is active.

(prepare-a-privacy-safe-support-request)=
## Prepare a privacy-safe support request

When the steps on this page don't resolve the problem, gather this before asking for help:

- The exact command you ran.
- The error lines the command printed.
- The log path and the relevant recent lines from `aeat config repair logs`.
- Any report or declaration IDs the output shows.

Remove personal data first: tax identifiers (NIF, CIF, DNI, NIE, NII), names,
addresses, and file paths that embed your user name. Log lines can contain
personal data. Read them before pasting.

Take the request to the [project issue tracker](https://github.com/nevenincs/cadrumo/issues).

If a term in an error message is unfamiliar, look it up in the {doc}`glossary </_generated/glossary>`.

## Next steps

- [Quickstart: prepare a modelo filing](quickstart.md): follow the first local filing path.
- [Set up your taxpayer profile](profile-setup.md): create and switch profiles.
- [Authenticate with AEAT](authenticate-with-aeat.md): check read-only live
  access setup.
- [Read AEAT notifications](check-aeat-notifications.md): inspect saved DEHú notification snapshots.
- [How Cadrumo turns your records into a tax file](../explanation/index.md): what the tax rules, secure storage, and workflow state are.
- [CLI reference](../cli/index.rst): every repair command, flag, and exit code.
