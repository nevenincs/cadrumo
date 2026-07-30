---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S282'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the two Code-Stands-Alone violations, a feature tag in a hashing test docstring and vault stems in the duplication disposition fields

## Scope

- `src/cadrumo/core/tests/test_hashing_adoption.py`
- `dev/audit/duplication_dispositions.toml`

## Description

- Replace the feature-tag citation in the hashing recurrence gate's module
  docstring with a statement of the same fact that names no development record.
- Remove the two vault-stem fields from the duplication disposition `[meta]`
  table, confirming first by exact search that the declaration site is their
  only occurrence and that the reader consumes only the `group` array.
- Remove the ADR and audit stems from the disposition file's header comment,
  preserving the count-is-advisory statement they carried.
- Retire the plan Step-id reference in the one `cluster-owned` group's `owner`
  field and in the two comments describing that classification, keeping the
  domain-meaningful cluster name.

## Outcome

SATISFIED. Four violations were found and removed where the Step anticipated
two: beyond the docstring feature tag and the `governing_adr` /
`governing_audit` fields, the header comment carried the same two stems in
prose and one disposition group's `owner` field carried a plan Step-id range,
which the Code-Stands-Alone mandate names explicitly alongside document stems.
An exact search over both files now returns no development-record identifier.

Removal was proven safe before it was made rather than after. The disposition
reader resolves only the `group` array, so the two `[meta]` fields had no
consumer; an exact search across the tree confirmed the declaration site was
their sole occurrence, so nothing read them anywhere.

Gates at HEAD `038b55ad2ef243ffe6dd9ec53b57e62ff7c4a7d6`:

- `uv run --no-sync pytest src/cadrumo/core/tests/test_hashing_adoption.py
  --collect-only -q` collected 3 tests; the run exited `3 passed in 21.17s`.
- `uv run --no-sync pytest dev/audit/tests/test_duplication_scan.py -q -m ""`
  collected 8 tests and exited `8 passed in 72.27s`, including the
  disposition-coverage gate that reparses the edited file against a live clone
  scan.
- `ruff check` and `ruff format --check` on the edited test module returned
  `All checks passed!` and `1 file already formatted`.

The marker default is recorded because it nearly produced a false green here.
Running both files together collected 3, not 11: every duplication-scan case
was silently deselected, so the first run did not exercise the disposition
file at all. The `-m ""` re-run is what actually verified the edit.

## Notes

No incidents; no peer work touched. The disposition file was last committed by
a peer campaign one day before this edit and carried no uncommitted working
change, so a pathspec commit was safe.

Two observations recorded rather than actioned, both outside this Step's scope.
No gate enforces the Code-Stands-Alone mandate anywhere in the tree — an exact
search for one returns nothing — so this class of violation is caught by author
discipline alone and will recur. And the disposition `[meta]` table declares
`observed_groups = 14` while the file carries 15 groups; the count is advisory
and unread by the gate, so it is stale metadata rather than a failure, and it
predates this edit.
