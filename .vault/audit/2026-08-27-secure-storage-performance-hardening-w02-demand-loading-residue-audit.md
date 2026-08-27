---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:6b6584e563afa3272a185db7df64fd4539ce5d214f93a0fa5dab1a661399487d'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
---

# `secure-storage-performance-hardening` audit: W02 demand-loading residue

## Summary

The `W03.P08.S32` cold-process listing contract was the first gate to observe a
real CLI process end to end. On its first run it failed on three properties
`W02` had already marked complete, and chasing the last of them surfaced three
more defects. All six are fixed; this record exists because the checkbox and
the tree disagreed, which is the failure mode `aeat-agent-orchestration`
warns about -- delivered-as-specified and recorded-but-not-implemented wearing
the same mark.

None of this was caught earlier because no gate ran a whole command in a fresh
process and looked at what it imported and wrote. `test_lazy_command_tree`
guards one family (registry) on the help path; `test_cli_performance_budgets`
tests the calibration arithmetic, not any live node.

## Findings

### F1 - the registry loaded at bootstrap for every command

`src/cadrumo/entrypoints/cli/_common.py` imported
`domain.calculations.registry.authority` at module scope for ONE call site on a
filing-precondition refusal path. `_common` is loaded by the CLI bootstrap, so
every command -- including all 68 state-free nodes -- paid for the whole
calculation registry.

Observed: 138 registry modules at CLI import. After demand-loading: 0.

### F2 - the custody adapter dragged in the authenticated aggregate

`adapters/persistence/storage/_profile_custody.py` imported
`_profile_custody_carry` at module scope, reaching
`ledger.confirmation_record` -> `confirmation_gate` -> `evidence_draft` ->
`invoices` -> `workflow.state_models` -> `active_profile` ->
`profile_bucket_scan` -> `profile_repository`. Carry is needed only when carry
runs; it is now loaded at its two delegating methods.

### F3 - every leaf invocation materialized the whole storage tree

`_profile_authentication_gate.preflight_parsed_leaf` called
`ensure_storage_tree()` unconditionally. A read-only listing created `blobs`,
`financial`, `secrets`, `submissions` and the whole `cache` tree -- 25
directories -- while declaring `side_effects={none}`. Materialization is now
gated on the spec's own declaration, the same authority the census and write
routing read. This exempts 218 of 365 nodes.

Observed: 27 created paths, now 2.

### F4 - a payload monolith pulled a sibling command's services

`entrypoints/cli/_config_payloads.py` imports the application services every
config verb needs. The listing imported it for two row types and received
`application.config_reset` -> `user_profile.lifecycle` -> `custody_service`.
The two rows moved to `_config/_profile_list_payloads.py`, matching the
per-leaf payload convention already used by the censo, check and google leaves.
The monolith remains the home of every other config payload and is a candidate
for the same treatment per leaf.

### F5 - a second, heavier definition of "which profiles exist"

`application/workflow/profile_bucket_scan.py` produced a UUID-and-label
projection -- the same fact the summary inventory produces -- through the
authenticated aggregate, taking a per-profile custody lock and able to publish
a label head as a side effect of resolving a NAME. Two definitions of one fact
that could disagree. All four functions now read `summary_inventory`, so the
projection has one authority. Every consumer benefits: `config_reset`,
`login_interaction`, `status_projection`, `profile_health`, `_common`.

### F6 - the sandbox notice contradicted its own cheapness contract

`application/operator_output/_sandbox_notice.py` documents itself as "cheap
enough to call on every emitted line", then called
`CommittedProfileRepository().load()` -- custody lock, password material,
transaction journal, label-head verify-or-publish -- on every emitted line of
every command. It now reads the summary projection, and the docstring states
what it does.

### F7 - the systemic cause: hybrid application package roots

Every capability-family leak this campaign traced ends the same way, and the
shape is worth naming once rather than rediscovering per node.

A CommandSpec parameter ANNOTATION is a `DeferredTarget`. Resolving a command
must resolve its annotations to build the Typer signature, so resolution
imports the module that owns each annotated type. Those modules are frequently
package roots -- `domain.modelos`, `application.registry`, `application.filing`
-- and those roots import heavy siblings and, in two cases, ADAPTERS at module
scope. So resolving one command pays for subsystems it never names.

GROUP figures hide which node is responsible. Per-node probing narrowed it
sharply, and the residue is far smaller than the group numbers suggest:

- `registry` group: 4 of 17 nodes are heavy, all `app/registry/manuals/*`.
- `encrypted-facts,network` group: 1 of 21, `app/ledger/import`.

