---
tags:
  - '#adr'
  - '#cli-lazy-subcommand-mutation'
date: '2026-07-09'
modified: '2026-07-10'
related:
  - '[[2026-07-10-cli-lazy-subcommand-mutation-research]]'
---

# `cli-lazy-subcommand-mutation` adr: `Lazy sub-command loader must not mutate the shared Typer object` | (**status:** `proposed`)

## Problem Statement

The CLI's lazy sub-command loader mutates a shared, module-global `typer.Typer`
object in place as a side effect of command resolution. Surfaced by task #211:
five `config auth certificate` / `config auth apoderado` refusal tests that
invoked the `config` sub-app object directly (`config_app`) failed
order-dependently once any prior test had materialised the full `aeat` app. The
tests were made production-faithful in commit `b4bd9b4ceb` (invoke via the root
app, assert the rendered refusal), and the underlying loader smell was left
untouched and escalated for this decision. Production is unaffected today; the
mutation is a latent fragility, so this ADR is a design-smell decision, not an
incident fix.

The mechanism, verified empirically against the live tree. Heavy sub-command
groups register a `LazySubcommand` (in
`src/aeat/entrypoints/cli/_command_suggestions.py`) instead of an
eagerly-imported Typer instance, so constructing the `aeat` app object never
pays the roughly 0.6 s registry parse that every leaf command module pulls
transitively. `AeatTyperGroup.get_command` triggers `LazySubcommand.load` on
first dispatch into a subtree. `load` calls its `decorate` hook —
`decorate_typer_app` in `src/aeat/entrypoints/cli/_errors.py` — on the factory's
return value, which for the `config` subtree is the module-level `config_app`
object re-exported from `src/aeat/entrypoints/cli/_config/__init__.py`.
`decorate_typer_app` walks the Typer tree recursively (`_decorate_typer_node`)
and REPLACES every `registered_callback.callback`,
`registered_commands[i].callback`, and `registered_groups[i].callback` in place
with the `command_error_boundary` wrapper. Because `config_app` is a module
global reached by the lazy factory, this rewrites the callback identity on the
shared object and on its entire descendant tree (`auth`, `certificate`,
`apoderado`, `diagnostics`). A direct probe confirms it: before root
materialisation the `certificate` command callbacks and the `config` root
callback hold one identity; after `get_command(config)` on the root app they
hold new identities on the same shared object.

The observable failure is order-dependent. A callback wrapped by
`command_error_boundary` RENDERS a refusal to stderr and exits (`SystemExit`),
whereas an unwrapped callback lets the typed `CliRefusedBoundaryError` propagate.
The #211 tests invoked `config_app` directly and asserted on the leaked typed
exception; once a prior test had lazily materialised `config` through the root
app, the shared `config_app` was already decorated in place, so the same object
now rendered the refusal instead of leaking it, and the assertion failed. The
coordinator characterised the symptom as sub-app leaves failing to resolve into a
`UsageError`; the reproduced, deterministic root cause is the in-place callback
decoration of the shared object. Either way the invariant broken is the same: a
resolver mutates shared global state as a side effect, so the state of
`config_app` depends on whether the root app has been resolved yet in the
process.

## Considerations

Production is genuinely unaffected. Every production dispatch reaches `config`
through the root `aeat` app's lazy resolver, which decorates the subtree exactly
once (`LazySubcommand.load` caches `self._command`, and `command_error_boundary`
memoises wrappers by `id(callback)` in `_WRAPPED_CALLBACKS`). Nothing in
production calls `get_command` / `invoke` on a sub-app Typer object directly, so
the order-dependent divergence never arises. The harm to date is confined to test
authorship.

The perf path this loader protects is load-bearing and gated. The 0.6 s registry
parse and a 2.0 s cold-start ceiling for `aeat --version` are enforced by
`src/aeat/entrypoints/cli/tests/test_lazy_command_tree.py`
(`test_version_cold_start_completes_under_budget`,
`test_importing_cli_package_does_not_import_registry`,
`test_state_free_surface_does_not_import_registry`). Any change to the lazy-load
spine must keep those green. The prior CLI-startup ADRs
(`2026-06-03-user-profile-lazy-import-adr`,
`2026-06-03-cli-errors-domain-package-lazy-import-adr`,
`2026-07-02-arch-remediation-lazy-import-policy-adr`) treat the state-free
surfaces as a distinct architectural class with strict import constraints; this
ADR sits under that umbrella and must not regress it.

