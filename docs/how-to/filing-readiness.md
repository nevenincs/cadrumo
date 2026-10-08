# Check that a filing is ready

The check tells you whether a draft's box values pass the rules of the official
form. Readiness asks an earlier question: is everything the calculation depends on
in place: profile facts, transaction data, and earlier filings? Use the commands
in this guide before you calculate, and again before you export, so nothing silent
is missing underneath a clean-looking draft.

These commands read the active profile and prompt for your passphrase. If you
have no profile, create one first with
[Set up your taxpayer profile](profile-setup.md).

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you [choose another
language](profile-setup.md#choose-the-output-language).

## Run the readiness report

Find the id of the version of the official form first, then report whether the active profile is ready for that modelo, year, and period:

```{cli-sequence} filing-readiness-report
:verify: Confirm the readiness report resolves for the modelo, year, and period.
```

The command exits with status 2 while the target is not ready, so a script detects the gap from the exit status. In this example `ready` is `false` because the fresh profile still lacks the sources for some of the modelo's values.

The report covers four axes, each reported separately:

- **Profile readiness** (`profile_ready`) - every profile fact the modelo
  requires. Each missing fact is listed by its section and field key, so you
  know exactly what to fill in with `aeat config profile edit`.
- **Tax rules readiness** (`registry_ready`) - whether the tax rules hold a version of the official form that covers the modelo, year, and period.
- **Records readiness** (`ledger_ready`) - for modelos filled from your records, the same source checks as `aeat app ledger preflight`, listing each transaction that blocks the period and why.
- **Values Cadrumo fills in** (`binding_ready`) - the figures the form pulls from other sources. `missing_bindings` lists each of these values whose source is not available yet.

Readiness does not check box-level completeness of a draft. That is what the check
(`aeat app modelo work verify`) does. See [Check a draft declaration and act on the issues](verification-reports.md).

## Check what this filing depends on

Some modelos fold in values from other filings. An annual summary reads its
quarters, and a cross-modelo box reads another form's result. List the
dependencies the official form declares for a filing year, then narrow to one
modelo, or to one modelo and period:

```{cli-sequence} filing-readiness-dependencies
:verify: Confirm the dependency inventory resolves for the filing year.
```

`--period` requires `--modelo`. With both set, the command also evaluates the current blockers for that exact filing (for example an earlier period whose AEAT receipt is still missing), so you see what must be resolved before this period can safely build on the ones before it. For the background, see [Building on earlier filings](../explanation/building-on-earlier-filings.md).

## See everything that happened to a filing

List every recorded lifecycle event for one modelo (calculations, checks passed and refused, filings, corrections, imports):

```{cli-sequence} filing-readiness-history
:verify: Confirm the modelo history stream resolves for the filing year.
```

Add `--period` to narrow to one period. This is the modelo-wide audit trail; for
the events of a single declaration, use `aeat app modelo work history`. See [The
filing workflow](filing-spine.md).

## Compare two filing years

See how this year's figures moved against last year's, box by box:

```{cli-sequence} filing-readiness-compare
```

Pass `--year` exactly twice. Each compared year needs a declaration with a saved calculation; the command refuses otherwise. Each row shows the box, its label and section, both values, the difference, and the percent change; all-zero rows are omitted from the text output. The comparison uses the most recent checked calculation of each year and falls back to the latest draft when none has passed the check. A year compared from a draft is flagged `BORRADOR` in the output.

Use the comparison as a sanity check before filing: an unexpected jump in a
box is worth tracing back to its transactions before you export.

## Look ahead to the year-end Renta

If you file quarterly Modelo 130 instalments, project what the year-end
Modelo 100 would look like from the quarters filed so far:

```{cli-sequence} filing-readiness-project
```

`--ccaa` names your autonomous community of tax residence, which selects the
regional scale for the Modelo 100 calculation.

The projection needs a version of the official Modelo 100 form for the year you project. Until that year's version is published, `project` refuses and says that no version of the form covers the filing year. A covered year also needs the date-valued profile facts a Renta filer declares.

The output shows the accumulated Modelo 130 figures (income, expenses, net
result, instalments paid) and the projected Modelo 100 result: the taxable
base, the state and regional gross tax (cuota íntegra), the state and regional
net tax (cuota líquida), and the resulting tax (cuota resultante).

**Read the extrapolation flag before trusting the numbers.** With fewer than
four quarters filed, the projection extrapolates a full year from the
quarters available and marks the output, for example
`quarters_filed 2/4 (extrapolated from 2Q)`. An extrapolated projection is a
planning estimate, not a draft Renta: it assumes the remaining quarters look
like the filed ones.

Refine the projection with values the quarters cannot know: withholdings,
personal circumstances, or specific boxes:

```{cli-sequence} filing-readiness-project-refine
```

Withholdings default to zero when not supplied, so a projection without them
overstates the balance due if you had retenciones. Each projected box carries its
formula and legal references in the JSON output, the same legal basis as a real
calculation.

For when the year-end filing actually happens, see
{ref}`Period codes and dates <period-tokens-and-dates>`.

## Trace a value to its legal basis

Every calculated value carries its legal basis, and each review step shows it. The formula behind each calculated box carries its legal and source references. See [Review and supply calculation inputs](review-calculation-values.md):

```{cli-sequence} filing-readiness-formulas
:verify: Confirm each computed box exposes its formula and grounding.
```

Two more places show the legal basis:

- The issues from the check name the legal references behind each rule. See [Check a draft declaration and act on the issues](verification-reports.md).
- `aeat app review queue --explain` - pending issues with their legal references.
  See [the review
  queue](classify-transactions.md#see-everything-that-still-needs-a-decision).

## Next steps

- [Check a draft declaration and act on the issues](verification-reports.md) - box-by-box check of the
  draft.
- [Review and supply calculation inputs](review-calculation-values.md) - fill
  missing values that readiness or the check found.
- [How filings build on earlier ones](../explanation/building-on-earlier-filings.md) -
  how cross-period dependencies work.
- [The filing workflow](filing-spine.md) - declarations, earlier calculations, and the history of each declaration.
- [CLI reference](../cli/index.rst) - full option reference.
