---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:170f0429df2a87b368f30d48955e925f7ba990cbc165e2d308f2ce6c1810df6d'
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

## Concurrent failures at HEAD bc80aa2808

Updated failure catalog at re-measurement. No global green is claimed.

S192 — dev/docs/tests/: 3 peer-owned failures. `test_generated_page_is_fresh` and
`test_settings_fields_all_present_in_env_example` from MCP stdio watchdog setting not
reflected in docs (commit `faa8643ece`). `test_sphinx_nitpicky_build_is_clean` from
four docstring-reference warnings across relocation commits `286db29da0`, `914c59ad07`,
`279bd29bfc`, and registry commit `8bec35ac37`.

S198 — nine repository ratchets: 4 peer-owned failures. Monkeypatch: `dev/deploy/tests/`
(commit `b6a10f9105`). Relative imports and skip/xfail: `src/cadrumo/entrypoints/mcp/tests/`
(commit `faa8643ece`). Mock inventory: `dev/docs/apidocs/tests/` and `dev/docs/tests/`
(commit `9f59f32595`).

S203 — duplication: 13 clones (AMBER). One new pair (censal-datos campaign) vs original
reading of 12. No feature-owned pair in either reading.

No feature-owned regression in any failing lane at HEAD `bc80aa2808`.

## Re-verified 2026-07-28 at HEAD `a4534b8a2bfbf9d9d95eed883f98d2098a437ec0`

Written three days after the sections above, against a tree that has moved. The
figures below supersede any that conflict; nothing above is edited, so the
original measurement stays readable next to what it became.

The discipline this Step records - no global green claimed, unrelated failures
attributed separately - is unchanged and remains correct. Two of its specific
attributions are superseded.

The two broken layering contracts are no longer broken. All five are evaluated
and kept at this HEAD, and the remedy was removal of the violating edges by
their owning campaigns rather than a widened ignore list.

The remaining ratchet and marker failures it attributes to other campaigns were
not re-measured here and are carried forward as recorded, still attributed
elsewhere. The Step's claim was never that the tree is green; it was that this
campaign's surface is not what is red, and that claim is strengthened rather
than weakened by the contracts having since gone green.

Command and result for the structural scan cited above, added because the
evidence bar asks for the invocation and not only its corpus. The scanner was
run as a standalone module against the production tree:
`python ast_twin_scan.py` over `src/cadrumo`, production modules only, 70-node
floor. Result line: `corpus: 1411 production modules, 4250 bodies hashed, 0
unparseable` followed by `collision groups: 39 total, 25 spanning more than one
file`, exit code 0. Its discrimination proof printed first and must pass or the
run aborts: `discrimination: twins collide = True (want True); control collides
= False (want False)`.

Command and result for the layering re-measurement cited above:
`uv run --no-sync lint-imports`, result line `Contracts: 5 kept, 0 broken`,
exit code 0, analysing 3668 files and 17633 dependencies.
