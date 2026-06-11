# Verify a draft filing and act on the findings

Verification checks your saved calculation locally against the official form rules and saves a report of what it found. Nothing is sent to AEAT; everything happens on your computer. The order is always the same: calculate, then verify, then export or record the filing.

## Before you start

You need:

- An active profile. See [Set up your profile](profile-setup.md).
- A calculated draft for the filing you want to check. See the [quickstart](quickstart.md).

If you want to understand how filings and saved calculations fit together, read [the filing spine](filing-spine.md) first.

## Run verification

Run verification against the filing you want to check. Name the modelo, the year, and the period:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Period tokens are `0A` for annual, `1T` to `4T` for quarters, and `01` to `12` for months.

When the draft passes, the result shows `granted_verificado_completo` `true` and a `completeness_status` of `complete` - the saved calculation is now verified and ready to export.

When the draft does not pass, the result shows `granted_verificado_completo` `false` and a `completeness_status` of `incomplete` or `blocked`. The saved calculation stays a draft.

The command saves the verification report in both cases, so you can return to the findings later.

By default the command checks the current saved calculation, and it checks only drafts. To pick a different draft, use `--select latest-draft` or pass that calculation's revision ID directly. Use `--by` to record who ran the check.

## List your verification reports

Every verification run leaves a report. List them:

```bash
aeat app modelo verification-report list
```

To narrow the list to the reports for one saved calculation, add `--calculation-revision-id` with that calculation's ID.

## View a report and read the findings

Open one report by its ID:

```bash
aeat app modelo verification-report view <verification-report-id>
```

The report shows:

- The completeness status: `complete`, `incomplete`, or `blocked`.
- Whether the draft became verified (`granted_verificado_completo`).
- When the run happened and who ran it.
- How many casillas the calculation resolved.
- Which required casillas are still missing.
- The list of findings.

Each finding carries:

- A severity: **blocking** or **warning**.
- The affected casilla, where one applies.
- A message describing what the rule checked.
- A suggested next action.
- The legal references behind the rule.

Blocking findings prevent the draft from becoming verified, and export needs a verified calculation. Warnings do not block; read them, decide whether they apply to you, and move on.

## After any fix: re-run verification

After you change anything, run verification again:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Confirm the finding you addressed is gone from the new report. Repeat until the result shows `granted_verificado_completo` `true`. Each symptom section in this guide finishes with this re-run step.

## The report says incomplete

Incomplete means required casillas have no value yet. The report lists which ones under **missing required casillas**.

Enter a value for each missing casilla and recalculate:

```bash
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T --casilla <ID>=<VALUE>
```

Then [re-run verification](#after-any-fix-re-run-verification). For the full input workflow, including where values come from and how to check them, see [Review your calculation values](review-calculation-values.md).

## The report says blocked

Blocked means at least one blocking finding stands between your draft and a verified calculation. You cannot export the draft until you resolve every blocking finding.

Read each finding's suggested next action first; it tells you what the tool expects you to do. The common kinds of blocking finding:

- **A cross-field rule failed.** Two or more casillas disagree in a way the form rules do not allow. Check the values named in the finding against your records.
- **A value could not be derived.** The tool needed to compute a casilla but your data did not provide enough input. Supply the missing input or enter the value directly.
- **A prior-period record is missing.** This filing depends on a filing from an earlier period that is missing or unconfirmed. Record or confirm that earlier filing first.

After each fix, [re-run verification](#after-any-fix-re-run-verification).

## Export refuses because no verified calculation exists

Export needs a verified (or locally-filed) saved calculation. It refuses a plain draft with a message such as "current revision is still draft; verify it before exporting" or "no exportable verified or filed revision exists". Check where your filing stands:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
```

If the saved calculation is still a draft, verify it:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Once verification grants verified-complete, retry the export:

```bash
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

## More than one filing matches

When more than one filing or saved calculation matches the modelo, year, and period you named, the tool refuses to guess and prints the candidates instead.

List your filings with their work-unit IDs:

```bash
aeat app modelo work list
```

Then target the one you mean by passing its work-unit ID directly:

```bash
aeat app modelo work verify --work-unit-id <work-unit-id>
```

To confirm which filing a command touched, check its state and the actions taken on it:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
aeat app modelo work history --modelo 303 --year 2026 --period 1T
```

## The filing deadline has passed

Verification does not check filing deadlines. It still runs for a past period and can pass; the deadline gate applies later, when you record the filing with `work file`.

If the deadline has passed, file late through AEAT's own channels; consult AEAT or an advisor about any surcharges that may apply.

## Where to get help

If a report or an error message does not match what this guide describes, see [Diagnose and repair](troubleshooting.md). Unfamiliar terms are defined in the {doc}`glossary </_generated/glossary>`. Before you share command output to ask for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [File at AEAT](file-at-aeat.md): upload the exported file at the AEAT portal.
- [Review your calculation values](review-calculation-values.md): check and correct the inputs behind each casilla.
- [The filing spine](filing-spine.md): how filings, saved calculations, and reports fit together.
- [CLI reference](../cli/index.rst): every command and option.