A union proves a set CONTAINS a violation, never which member. Two separate
times this session a single-node probe returned clean and looked like a blind
gate when the group was genuinely dirty.

`domain.modelos` was fixable in one file because it is a PURE re-export facade
(113 names, no other top-level code): converting it to the PEP 562 lazy map
took it from 277 modules to 3. `application.registry` and `application.filing`
are NOT: they are hybrids that define real code (15 and 35 top-level
definitions) AND re-export. A lazy map cannot be dropped over them; each needs
its definitions split from its re-exports so the root can become inert. That is
a structural campaign, not a patch, and it is the honest reason the remaining
capability residue stays open.

## Carry-forward

- The diagnostic log root (`logs`, `logs/cadrumo.log`) is still created by any
  invocation, because `get_logger` runs at module import in 178 modules and
  `configure_logging` deliberately creates the directory eagerly so an
  unwritable root degrades to stderr instead of crashing startup. The listing
  contract names those two paths as an explicit exemption rather than relaxing
  to a prefix match, so a real regression still fails loudly. Making the file
  handler lazy (`delay=True`) would move that degradation check to first emit
  and is a deliberate decision for the logging owner, not a silent change here.
- `core/i18n/_render.py` binds `_log = get_logger(__name__)` at module scope
  and never uses it. Dead, but not load-bearing for the above.
- `W04.P09` and `W04.P10` file hints name
  `test_command_loading_contract.py`, which the `S54`/`S55` cutover replaced
  with `test_command_spec_universal_gates.py`. The Step intent survives; the
  paths need rewriting before those Steps are worked.

- `application/operator_output/tests/test_operator_output.py` fails at HEAD on
  two cases that pin the retired `SCHEMA_REGISTRY` design.
  `core/json_contract.validate_registered_result` no longer performs a registry
  lookup: it asserts the result is a strict `OutputSchema` and revalidates it
  against its own type. So an "unregistered command" no longer raises, and a
  non-schema result raises "is not a strict output schema" rather than "does
  not conform to the registered schema". Committed code against committed
  tests, neither touched by this campaign. The tests need rewriting to the
  current contract by the owner of that boundary.
- `application/workflow/tests/test_profile_health.py` fails 6 cases when run as
  a FILE in isolation, with `ProfileKeysRegistrationError`: the profile-key
  reader depends on `cadrumo.application.wizard` having been imported by some
  other test first. It passes in a directory run. Demand-loading makes this
  class of accidental-import dependency more likely to surface, so the reader
  should ensure registration rather than rely on an incidental import.
- `read_profile_bucket*` needed the REFUSING half of the summary boundary
  (`require_summaries`). The typed-outcome form is correct only where a surface
  can explain itself to the operator; a function returning a pointer-or-`None`
  cannot, and an empty result there reads as "you have no profiles". Any future
  consumer of `summary_inventory` must make that same choice deliberately.

- The `domain.modelos` lazy-facade conversion was baselined rather than argued
  for. A detached worktree at the commit before it ran the same
  `application/modelo` suite: 158 failed / 1828 passed / 5 errors at BOTH
  revisions, and the failing NAME sets are byte-identical (163 = 163, empty
  diff both directions). Those failures are pre-existing peer breakage. The
  check was worth its fifteen minutes: a lazy facade breaks exactly the code
  that relied on import as a side effect, and one of the errors
  (`wizard.compiler` missing `WIZARD_FLOWS`) has that shape, so "the error
  types look domain-ish" would not have been evidence.
- The remaining capability-family leaks are NOT gratuitous eager imports, and
  must not be closed by widening declarations until each is adjudicated:
  - `encrypted-facts` retains ~5 registry modules, which are only
    `registry/__init__` plus the `registry.ids` leaf, pulled because
    `_row_source_identity` takes `BindingId` from there. The same file imports
    `ContentDigest` from `core.identity` two lines above; `BindingId` belongs
    there too. Placement, not thresholds -- a "fewer than N modules" gate would
    be the hardcoded-count anti-pattern.
  - `encrypted-facts,network` retains 152 registry modules through
    `ledger.actions_common` typing against `domain.modelos` protocols ->
    `CalculationRevision` -> `registry.bindings`. That chain is semantically
    real: a module typed against calculation revisions needs registry types.
    Either those nodes genuinely touch calculations and should DECLARE
    `calculation`, or the protocol module needs splitting so typing does not
    drag the registry. Widening the declaration to make a gate green would be
    weakening the claim, not satisfying it.
