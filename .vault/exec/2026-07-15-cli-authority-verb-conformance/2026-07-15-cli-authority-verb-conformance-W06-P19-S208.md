---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S208'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Record unrelated concurrent failures separately without claiming global green

## Scope

- `.vault/exec/`

## Description

Record every unrelated concurrent failure separately, attributed by owner and by working-tree
state, without claiming global green.

## Outcome

SATISFIED. NO GLOBAL GREEN IS CLAIMED FOR THIS TREE.

Committed at HEAD and owned by other campaigns. The marker-integrity ratchet fails on three
modules whose module-level marker follows a conditional: a TUI theme test, a calculations
relation-prefill grounding test, and a filing registry-snapshot freshness test. The mock-inventory
ratchet fails on two banned stub helpers, both in that filing test. The monkeypatch ratchet fails
on eight sites, all in that same filing test, patching a production resources accessor. Two of five
layering contracts are broken: a bucket payload-version test reaches three application packages
from the domain layer, user-profile registration and the operator-output sandbox notice reach the
storage adapter from the application layer, and four TUI tests reach the CLI config manager
frontend from the adapters layer. Ruff reports an unsorted export list in a TUI form screen, an
unsorted import block in the IVA domain package, and format drift in the wizard commands module and
the core config module. The module size budget is exceeded by a modelo reconcile module at 1283
against 1250 and a registry ledger-bindings module at 1475 against 1440. The Catalan catalogue
carries one key identical to English, a manager-flow section title, against a ceiling of zero. Two
lazy-import ceilings carry slack over their live counts. Test-only private-import debt stands at 57
live sites against 52 documented. The docstring core-struct gate fails on four module uses and two
public functions. Two user-profile modules are unreachable from any test. The combined-period-string
gate and the dev UTF-8 literal gate each fail once. The duplication-disposition gate fails because
the live scan observes two TUI clone groups the dispositions file does not record.

Uncommitted peer work in flight. A Modelo 390 sequence-contract blocked-reason line reddens
documented-command conformance, described under S187. A relocation of two wizard result schemas
into a new untracked application module removes them from the production discovery walk, described
under S192. Ruff reds sit on two untracked peer test files, a release pointer guard and a Clave
credential resolution, and on two modified peer test files, distribution claims and the
publish-release workflow.

Resolved by peer commits DURING this Phase, recorded so the earlier readings are not read as
current. An auth error-code registry race reddened three CLI conformance suites and cleared without
any change on this side. A stale ignored-import entry naming a deleted registry test blocked the
import linter before it could evaluate contracts, and was corrected between two runs. A live
censal-pull module imported a provenance constant that did not exist; the whole module was then
deleted. Two production-scope private-import regressions cleared between two runs of the same gate.

Environment, not code. Custody cases carrying the OS keychain marker are excluded from every lane
here. They fail with a Windows error 1312 under an agent logon, have never been observed green in
any lane, and were not verified. Separately, the documentation gate was launched at the default
worker count on a box carrying 114 concurrent Python processes from other agents and CI lanes; three
xdist workers died with a node-down message and the run wedged with no further progress. It was
stopped and re-run at reduced parallelism. That is a resource-contention artefact of the shared
machine, not a documentation defect, and the re-run is what the S202 record reports.

## Notes

The single failure attributable to this feature's own surface is the CLI config package
initialiser at 1385 lines against its 1261 ceiling, recorded under S200. Everything else above
belongs to a concurrent campaign or to the machine.

The tree moved continuously through this Phase. Between the first and last measurement HEAD
advanced through at least eight commits, and two separate gates changed verdict without any change
on this side. Every result in this Phase is therefore bound to a named HEAD, and where a verdict
mattered the gate was re-run and the second reading recorded alongside the first.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
