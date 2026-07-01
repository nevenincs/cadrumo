# RB-003 Verification blocks your export

An export refuses because the draft is not yet verified, or verification reports
blocking findings. Read the findings, fix what they name, and re-verify before
exporting.

## When to use this

- An export refuses with a message that the revision `is not verified-complete
  or filed and cannot be exported`.
- Verification returns `granted_verificado_completo` `false` with a
  `completeness_status` of `incomplete` or `blocked`.

## What you will need

- The profile whose filing you are preparing, active.
- The modelo, year, and period of the draft.
- Your master-key passphrase.

## Fix it

Run verification against the draft you want to export. Name the modelo, year,
and period:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Replace `303`, `2026`, and `1T` with your own. Period tokens are `0A` for
annual, `1T` to `4T` for quarters, and `01` to `12` for months.

The command saves a report whether or not the draft passes. Open the report and
read its findings:

```bash
aeat app modelo verification-report list
aeat app modelo verification-report view <verification-report-id>
```

Each finding carries a severity - **blocking** or **warning** - the affected
box, a message describing what the rule checked, and a suggested next action. A
blocking finding is what stops the export; a warning does not.

Fix what each blocking finding names. A missing required value is supplied
through the calculation inputs - see [Review and supply calculation
inputs](../how-to/review-calculation-values.md). When you have supplied the
values, recalculate and re-verify:

```bash
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

## Confirm the fix

Verification passes when the result shows `granted_verificado_completo` `true`
and a `completeness_status` of `complete`. The saved calculation is now verified
and the export works.

## Why this happens

An export produces a file you upload to AEAT yourself, so the tool only exports a
calculation that passed its verified-complete contract. Blocking findings mark
the reasons a draft is not yet safe to file; the export stays refused until they
are cleared.

## Related

- [Verify a draft filing](../how-to/verification-reports.md) - run verification
  and read every field of the report.
- [Review and supply calculation inputs](../how-to/review-calculation-values.md)
  - supply the values a finding says are missing.
- [Follow the filing workflow](../how-to/filing-spine.md) - where verify and
  export sit in the full loop.
- [Diagnose and repair your local setup](../how-to/troubleshooting.md) - the
  full symptom index.
