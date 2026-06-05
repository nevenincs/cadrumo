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

Some commands also accept compact period forms such as `2026Q1`, `2026-1T`,
`2026A`, or bare `2026` where a single period string is expected.

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
