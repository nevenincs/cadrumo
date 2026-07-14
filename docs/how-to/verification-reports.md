# Verify a draft filing and act on the findings

This page covers the verification of a draft filing: running the check,
reading the saved report, and acting on each kind of finding. Verification
checks your saved calculation locally against the official form rules and
saves a report of what it found. Nothing is sent to AEAT; everything happens
on your computer. The order is always the same: calculate, then verify, then
export or record the filing.

The check asks three things: does every required box have a value; do the
sums add up consistently, with no box contradicting another; and does
anything block the form from being treated as complete. It also checks
conditions outside the draft itself: that any earlier period this form
builds on is filed and evidenced, that the running IVA balance carried
between periods reconciles, and that every carried-forward figure still
points at the revision it was filed under.

A passed check is a local check. Treat it as "my draft is complete and
consistent", never as "I have filed" or "I am on time". Verifying is **not**
the agency accepting your filing (the tool never contacts AEAT), **not** a
guarantee the upload will succeed (submission happens separately, outside
the tool), and **not** a deadline check (a draft can pass long after the
deadline; see [the deadline section](#the-filing-deadline-has-passed)).

## Before you start

**Requirement:** an active taxpayer profile with a name and surnames, and a
calculated draft to check. Create a profile with `aeat config profile create`,
supplying the name, surnames, and an activity-start date. The
activity-start date matters for a first filing: it scopes out the dependency on
a prior period you never filed, so verification can pass. See
[Set up your profile](profile-setup.md).

You also need a master-key passphrase (Cadrumo prompts for it). For a
first-period Modelo 303, record some business activity in the ledger, then
create and calculate the draft. The sequence below does all of this from the
seed ledger.

If you want to understand how filings and saved calculations fit together,
read [The filing workflow](filing-spine.md) first.

## Run verification

Create the draft, calculate it, verify it, and open the saved report. Verify
saves a report whether or not the draft passes, and `verification-report view`
reopens it by id:

```{cli-sequence} verification-reports-modelo-303
:seed: autonomo-irpf-2026
:verify: Confirm the verification report shows the draft is complete.
@step Open a Modelo 303 draft for the first quarter.
aeat --format json app modelo work create --modelo 303 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
@step Calculate the draft from the classified ledger.
aeat --format json app modelo work calculate {work_unit_id}
@capture calculation_revision_id result.calculation_revision_id
@step Verify the draft; the run saves a report you can reopen.
aeat --format json app modelo work verify {calculation_revision_id}
@capture verification_report_id result.verification_report_id
@step Open the saved verification report and read its findings.
@result aeat --format json app modelo verification-report view {verification_report_id}
@expect result.granted_verificado_completo == true
@expect result.completeness_status == "complete"
@expect exit_code == 0
```

Period tokens are `0A` for annual, `1T` to `4T` for quarters, and `01` to `12`
for months - see [Period tokens and dates](filing-calendar.md#period-tokens-and-dates).

With the profile and draft above, this first-period Modelo 303 passes: the
report reads `granted_verificado_completo` `true` and a `completeness_status`
of `complete` - the saved calculation is now verified and ready to export.

When the draft does not pass, the report reads `granted_verificado_completo`
`false` and a `completeness_status` of `incomplete` or `blocked`, and the saved
calculation stays a draft. The command saves the report in both cases, so you
can return to the findings later.

By default `work verify` checks the current saved calculation, and it checks
only drafts. To pick a different draft, use `--select latest-draft` or pass that
calculation's revision ID directly. Use `--by` to record who ran the check.

## List your verification reports

Every verification run leaves a report. List them with `aeat app modelo
verification-report list`.

To narrow the list to the reports for one saved calculation, add
`--calculation-revision-id` with that calculation's ID.

## View a report and read the findings

Open one report by its ID with `aeat app modelo verification-report view
<verification-report-id>` (the sequence above did exactly this on the report it
had just produced).

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
- The legal references behind the rule, where the rule has them.

For the legal references in machine-readable form, render the report as JSON.
`--format json` is a global flag, so it goes before the command. The card in
[Run verification](#run-verification) does exactly this: its closing frame is the
JSON `verification-report view` of the report it just produced.

Each finding in the JSON output carries `legal_refs` and `source_refs`. Most
findings name a legal reference - a cross-period dependency, for example, cites
the law behind the prior-filing carry. A few purely structural checks, such as
an unresolved registry snapshot, have none, so those fields are empty for them.

Blocking findings prevent the draft from becoming verified, and export needs a
verified calculation. Warnings do not block; read them, decide whether they
apply to you, and move on.

## After any fix: re-run verification

After you change anything, run `aeat app modelo work verify` again for the same
target, exactly as the card in [Run verification](#run-verification) does. That
card addresses the draft by its revision id; passing `--modelo`, `--year`, and
`--period` instead re-runs the check against the current draft for that target.

Confirm the finding you addressed is gone from the new report. Repeat until the
result shows `granted_verificado_completo` `true`. Each symptom section in this
guide finishes with this re-run step.

## The report says incomplete

Incomplete means required casillas have no value yet. The report lists which
ones under **missing required casillas**.

`--casilla` works only on boxes whose input kind is `manual`. A box filled from
your ledger or another source is `bound`, and `--casilla` refuses it with
`cannot override bucket-derived source-bound casillas`. Fix the source for those.
See [Review your calculation values](review-calculation-values.md). Check which
kind a box is, then supply the value for a manual one and recalculate:

```{cli-sequence} verification-reports-incomplete
:verify: Confirm you can read each box's input kind before supplying a manual value.
@step Check which input kind each box is; only manual boxes accept --casilla.
@result aeat --format json app modelo casillas 303 --period 1T
@expect exit_code == 0
@step Supply a manual casilla's value and recalculate.
@static aeat app modelo work calculate --modelo 303 --year 2026 --period 1T --casilla <ID>=<VALUE>
```

Then [re-run verification](#after-any-fix-re-run-verification). For the full
input workflow, including where values come from and how to check them, see
[Review your calculation values](review-calculation-values.md).

## The report says blocked

Blocked means at least one blocking finding stands between your draft and a
verified calculation. You cannot export the draft until you resolve every
blocking finding.

Read each finding's suggested next action first; it tells you what the tool
expects you to do. The common kinds of blocking finding:

- **A cross-field rule failed.** Two or more casillas disagree in a way the form
  rules do not allow. Check the values named in the finding against your records.
- **A value could not be derived.** The tool needed to compute a casilla but your
  data did not provide enough input. Supply the missing input or enter the value
  directly.
- **A prior-period record is missing.** This filing depends on a filing from an
  earlier period that is missing or unconfirmed. Record or confirm that earlier
  filing first. If you had no obligation in that earlier period because you had
  not started your activity yet, set your activity-start date on the profile so
  the dependency is scoped out (replace `me` with your profile name):

  ```{cli-sequence} verification-reports-scope-dependency
  :verify: Confirm setting the activity-start date on the profile succeeds.
  @setup aeat config profile create me --quiet --entity-type natural_person --tax-id 87654321X --name "Ana" --surnames "Garcia Lopez"
  @step Set the activity-start date so an unstarted prior period is scoped out.
  @result aeat config profile edit me --quiet --activity-start-date 2026-01-01
  @expect exit_code == 0
  ```

After each fix, [re-run verification](#after-any-fix-re-run-verification).

## Export refuses because no verified calculation exists

Export needs a verified (or locally-filed) saved calculation. It refuses a plain
draft with a message such as "current revision is still draft; verify it before
exporting" or "no exportable verified or filed revision exists". If the saved
calculation is still a draft, verify it first, as in
[After any fix: re-run verification](#after-any-fix-re-run-verification). Check
where the filing stands, then retry the export once verification grants
verified-complete:

```{cli-sequence} verification-reports-export-check
:verify: Confirm you can read where a filing stands before exporting.
@setup aeat config switch docs-sequence-sandbox
@setup aeat --format json app modelo work create --modelo 303 --year 2026 --period 1T
@step Check where your filing stands.
@result aeat --format json app modelo work status --modelo 303 --year 2026 --period 1T
@expect exit_code == 0
@step Once verification grants verified-complete, retry the export.
@static aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

## More than one filing matches

When more than one filing or saved calculation matches the modelo, year, and
period you named, the tool refuses to guess and prints the candidates instead.

List your filings with their work-unit IDs with `aeat app modelo work list`, then
target the one you mean by passing its work-unit ID directly to `aeat app modelo
work verify --work-unit-id <work-unit-id>`.

To confirm which filing a command touched, check its state and the actions taken
on it:

```{cli-sequence} verification-reports-work-history
:seed: autonomo-irpf-2026
:verify: Confirm the work unit's state and action history read back.
@setup aeat config switch docs-sequence-sandbox
@setup aeat --format json app modelo work create --modelo 303 --year 2026 --period 1T
@step Show the work unit's current state.
aeat --format json app modelo work status --modelo 303 --year 2026 --period 1T
@step Show the actions taken on the work unit.
@result aeat --format json app modelo work history --modelo 303 --year 2026 --period 1T
@expect exit_code == 0
```

## The filing deadline has passed

Verification does not check filing deadlines. It still runs for a past period and
can pass; the deadline gate applies later, when you record the filing with
`work file`.

If the deadline has passed, file late through AEAT's own channels; consult AEAT
or an advisor about any surcharges that may apply.

## Where to get help

Command labels and messages display in Spanish to match the official AEAT forms,
while this guide is in English. The field names this guide names -
`granted_verificado_completo`, `completeness_status`, `finding_legal_refs` -
match the output exactly, so you can map a Spanish line back to the step that
describes it.

If a report or an error message does not match what this guide describes, see
[Diagnose and repair](troubleshooting.md). Unfamiliar terms are defined in the
{doc}`glossary </_generated/glossary>`. Before you share command output to ask
for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or
NII.

## Next steps

- [File at AEAT](file-at-aeat.md): upload the exported file at the AEAT portal.
- [Review your calculation values](review-calculation-values.md): check and correct the inputs behind each casilla.
- [The filing workflow](filing-spine.md): how filings, saved calculations, and reports fit together.
- [CLI reference](../cli/index.rst): every command and option.
