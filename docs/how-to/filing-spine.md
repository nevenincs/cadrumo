# How filings, work units, and calculation revisions fit together

`aeat` supports local preparation, verification, export, and reconciliation of
Spanish tax filings before manual Agencia Estatal de Administración Tributaria
(AEAT) portal submission. The command line now centres the common workflow on
the filing that an operator can see: active profile, modelo, filing year, and
period.

## Visible filing target

The visible filing target is:

- the active profile,
- the modelo code,
- the filing year,
- and the period.

For example, Modelo 303 for the first quarter of 2026 is addressed as:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
```

This is the normal operator-facing address. The same shape works across create,
calculate, verify, file, export, reconcile, status, and revision-listing
commands.

Internally, the resolver also binds the target to the registry revision that
defines the modelo for that filing period. If more than one active work unit
could satisfy the same visible target because of a registry-revision conflict,
the command refuses and asks you to choose the intended revision explicitly.

## Internal IDs

Work-unit IDs and calculation-revision IDs still exist. They remain
content-addressed identifiers for audit, replay, storage, and machine consumers.
The command line may print them, and advanced scripts may pass them, but routine
filing work should not depend on manually carrying them between commands.

## Work-unit selection

When you pass modelo, year, and period, the command first searches the active
profile for that visible filing target. It does not silently create a second
active work unit for the same target.

If no active work unit exists,
`aeat app modelo work create --modelo 303 --year 2026 --period 1T` can
provision one.
If more than one candidate would match, the command refuses and reports
candidates instead of guessing.

If a requested registry revision conflicts with the existing work unit, the
command refuses with conflict guidance.

The work unit is the filing workspace. It is the singleton for the resolved
filing target in the active profile, and it owns the pointers that make later
commands ergonomic:

- the current calculation revision,
- the filed calculation revision,
- and the current filing record, when a filing record exists.

## Calculation revisions

A work unit can contain multiple calculation revisions. Re-running calculation
for the same visible target saves another revision under the same work unit.
The new or reused draft becomes the current calculation revision for that work
unit.

The supported revision selectors are:

- `current`,
- `latest-draft`,
- `latest-verified`,
- `filed`,
- and an explicit calculation-revision ID for exact replay.

Commands choose revisions according to their own semantics:

- `aeat app modelo work calculate --modelo ... --year ... --period ...` creates
  or reuses a draft revision and sets it as current.
- `aeat app modelo work verify --modelo ... --year ... --period ...` defaults
  to the current draft revision for that filing.
- `aeat app modelo work file --modelo ... --year ... --period ...` defaults to
  the current verified revision and records a local filed marker.
- `aeat app modelo export --modelo ... --year ... --period ... --output PATH`
  prefers the filed revision, then the current verified revision.

These defaults are command-specific. They are not a generic "latest revision"
rule. Use `--select` when you need a different revision selector.

## Exact-addressing options

Exact work-unit and calculation-revision IDs remain useful when:

- an automation already stores the exact ID,
- an audit needs to replay a specific revision,
- a visible target is ambiguous and the operator wants to select one candidate
  explicitly,
- or a machine consumer needs content-addressed stability.

For everyday command-line use, prefer modelo, year, and period.

## Next steps

- [How to run the shortest Modelo lifecycle](quickstart.md) - the shortest
  procedure from ready profile to exported file.
- [How-to guides](index.md) - model-specific filing recipes.
- [Command reference](../cli/index.rst) - exact flags and selector options.
