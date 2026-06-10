# Plan your filing calendar

Use this guide when you want to understand what may be due, what is overdue,
and what to prepare next for the [active profile](profile-setup.md#what-the-active-profile-means).
A modelo is a Spanish tax form.

These commands are local unless a command is under `aeat app live`. Local
calendar commands read the [active profile](profile-setup.md#what-the-active-profile-means)
and local registry data. They do not file, submit, or contact the Agencia
Estatal de Administracion Tributaria (AEAT).

## Before you start

You need an [active taxpayer profile](profile-setup.md#what-the-active-profile-means).
If you do not have one, create it with
[Set up your taxpayer profile](profile-setup.md).

Calendar results depend on profile facts: taxpayer type, activity start date,
IVA regime, IRPF/Renta facts, withholding obligations, and other enrollment
details. You can maintain those facts manually in the profile. You can also
compare or apply AEAT Modelo 036 censo facts with
[Link Modelo 036 census information](censo-update.md), but censo linking is
not universally required.

If a profile is incomplete, calendar commands may stop and name the missing
facts. Fix the profile first. If you want to see partial results before the
profile is complete, add `--allow-incomplete` to skip that check.

## What are my filing obligations?

Start with the agenda:

```bash
aeat app overview agenda
```

The agenda ranks obligations around a reference date. The agenda shows:

- obligations due today
- obligations coming up in the next two weeks
- obligations that are already overdue

Use another reference date when planning ahead or reviewing a past point in
time:

```bash
aeat app overview agenda --date 2026-04-15
```

Change the upcoming window with `--horizon`; the default is 14 days:

```bash
aeat app overview agenda --date 2026-04-15 --horizon 30
```

To understand why one modelo appears or does not appear, use:

```bash
aeat app overview explain 130 --year 2026
```

`explain` reports whether that modelo applies, the registry reason, and the
profile facts used for the decision.

## What messages have I received?

Calendar commands do not read AEAT mailboxes. For DEHu notification snapshots,
use the live notification workflow:

```bash
aeat app live notifications latest
```

If you have not captured notifications yet, use
[Check AEAT notifications](check-aeat-notifications.md). Live notification
capture requires AEAT authentication and is read-only.

## What missed modelos did I forget to file?

Use backlog for past-due obligations that are not locally marked as presented:

```bash
aeat app overview backlog
```

The default backlog window starts 365 days before today and ends today. Narrow
the review when you are checking a specific period:

```bash
aeat app overview backlog --from 2026-01-01 --to 2026-06-30
```

Backlog is a local planning tool. It does not prove what AEAT has or has not
received. It depends on the [active profile](profile-setup.md#what-the-active-profile-means),
local filing markers, and local registry rules. For the local filing lifecycle,
see [The filing workflow: work units and calculation revisions](filing-spine.md).

## What upcoming modelos will I have to file?

Generate a calendar window:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31
```

Both dates are required in `YYYY-MM-DD` format. The calendar applies national
public holidays and business-day shifts before printing deadlines.

To see every registered profile instead of only the
[active profile](profile-setup.md#what-the-active-profile-means), add
`--all-profiles`:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --all-profiles
```

When you want to inspect obligations that `aeat` normally filters out, add
`--show-suppressed`:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --show-suppressed
```

Suppressed entries include obligations that do not apply given your profile
facts, or that are incomplete. Each entry shows why it was suppressed.

## When is year-end, and how long are periods?

Use the year you are preparing and the date window you care about. A full
calendar year window is:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31
```

Quarterly filing periods use `1T`, `2T`, `3T`, and `4T`. Annual filings use
`0A`. Monthly periods use two-digit month tokens such as `01` and `12`.

For a compact explanation of period codes, quarter boundaries, and annual
year-end - all addressed with `--year 2026 --period 1T` - see
[Understand filing periods](filing-periods.md).

## What should I do with one modelo?

List the modelo catalogue:

```bash
aeat app modelo list
aeat app modelo list --year 2026
```

Describe one modelo before creating filing work:

```bash
aeat app modelo describe 130
aeat app modelo describe 130 --period 1T
```

Then follow the filing workflow for the target modelo, year, and period:

- [Quickstart: produce a modelo file](quickstart.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [The filing workflow: work units and calculation revisions](filing-spine.md)

## If results look wrong

If a command reports missing profile facts, update the profile with
[Set up your taxpayer profile](profile-setup.md). If censo-derived facts may
be stale or missing, compare them with
[Link Modelo 036 census information](censo-update.md).

If a command reports an invalid date, inactive profile, or readiness problem,
use [Diagnose and repair your local setup](troubleshooting.md).

For exact command flags and output fields, use the
[CLI reference](../cli/index.rst).

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Check AEAT notifications](check-aeat-notifications.md)
- [Understand filing periods](filing-periods.md)
- [Work with Transactions](import-bank-statements.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [CLI reference](../cli/index.rst)