- `application/ledger/actions_common.py` no longer imports the concrete
  calculation catalogue adapter at module scope; it is constructed only when a
  caller injects no repository. This removes an application-to-adapter
  module-scope edge and is correct on layering grounds, but it did NOT move the
  152-module measurement, because the protocol chain above still pulls the
  registry. Recorded as a layering fix with no measured performance effect.

- Three read-only commands create the encrypted database by opening the
  cold-bootstrap secure-object store: `config auth apoderado check`,
  `config auth certificate list`, `config repair integrity objects`. Traced to
  `workflow_state_repository` -> `cold_bootstrap_store` -> `get_engine`.
  Bootstrap-on-first-access is SANCTIONED by `no-legacy-compatibility` (it is
  creation, not migration), so this is not plainly a defect. The open question
  is whether a command that only READS should open the store in a mode that
  declines to create it. That is a storage-engine decision, not a CLI one, and
  needs an owner. Until then the side-effect gate carries a reasoned
  per-command allowlist with a stale-entry case that deletes an entry the
  moment it stops applying.
- `CommandSideEffectClass` has no member meaning "writes a derived cache".
  `local-state` is bound by the CommandSpec invariant to profile-scoped write
  ROUTING, so declaring it on a command that writes the process-wide
  `cache/registry-verdict` or `cache/corpus-text` tree would assert something
  false about where its writes go. Nine leaves sit in that gap today. The gate
  excuses the derived tree by a documented predicate rather than by widening a
  declaration; closing the gap properly means a new taxonomy member.
- A `.profile-custody-root.lock` survives a read on five leaves. Lock files are
  coordination rather than content and are deliberately not unlinked (deleting
  a lock races the next acquirer), so this is recorded as expected rather than
  as a leak -- but it is the reason the predicate exempts `*.lock` at all.

- `W04.P09.S36` asks for static AND executed import-graph checks. The EXECUTED
  half exists and is maintained (`src/cadrumo/tests/test_deferred_cross_layer_imports.py`);
  this campaign declared its one new deferral there and deleted the row its
  sandbox-notice change retired. The STATIC half -- eager cross-layer edges and
  cycles -- is `.importlinter`, and it is DEAD: `uv run --no-sync lint-imports`
  aborts with "Modules have shared descendants." and never evaluates any of its
  11 contracts. Re-verified directly at HEAD here. A peer already owns this in
  `2026-08-27-tui-architecture-import-linter-suite-aborts-audit`, so it is not
  duplicated, but S36 CANNOT be closed on the executed half alone: half the
  Step's guarantee is currently unenforced, and closing it would record a
  protection the tree does not have.
- The deferred-edge inventory has drifted independently of this campaign: 4
  undeclared edges (`filing/_runtime_repository`, two more in
  `ledger/actions_common`, `modelo/_taxation_comparison`) and 25 stale rows
  (`bucket_maintenance/_service`, `auth/sessions`, `live/*`, `workflow/_adapters`,
  and several `core/resources/_repos` loaders that no longer defer). Adding the
  undeclared ones as UNADJUDICATED without reading them is exactly the silent
  absorption the gate exists to catch, so they are left for their owners.

- **UPDATE on the dead import-linter.** Root-caused and fixed rather than left
  as a dependency. One contract aborted the whole file:
  `tui-feature-independence` listed its modules as `<pkg>.**`, and a `**`
  expression expands to every descendant, so a package with a test subpackage
  yields both `<pkg>.tests` and `<pkg>.tests.test_x` -- an ancestor and its own
  descendant inside ONE listed expression, which an independence contract
  refuses. Import Linter reports that during contract CONSTRUCTION and aborts
  before evaluating anything, so a single malformed contract silenced all
  eleven. Isolated by running each contract alone: every other one evaluates
  normally.

  The suite now analyses 5481 files and 29127 dependencies: **4 kept, 6
  broken**. The six were invisible while it aborted -- the llm-to-persistence
  reach, four TUI contracts, and the LAYERED contract itself (e.g.
  `application.live.censo -> adapters.outbound.aeat.sede`). They are
  pre-existing debt owned by other campaigns; restoring the enforcement is what
  makes them visible.

  Consequence for `W04.P09.S36`: the static half now RUNS, but it does not
  PASS. The Step asked for checks covering eager cross-layer edges and cycles;
  those checks exist and enforce again, while six contracts report real
  violations outside this campaign's scope. S36 should close on "the checks
  enforce" only alongside this record, never as "the graph is clean".
