(verify-a-draft-filing-and-act-on-the-findings)=
# Check a draft declaration and act on the issues

This page covers the check of a draft declaration: running the check,
reading the saved report, and acting on each kind of issue. The check tests
your saved calculation locally against the official form rules and saves a
report of what it found. Nothing is sent to the Agencia Estatal de
Administración Tributaria (AEAT); everything happens on your computer. The
order is always the same: calculate, then check, then
record the filing.

The check asks three things: does every required box have a value; do the sums add
up consistently, with no box contradicting another; and does anything block the
form from being treated as complete. It also checks conditions outside the draft
itself: that any earlier period this form builds on is recorded as filed or backed
by an AEAT receipt, that the running VAT balance carried between periods adds up,
and that every carried-forward figure still points at the calculation it was filed
under.

A passed check is a local check. Treat it as "my draft is complete and
consistent", never as "I have filed" or "I am on time". Checking is **not** the
agency accepting your filing (the tool never contacts AEAT), **not** a guarantee
the upload will succeed (submission happens separately, outside the tool), and
**not** a deadline check (a draft can pass long after the deadline; see [the
deadline section](#the-filing-deadline-has-passed)).

## Before you start

**Requirement:** an active taxpayer profile with a name and surnames, and a
calculated draft to check. Create a profile with `aeat config profile create`,
supplying the name, surnames, and an activity-start date. The activity-start date
matters for a first filing: it tells Cadrumo not to require a prior period you
never filed, so the check can pass. See [Set up your profile](profile-setup.md).

You also need your passphrase (Cadrumo prompts for it). For a
first-period Modelo 303, record some business activity in your records, then
create and calculate the draft. The example in [Run the check](#run-verification)
starts from a profile and records that already hold business activity.

If you want to understand how filings and saved calculations fit together,
read [The filing workflow](filing-spine.md) first.

(run-verification)=
## Run the check

Create the draft, calculate it, check it, and open the saved report. The check
saves a report whether or not the draft passes, and `verification-report view`
reopens it by id:

```{cli-sequence} verification-reports-modelo-303
:verify: Confirm the check report shows the draft is complete.
```

Period codes are `0A` for annual, `1T` to `4T` for quarters, and `01` to `12`
for months - see {ref}`Period codes and dates <period-tokens-and-dates>`.

With this profile and draft, the first-period Modelo 303 passes: the report
reads `granted_verificado_completo` `true` and a `completeness_status` of
`complete` - the saved calculation is now checked and ready to file. The report
still lists two `warning` issues, which do not block. One notes that an earlier
period is scoped out by the activity-start date. The other notes an output
transaction with no supporting document.

When the draft does not pass, the report reads `granted_verificado_completo`
`false` and a `completeness_status` of `incomplete` or `blocked`, and the saved
calculation stays a draft. The command saves the report in both cases, so you can
return to the issues later.

By default `work verify` checks the current saved calculation, and it checks only
drafts. To pick a different draft, use `--select latest-draft` or pass that
calculation's ID directly. Use `--by` to record who ran the check.

(list-your-verification-reports)=
## List your check reports

Every check leaves a report. List them with `aeat app modelo verification-report
list`.

To narrow the list to the reports for one saved calculation, add
`--calculation-revision-id` with that calculation's ID.

(view-a-report-and-read-the-findings)=
## View a report and read the issues

Open one report by its ID with `aeat app modelo verification-report view
<verification-report-id>` (the sequence in [Run the check](#run-verification)
did exactly this on the report it had just produced).

The report shows:

- The completeness status: `complete`, `incomplete`, or `blocked`.
- Whether the draft passed the check (`granted_verificado_completo`).
- When the run happened and who ran it.
- The boxes the calculation filled in (`resolved_casilla_ids`).
- Which required boxes are still missing (`missing_required_casilla_ids`).
- The list of issues.

Each issue carries:

- A severity: **blocking** or **warning**.
- A kind: `missing_required_casilla`, `reconciliation_mismatch`,
  `cross_period_dependency_unclean`, `blocking_rule`, or `advisory`.
- The affected box, where one applies.
- A message describing what the rule checked.
- A suggested next action, where one applies.
- The legal references behind the rule.

For the legal references in machine-readable form, render the report as JSON.
`--format json` is a global flag, so it goes before the command. The example in
[Run the check](#run-verification) does exactly this: its last step is the JSON
`verification-report view` of the report it just produced.

Each issue in the JSON output carries at least one entry in `legal_refs` - a
cross-period dependency, for example, cites the law behind the prior-filing
carry. It also carries `source_refs`, which name the official form or
instruction and can be empty.

Blocking issues prevent the draft from passing the check, and recording the
filing needs a checked calculation. Warnings do not block; read them, decide whether they
apply to you, and move on.

(after-any-fix-re-run-verification)=
## After any fix: run the check again

After you change anything, run `aeat app modelo work verify` again for the same
target, exactly as the example in [Run the check](#run-verification) does. That
example addresses the draft by its id; passing `--modelo`, `--year`, and
`--period` instead re-runs the check against the current draft for that target.

Confirm the issue you addressed is gone from the new report. Repeat until the
result shows `granted_verificado_completo` `true`. Each symptom section in this
guide finishes with this re-run step.

## The report says incomplete

Incomplete means required boxes have no value yet. The report lists which ones
under **missing required boxes**.

For example, a Modelo 349 draft calculated before any intra-community invoice is
recorded has no counterparty record, so the boxes each record needs are empty:
country code, EU VAT number, name, operation key, and base. The check still saves
the report, but it exits with status 1 and reads `completeness_status`
`incomplete` and `granted_verificado_completo` `false`, with the empty boxes under
`missing_required_casilla_ids`:

```{cli-sequence} verification-reports-incomplete-report
:verify: Confirm the report reads incomplete and names the empty required boxes.
```

Those boxes come from your invoices, so record the intra-community invoices and
recalculate rather than typing the values in. See [Prepare a Modelo 349
recapitulative declaration](modelo-349.md).

`--casilla` works only on boxes whose input kind is `manual`. A box filled from
your records or another source is `bound`, and `--casilla` refuses it with `cannot
override bucket-derived source-bound casillas`. Fix the source for those. See
[Review your calculation values](review-calculation-values.md). Check which kind a
box is, then supply the value for a manual one and recalculate. The example
supplies box 44, the prorrata regularisation, and the recalculation carries it
into the deductible total:

```{cli-sequence} verification-reports-incomplete
:verify: Confirm the supplied manual value reaches the recalculated deductible total.
```

Then [run the check again](#after-any-fix-re-run-verification). For the full input
workflow, including where values come from and how to check them, see [Review your
calculation values](review-calculation-values.md).

## The report says blocked

Blocked means at least one blocking issue stands between your draft and a checked
calculation. You cannot record the filing until you resolve every blocking issue.

Read each issue's suggested next action first; it tells you what the tool expects
you to do. The common kinds of blocking issue:

- **A cross-field rule failed.** Two or more boxes disagree in a way the form
  rules do not allow. Check the values named in the issue against your records.
- **A value could not be derived.** The tool needed to calculate a box but your
  data did not provide enough input. Supply the missing input or enter the value
  directly.
- **Your records changed after you calculated.** The check compares the saved
  calculation with your records as they are now. If you reclassify, correct, or
  remove an entry after calculating, a blocking issue says your records changed
  and asks you to calculate again. The example records a sale, calculates,
  corrects the sale's price, then checks without calculating again. The check
  saves the report, exits with status 1, and reads `completeness_status` `blocked`
  and `granted_verificado_completo` `false`:

  ```{cli-sequence} verification-reports-blocked
  :verify: Confirm the report reads blocked and carries a blocking finding.
  ```

  Calculate the draft again so the saved figures match your records.
- **A prior-period record is missing.** This filing depends on a filing from an
  earlier period that is missing or unconfirmed. Record or confirm that earlier
  filing first. If you had no obligation in that earlier period because you had
  not started your activity yet, set your activity-start date on the profile so
  the dependency is scoped out. Without a profile name, the edit applies to
  the active profile:

  ```{cli-sequence} verification-reports-scope-dependency
  :verify: Confirm setting the activity-start date on the profile succeeds.
  ```

After each fix, [run the check again](#after-any-fix-re-run-verification).

## Export refuses

Export refuses a plain draft. When the current calculation is a draft, the
message reads `The selected calculation revision is not in a usable state for
this operation`. When no calculation has passed the check or been recorded as
filed, it reads `No calculation revision matched the requested selector`. Check
the draft first, as in [After any fix: run the check again](#after-any-fix-re-run-verification).

Export also refuses an `--output` path that already exists, unless you add
`--replace`, and a path whose parent directory does not exist.

A draft that passed the check as complete is what export requires. The Modelo 303
file it writes carries Cadrumo's all-zero development software identity, which
AEAT does not accept for presentation. Check where the filing stands, then read
the checked figures back and enter them at the AEAT portal:

```{cli-sequence} verification-reports-export-check
:verify: Confirm the checked calculation exports with the development identity.
```

## More than one filing matches

When more than one filing or saved calculation matches the modelo, year, and
period you named, the tool refuses to guess and prints the candidates instead.

List your declarations with their IDs with `aeat app modelo work list`, then
target the one you mean by passing its ID directly to `aeat app modelo work verify
--work-unit-id <work-unit-id>`.

To confirm which filing a command touched, check its state and the actions taken
on it:

```{cli-sequence} verification-reports-work-history
:verify: Confirm the declaration's state and action history read back.
```

(the-filing-deadline-has-passed)=
## The filing deadline has passed

The check does not look at filing deadlines. It still runs for a past period and
can pass; the deadline check applies later, when you record the filing with `work
file`.

If the deadline has passed, file late through AEAT's own channels; consult AEAT
or an advisor about any surcharges that may apply.

## Where to get help

`aeat` prints its messages in Spanish unless you choose another language. Add
`--language en` (or `es`, `ca`, `hu`) straight after `aeat` for one command, or
store a default for your profile with
`aeat config profile edit --output-language en`. The examples in this
documentation are recorded in English. The field names this guide names -
`granted_verificado_completo`, `completeness_status`, `legal_refs` - match the
output exactly, so you can map any line back to the step that describes it.

If a report or an error message does not match what this guide describes, see
[Diagnose and repair](troubleshooting.md). Unfamiliar terms are defined in the
{doc}`glossary </_generated/glossary>`. Before you share command output to ask
for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or
NII.

## Next steps

- [File at AEAT](file-at-aeat.md): enter the checked figures at the AEAT portal.
- [Review your calculation values](review-calculation-values.md): check and
  correct the inputs behind each box.
- [The filing workflow](filing-spine.md): how filings, saved calculations, and reports fit together.
- [CLI reference](../cli/index.rst): every command and option.