The decoration must happen at load time, not construction time. The root
`decorate_typer_app(app)` runs at import, when `config` is deliberately absent
from the eager tree, so the subtree can only be decorated when it is lazily
materialised. That is why `LazySubcommand` carries a `decorate` hook at all. The
open question is not WHETHER to decorate at load time but WHAT to decorate: the
shared module-global Typer instance (today) or a per-invocation artefact.

The likelihood of a future direct sub-app caller is low but non-zero. Several
existing tests already walk sub-app `registered_commands` / `registered_groups`
structurally (`test_json_schema_conformance`, `test_operator_surface_contract_drift`,
`test_live_read_subgroups`, `test_ledger_verb_spine`); they inspect names, not
invoke, so decoration does not break them. A future production path that embeds a
sub-app, generates completions from one, or dispatches a sub-app object directly
would inherit the same order-dependent trap silently.

## Considered options

- **Option A — De-mutate: decorate a per-load artefact, leave the shared object
  pristine.** `LazySubcommand.load` decorates and returns a per-load result
  without back-writing to the module-global Typer. Two feasible shapes: (i) walk
  and wrap the callbacks on the built Click command tree that
  `typer.main.get_command` returns, rather than on the source Typer instance; or
  (ii) decorate a structural copy of the Typer subtree. Pros: permanently removes
  the trap class; the shared object becomes safe to reuse and inspect regardless
  of resolution order; restores the "a resolver does not mutate shared input"
  invariant. Cons: touches the whole CLI's load-bearing lazy-load spine
  (`LazySubcommand.load`, `decorate_typer_app`); the wrapping interception point
  shifts (Click callback vs raw Typer callback for shape i; Typer-internal copy
  fidelity for shape ii), so it must be proven behavior-preserving against the
  error-contract and cold-start gates. Kept as the recommended target design.

- **Option B — Accept the mutation, add a guard/contract.** Keep the in-place
  decoration (prod-safe) but detect or forbid direct sub-app `get_command` /
  invoke after full-app load, e.g. a runtime assertion or a structural test
  asserting the invariant "only the root app is invoked." Pros: near-zero blast
  radius; makes the hidden invariant explicit. Cons: does not remove the trap,
  only annotates it; a runtime guard on the hot resolution path adds cost and its
  own failure surface; the guard cannot distinguish a legitimate future direct
  caller from misuse. Rejected as the primary decision (it institutionalises the
  smell) but its documentation half is folded into Option A as defense-in-depth.

- **Option C — Status quo plus a codified convention.** Leave the loader; codify
  "tests invoke via the root app, never a sub-app object directly" as a project
  rule — the convention commit `b4bd9b4ceb` already embodies. Pros: zero code
  risk; the fix already shipped. Cons: the shared object stays a latent trap; the
  convention binds test authors only, not a future production direct caller; the
  invariant stays implicit in prose rather than enforced by the object being safe.
  Kept as the low-risk fallback if the team judges Option A's blast radius
  unjustified given production is unaffected.

## Constraints

The change lands on a load-bearing surface with two hard contracts that must stay
green in the same change: the cold-start / no-registry-import budget gates in
`test_lazy_command_tree.py`, and the CLI error contract (every command and group
callback's exceptions rendered as the shared-spine JSON / text error document,
with the `_UNDER_TEST` re-raise escape hatch intact). Typer is a third-party
dependency whose `get_command` internals (it reads `typer_instance._add_completion`,
`.registered_commands`, `.registered_groups`, `.registered_callback`, and the
`pretty_exceptions_*` attributes) are not a stable public API; Option A shape (ii)
would couple to those internals, so shape (i) — decorating the built Click tree —
is the lower-coupling path and is preferred for the implementation, subject to
proving the interception point still satisfies the error contract. No parent
feature is unstable; the dependency is on the already-accepted lazy-import ADRs,
which are stable.

## Implementation

