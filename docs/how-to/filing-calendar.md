# Plan your filing calendar

Use this guide to see which filing obligations `aeat` derives from your active
profile, generate a date range calendar, and check why a modelo may apply. A
modelo is a Spanish tax form.

These commands are local. They read your profile and the local registry data.
They do not file, submit, or contact the Agencia Estatal de Administración
Tributaria (AEAT).

## What this calendar means

The calendar answers this question: based on your active profile and the local
modelo registry, which filing periods apply inside this date window?

It is not an official AEAT record of your filing obligations or filing history.
It does not prove that you filed every required form. The default overview
calendar shows deadline state from the local deadline engine, so applicable
obligations appear as due or late.

Profile and census facts decide which modelos appear. If your taxpayer type,
activity, Impuesto sobre el Valor Añadido (IVA) regime, or Censo registration
details are wrong, the calendar can be wrong too. Fix those facts first with
[Set up your taxpayer profile](profile-setup.md) or
[Link Modelo 036 census information](censo-update.md).

## Before you start

You need an active taxpayer profile. If you do not have one, create it with
[Set up your taxpayer profile](profile-setup.md).

Calendar commands depend on profile facts. If your profile is incomplete, a
command may stop and name the missing facts. Fix the profile first unless you
are deliberately checking partial results with `--allow-incomplete`. That flag
does not bypass a missing taxpayer model; declare the taxpayer model before you
use `agenda`, `backlog`, or `calendar`.

## See overdue and upcoming obligations

To rank overdue, due-today, and upcoming obligations, run `agenda`:

```bash
aeat app overview agenda
```

The output groups obligations into:

- `next_due`: the next obligation to handle
- `due_today`: obligations due today
- `due_soon`: obligations due within the `--horizon` period
- `overdue`: obligations already past their deadline

To plan from another reference date, use `--date`:

```bash
aeat app overview agenda --date 2026-04-15
```

To change the horizon, use `--horizon`. The default is 14 days:

```bash
aeat app overview agenda --date 2026-04-15 --horizon 30
```

## List overdue obligations first

When you want past-due obligations sorted oldest first, run `backlog`:

```bash
aeat app overview backlog
```

When you need a narrower review, limit the backlog to a date window:

```bash
aeat app overview backlog --from 2026-01-01 --to 2026-06-30
```

## Generate a calendar window

To generate a deadline calendar, run `calendar` with a start and end date:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31
```

Both dates are required. Use this date format: `YYYY-MM-DD`.

The calendar applies national public holidays and business-day shifts before it
prints deadlines. To generate the same window for every registered profile, add
`--all-profiles`:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --all-profiles
```

When you want to see obligations that `aeat` normally filters out, add
`--show-suppressed`. Suppressed entries include obligations that do not apply,
belong to another taxpayer attribution path, or are incomplete. Each entry
shows the verdict and the reason.

## Check why a modelo applies

To check one modelo, run `overview explain` with a modelo code:

```bash
aeat app overview explain 130
```

A modelo code is the number printed on a Spanish tax form, such as `130`, `303`,
or `100`. The command reports whether that modelo applies, the reason from the
local registry, and the profile facts used for the decision.

To check a specific fiscal year, pass `--year`:

```bash
aeat app overview explain 130 --year 2026
```

## Look up modelo details

To list the modelo catalogue, run:

```bash
aeat app modelo list
```

To filter the catalogue to a fiscal year, pass `--year`:

```bash
aeat app modelo list --year 2026
```

Before you create filing work for one modelo, describe it:

```bash
aeat app modelo describe 130
```

When the revision depends on the filing period, pass `--period`:

```bash
aeat app modelo describe 130 --period 1T
```

Use the [CLI reference](../cli/index.rst) for the full flag list and valid
period values.

## If results look wrong

If a command reports missing profile facts, update the profile with
[Set up your taxpayer profile](profile-setup.md).

If a command reports an invalid date, inactive profile, or readiness problem,
use [Diagnose and repair your local setup](troubleshooting.md).

For command flags and output fields, use [CLI reference](../cli/index.rst).

## Next steps

- [Work with transaction data](import-bank-statements.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [How filings, work units, and calculation revisions fit together](filing-spine.md)
- [CLI reference](../cli/index.rst)
