# Plan your filing calendar

This page covers the filing calendar: how to see what may be due, what is
overdue, and what to prepare next for the
[active profile](profile-setup.md#what-the-active-profile-means), and which
`--year` and `--period` tokens address each filing window. A modelo is a
Spanish tax form.

These commands are local unless a command is under `aeat app live`. Local
calendar commands read the [active profile](profile-setup.md#what-the-active-profile-means)
and local registry data. They do not file, submit, or contact the Agencia
Estatal de Administración Tributaria (AEAT).

## Before you start

You need an [active taxpayer profile](profile-setup.md#what-the-active-profile-means),
and Cadrumo needs your master-key passphrase (it prompts for it). If you
do not have a
profile, create it with [Set up your taxpayer profile](profile-setup.md).

The profile must declare at least one obligation, or these commands refuse with
"El perfil activo no declara este modelo fiscal". A profile created without
taxpayer type, estimation regime, or IVA regime declares no modelo and shows
nothing. Declare those facts first with
[Set up your taxpayer profile](profile-setup.md).

Calendar results depend on profile facts: taxpayer type, activity start date,
IVA regime, IRPF/Renta facts, withholding obligations, and other enrollment
details. You maintain those facts manually in the profile - see
[Maintain Modelo 036 census facts in your profile](censo-update.md).

If a profile is still incomplete, a command may stop and name the missing facts.
Fix the profile first. To see partial results before the profile is complete,
add `--allow-incomplete` where the command accepts it (`agenda`, `backlog`, and
`calendar`). The CLI emits help, results, and refusals in Spanish.

## What are my filing obligations?

Start with the agenda. It ranks obligations around a reference date, showing
what is due today, what is coming up in the next two weeks, and what is already
overdue. Pass `--allow-incomplete` on a profile whose census facts are not yet
fully filled in, change the reference date with `--date`, and widen the upcoming
window with `--horizon` (the default is 14 days):

```{cli-sequence} filing-calendar-agenda
:verify: Confirm the agenda ranks obligations around each reference date.
```

To understand why one modelo appears or does not appear, use:

```{cli-sequence} filing-calendar-explain
:verify: Confirm the explain report resolves for the modelo and year.
```

`explain` reports whether that modelo applies, the registry reason, and the
profile facts used for the decision.

## What messages have I received?

Calendar commands do not read AEAT mailboxes. For DEHu notification snapshots,
use the live notification workflow:

```{cli-sequence} filing-calendar-live-notifications
```

If you have not captured notifications yet, use
[Check AEAT notifications](check-aeat-notifications.md). Live notification
capture requires AEAT authentication and is read-only.

## What missed modelos did I forget to file?

Use backlog for past-due obligations that are not locally marked as presented.
The default window starts 365 days before today and ends today; narrow it with
`--from` and `--to` when you are checking a specific period:

```{cli-sequence} filing-calendar-backlog
:verify: Confirm the backlog resolves for the default and narrowed windows.
```

Backlog is a local planning tool. It does not prove what AEAT has or has not
received. It depends on the [active profile](profile-setup.md#what-the-active-profile-means),
local filing markers, and local registry rules. For the local filing lifecycle,
see [The filing workflow](filing-spine.md).

## What upcoming modelos will I have to file?

Generate a calendar window:

```{cli-sequence} filing-calendar-strict
```

Both dates are required in `YYYY-MM-DD` format. The calendar applies national
public holidays and business-day shifts before printing deadlines.

The calendar is stricter than `agenda` and `backlog`: it also refuses while a
profile check is unresolved, such as `censo.enrolment_unverified`. That check
reports that your census-backed enrollment facts are operator-declared, not
AEAT-verified; AEAT publishes no read-only census view the tool could confirm
them against. Review the profile facts (see
[Maintain Modelo 036 census facts in your profile](censo-update.md)) and add
`--allow-incomplete` to print a provisional calendar. Provisional entries are
marked `censo_enrolment=unverified`. Add `--all-profiles` to include every
registered profile instead of only the
[active profile](profile-setup.md#what-the-active-profile-means), or
`--show-suppressed` to inspect obligations Cadrumo normally filters out:

```{cli-sequence} filing-calendar-calendar
:verify: Confirm the provisional calendar prints across its variants.
```

Suppressed entries include obligations that do not apply given your profile
facts, or that are incomplete. Each entry shows why it was suppressed.

## Period tokens and dates

Calendar commands use real inclusive dates in `YYYY-MM-DD` format, as shown
above. Modelo work commands instead separate the filing year from the registry
period:

```{cli-sequence} filing-calendar-work-status
:verify: Confirm the work unit status reads back for the visible target.
```

The period tokens are:

- `1T`: first quarter, January 1 through March 31
- `2T`: second quarter, April 1 through June 30
- `3T`: third quarter, July 1 through September 30
- `4T`: fourth quarter, October 1 through December 31
- `0A`: annual period, January 1 through December 31
- `01` through `12`: monthly periods

Which tokens a modelo accepts is modelo-specific, not universal. A quarterly
modelo such as 130 accepts only `1T` through `4T`; an annual modelo such as 390
accepts only `0A`; Modelo 303 accepts `1T` through `4T` and `01` through `12`,
but not `0A`. A token the modelo does not accept is refused (for example, 303
with `0A` reports "no revision for ... period='0A'"). To see the tokens one
modelo accepts, run `aeat app modelo describe 303` and read its `Períodos`
line.

Every command takes the year separately with `--year` and the period as one of
these AEAT tokens. Calendar shapes such as `2026Q1` or bare `2026` are not
accepted; pass `--year 2026 --period 1T` instead.

The `ledger list` and `ledger review` commands filter by period through
`--filter` clauses. The period token and the year travel as two separate
clauses, using the same AEAT tokens:

```{cli-sequence} filing-calendar-ledger-filter
:verify: Confirm the ledger filter accepts the split period and year clauses.
```

Pass the bare token to `period=` and the year to `year=`. The two clauses go
together: `--filter period=1T` without `--filter year=2026` is refused.
Combined forms such as `period=2026-1T` or `period=2026Q1` are not accepted.

For local planning, year-end is December 31 of the filing year. Annual period
`0A` covers the full calendar year. The fourth quarter `4T` also ends on
December 31, but it is still a quarterly period, not an annual return. The
calendar commands above show deadlines after holiday and business-day
adjustments.

## What should I do with one modelo?

List the modelo catalogue, then describe one modelo before creating filing work:

```{cli-sequence} filing-calendar-catalogue
:verify: Confirm the catalogue lists modelos and describes one for a period.
```

Then follow the filing workflow for the target modelo, year, and period:

- [Quickstart: produce a modelo file](quickstart.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [The filing workflow](filing-spine.md)

## If results look wrong

If a command reports missing profile facts, update the profile with
[Set up your taxpayer profile](profile-setup.md). If census facts may be stale
or missing, re-check them against your Modelo 036 copy with
[Maintain Modelo 036 census facts in your profile](censo-update.md).

If a command reports an invalid date, inactive profile, or readiness problem,
use [Diagnose and repair your local setup](troubleshooting.md).

For exact command flags and output fields, use the
[CLI reference](../cli/index.rst).

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Check AEAT notifications](check-aeat-notifications.md)
- [Import and manage transactions](import-bank-statements.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [CLI reference](../cli/index.rst)
