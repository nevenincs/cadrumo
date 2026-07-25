---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S200'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the complete unit suite and record the attributable result

## Scope

- `src/cadrumo/`

## Description

Run the complete unit suite and record the attributable result, then re-run every failing
gate at a later HEAD to separate tree properties from mid-run churn.

## Outcome

FAILED. No global green is claimed, and no failure is attributable to this feature except
one module-size ceiling.

Command: `uv run --no-sync pytest -q -rs -n 8 --dist=loadfile -m "unit and not external_tool and
not os_keychain" --ignore=<workbook parity> --tb=line`.
Exit line `20 failed, 14371 passed, 12 warnings in 1116.99s`, exit code 1. HEAD was `5eaf4b0ee6`
when the run started and `69f81ee69b` when it ended, so the result is a measurement across a
moving tree and is treated as such.

Eighteen of the twenty failures localised to fourteen gate modules. Re-running exactly those
fourteen at HEAD `bbe8bd8aad` gave `14 failed, 95 passed in 302.21s`, so four of the eighteen were
resolved by peer commits landing between the two runs: the ledger import-linter configuration
gate, the cross-module import resolution gate, and both production-scope private-import cases of
the import-hygiene gate.

The fourteen that reproduce, each with its owner:

Module size budgets and the CLI module size gate both fail on the CLI config package initialiser
at 1385 lines against a ceiling of 1261. This record ORIGINALLY attributed that breach to this
campaign as its one feature-owned regression. That attribution was WRONG and is corrected here on
numstat evidence.

The file stood at 1254 lines, INSIDE the 1261 budget, immediately before the peer commit that opens
the manager from profile create and edit. That commit is `+138 / -4`, a net `+134`, taking the file
to 1388 and through the ceiling in one move. The three commits after it are this campaign's and
they REDUCE the file: the TUI create-routing fix `+9 / -7`, the wizard retirement `+1 / -6`, and a
docstring correction `+2 / -2`. Net across the three is minus three lines.

The two subjects read as a joint cause because they land the same day on the same file and both
concern the manager. The numstat separates them cleanly: one added 134 lines, the other removed
three. The breach is the peer commit's, and no amount of this campaign's shrinking would have
cleared a ceiling it did not cross.

The same budget gate additionally names a modelo reconcile module at 1283 against 1250 and a
registry ledger-bindings module at 1475 against 1440, both owned elsewhere.

Marker integrity, mock inventory and monkeypatch inventory reproduce the three ratchet failures
recorded under S198.

Import hygiene fails on the test-only private-import debt, 57 live sites against 52 documented,
with named new sites.

Lazy import policy fails because two ceilings carry slack over their live counts.

Locale translation honesty fails on one Catalan key identical to English.

Docstring core-struct links fails twice, on four module uses and two public functions.

Module test-coverage reachability fails on two user-profile modules.

The combined-period-string gate and the dev UTF-8 literal gate each fail once.

## Notes

Two of the original twenty could not be localised from the line-traceback output. One is
attributable with confidence: a live censal-pull module failed to import a provenance constant
that did not exist, and that whole module was deleted by a peer commit during the run, so the
failure is moot rather than fixed. The coordinator should re-derive the exact residual set with a
failure summary on a settled tree rather than trusting this enumeration to be exhaustive.

Custody cases carrying the keychain marker were excluded by the marker expression, as they fail
for environmental reasons under an agent logon and have never been observed green in any lane.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
