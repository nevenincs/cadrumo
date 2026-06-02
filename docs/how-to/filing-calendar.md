# Plan your filing calendar

See which modelos are due and when, so you don't miss a deadline. You need an
active profile; to create one, see
[Set up your taxpayer profile](profile-setup.md). Every command here is local,
applies public holidays and business-day shifts, and never contacts the Agencia
Estatal de Administración Tributaria (AEAT).

## See what's due now

Classify your obligations around today into the next due item plus due-today,
due-soon, and overdue groups:

```
aeat app overview agenda
```

Set a different reference date with `--date YYYY-MM-DD`. Widen or narrow the
due-soon window with `--horizon <days>` (default 14). To list overdue
obligations you haven't filed yet, oldest first:

```
aeat app overview backlog
```

## Generate a calendar over a date range

List every deadline in a date window, with holidays and business-day shifts
already applied:

```
aeat app overview calendar --from 2026-01-01 --to 2026-12-31
```

Both dates are required and use ISO format (YYYY-MM-DD). Add `--all-profiles` to
span every registered profile, or `--show-suppressed` to include non-applicable
entries. See the [CLI reference](../cli/index.rst) for the full flag set.

## Understand why a modelo applies

To see why a form applies to you, decompose its applicability against your active
profile:

```
aeat app overview explain 130
```

It reports the applicable flag, the registry-backed rationale, and the profile
facts the decision depends on. Add `--year <year>` to evaluate a specific year.

## Where next

- [Quickstart](quickstart.md) - build and export a modelo once you know what's due.
- [Common filing recipes](index.md) - other modelos and tasks.
- [Pipeline explanation](../explanation/index.md) - how calculation,
  verification, and export connect, and why `aeat` never files.
- [CLI reference](../cli/index.rst) - every overview flag and exit code.
- [Glossary](../glossary.md) - the Spanish terms used here.
- Report a problem on the [issue tracker](https://github.com/wgergely/aeat/issues).
