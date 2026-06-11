# Understand filing periods

Use this guide when a command asks for `--year`, `--period`, or a calendar date
window and you are not sure which period token to use.

## Calendar windows

Calendar commands use real dates:

```bash
aeat app overview calendar --from 2026-01-01 --to 2026-12-31
```

Both dates are inclusive and use `YYYY-MM-DD`.

## Modelo period tokens

Modelo work commands usually separate the filing year from the registry period:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
```

Common period tokens are:

- `1T`: first quarter, January 1 through March 31
- `2T`: second quarter, April 1 through June 30
- `3T`: third quarter, July 1 through September 30
- `4T`: fourth quarter, October 1 through December 31
- `0A`: annual period, January 1 through December 31
- `01` through `12`: monthly periods

Every command takes the year separately with `--year` and the period as one
of these AEAT tokens. Calendar shapes such as `2026Q1` or bare `2026` are not
accepted; pass `--year 2026 --period 1T` instead.

## Period filters on ledger lists

The `ledger list` and `ledger review` commands filter by period through
`--filter` clauses. The period token and the year travel as two separate
clauses, using the same AEAT tokens:

```bash
aeat app ledger list --filter period=1T --filter year=2026
```

Pass the bare token to `period=` and the year to `year=`. The two clauses go
together: `--filter period=1T` without `--filter year=2026` is refused. Combined
forms such as `period=2026-1T` or `period=2026Q1` are not accepted.

## Year-end

For local planning, year-end is December 31 of the filing year. Annual period
`0A` covers the full calendar year. The fourth quarter `4T` also ends on
December 31, but it is still a quarterly period, not an annual return.

Use [Plan your filing calendar](filing-calendar.md) to see deadlines after
holiday and business-day adjustments.

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [Review and supply calculation inputs](review-calculation-values.md)