If Option A is ratified, the change is decomposed as follows. First, land a
regression test that reproduces the trap: after materialising the `config`
subtree through the root `aeat` app, assert the shared `config_app` object is
unmutated — every `registered_callback` / `registered_commands` /
`registered_groups` callback identity across the `config -> auth -> certificate`
/ `apoderado` tree is invariant across root-app materialisation (the probe used
to ground this ADR shows those identities currently change; the test fails today
and passes once de-mutated). Pair it with a behavioural assertion that a direct
sub-app invocation behaves identically before and after root materialisation.

Second, move the decoration off the shared object. In `LazySubcommand.load`,
build the Click command via `get_command` first, then apply the error-boundary
decoration to the resulting Click command tree (walk its `commands` recursively,
wrapping each Click command / group callback), instead of calling
`decorate_typer_app` on the source Typer instance. The module-global `config_app`
(and every lazily loaded subtree) is never written to. `decorate_typer_app`
remains for the eager root-app decoration path; a Click-tree-oriented companion
walker is introduced for the lazy path. Keep the `_WRAPPED_CALLBACKS` memoisation
so repeated resolution within a process wraps once.

Third, run the full guard set: the cold-start / registry-import gates, the CLI
error-contract conformance, and the operator-surface / schema-conformance walks,
plus a `--collect-only` clean-collection check. Confirm the roughly 0.6 s parse
is still deferred and the 2.0 s `aeat --version` ceiling holds.

Fourth, regardless of A or C, codify the convention that tests and any embedder
invoke the CLI through the root `aeat` app, not a sub-app Typer object directly —
the durable, cross-session half of the lesson.

Concrete code-surface footprint: `src/aeat/entrypoints/cli/_command_suggestions.py`
(`LazySubcommand.load`, the `decorate` hook call); `src/aeat/entrypoints/cli/_errors.py`
(`decorate_typer_app` / `_decorate_typer_node`, and a new Click-tree walker);
`src/aeat/entrypoints/cli/__init__.py` (the `_lazy` wiring that passes
`decorate=_decorate_typer_app`); the shared sub-app objects are
`src/aeat/entrypoints/cli/_config/__init__.py` (`config_app`) and its peers; the
reproducing test lands under `src/aeat/entrypoints/cli/tests/`. No change to
`config_app`'s definition or to any command body.

## Rationale

De-mutation (Option A) is recommended because the defect is a shared-mutable-state
side effect in a resolver, and the correct fix removes the side effect rather than
documenting it. The mutation already cost debugging time in #211, and while
production is unaffected today, the invariant "a lazily resolved sub-app is safe
to hold and invoke directly" is worth more than the marginal complexity of
decorating a per-load artefact — it makes the object correct by construction
instead of correct by convention. The perf benefit is fully preserved: decoration
and `get_command` still run once per subtree on first dispatch; only the write
target moves from the shared Typer instance to the per-load Click tree, which is
negligible cost. The decision is grounded in the reproduced callback-identity
mutation, the `b4bd9b4ceb` fix and its commit message, the lazy-load budget gate,
and the CLI error-contract decoration path — no perf figure is asserted beyond the
roughly 0.6 s parse and 2.0 s ceiling already documented by the existing gate.

Honest counter-weight, recorded for the ratifier: because production is unaffected
and the only victims to date are test-authorship shapes, Option C (convention
only) is a defensible lower-cost choice, and the blast radius of touching the
lazy-load spine is real. This ADR recommends A but does not force it; the status
is `proposed` pending team-lead or operator ratification, and C is the explicit
fallback.

## Consequences

Choosing A: the shared sub-app objects become safe to invoke and inspect in any
order, removing a silent order-dependent trap for every current and future direct
caller (test or production); the "invoke via root app" convention becomes
defense-in-depth rather than the sole protection. The cost is a behavior-preserving
edit on the load-bearing lazy-load spine, which must land atomically with its
reproducing regression test and clear the cold-start and error-contract gates; a
subtle regression there would surface as either a cold-start budget breach or an
unrendered CLI error, both caught by existing gates. The Click-tree decoration
walker introduces a second decoration path alongside `decorate_typer_app`, a small
duplication to keep bounded.

Choosing C instead: zero code risk and the fix already shipped, but the latent
trap persists and a future production direct-sub-app caller would rediscover it
order-dependently; the invariant remains prose-enforced.

Either way, the codified "root-app invocation" convention closes the immediate
recurrence for test authors and is the cross-session lesson worth persisting.
