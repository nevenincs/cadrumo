---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:4f2e03028179ace5559ca7dd737916c31ed2c257657d5036630e17a8c37f2b44'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W01.P01.S02 capability taxonomy review`

## Scope

Reviewed the current uncommitted implementation of `W01.P01.S02` in
`src/cadrumo/entrypoints/cli/_command_schema.py` and
`src/cadrumo/entrypoints/cli/tests/test_command_schema.py` against the accepted
command-scoped-loading ADR, its research and reference, the campaign plan, and
the always-on architecture, orchestration, quality, and Vaultspec rules. The
review covered safety, architectural intent, completeness, metadata-light
exact-enrollment support, typing, anti-tautology strength, and test quality.

## Findings

### capability-metadata-import-boundary | high | The taxonomy cannot be consumed as lightweight registration metadata

`CommandCapabilityClass` is declared in `_command_schema`, whose import eagerly
loads Pydantic, the application-layer operator-surface contract, the JSON schema
registry, and schema-surface declarations. A clean-process probe confirmed that
importing the taxonomy loads both `pydantic` and
`cadrumo.application.operator_surface` and leaves 548 modules loaded. The live
registration authority therefore cannot attach or reconcile this metadata
without paying unrelated schema/application cost, contradicting the ADR's
lightweight registration-metadata boundary and undermining the later universal
resolution gates that must consume the taxonomy on every node.

### state-free-performance-coupling | high | Authority-free commands are incorrectly restricted to metadata workloads

`CommandCapabilityClass.__post_init__` rejects every `state-free` declaration
whose performance class is not `metadata`. Capabilities describe which
authorities a command may enter, while performance classes independently
describe workload cost. An authority-free command may legitimately perform
pure computation or an interactive effect-free workflow. The current coupling
forces such nodes either to lie by declaring an unrelated authority or to be
unclassifiable, so the taxonomy cannot provide exact enrollment for the whole
live CLI and its class-relative budgets.

### closed-taxonomy-test | medium | The closed-set test does not fail when production silently adds a token

`test_command_capability_taxonomy_is_closed_and_serialisable` proves that a
handwritten list of expected tokens is accepted and one arbitrary unknown token
is rejected, but it never compares that expected set exactly with
`get_args(CommandCapability)`. Adding a production capability without enrolling
it in the test remains green. The contradiction matrix also omits unknown
capability, unknown side-effect, unknown performance, empty side-effect, and
`none`-plus-effect branches, leaving most runtime validation paths unproven.

### capability-metadata-import-boundary-resolution | low | Prior HIGH finding resolved on re-review

The corrected module has no runtime Pydantic, operator-surface, JSON-contract,
or schema-surface import at taxonomy-import time. Schema projection dependencies
are deferred to their owning call sites, and `SchemaModuleLoadFailure` is now a
stdlib dataclass. Direct source inspection and the fresh-process test confirm
that consuming `CommandCapabilityClass` adds none of the targeted application or
schema families. The prior HIGH finding is resolved.

### state-free-performance-coupling-resolution | low | Prior HIGH finding resolved on re-review

The corrected validator requires `state-free` commands to remain effect-free
but no longer couples that authority declaration to the `metadata` performance
lane. The production test constructs an effect-free `state-free` command in the
`compute` lane and verifies its expansion. The prior HIGH finding is resolved.

### taxonomy-negative-coverage-resolution | low | Prior validation-branch gap resolved on re-review

The contradiction matrix now plants unknown capability, unknown side-effect,
unknown performance, empty side-effect, and `none`-plus-effect declarations in
addition to the original contradictions. The runtime validation paths identified
in the first review are now exercised and the focused suite passes all fourteen
tests. That portion of the prior MEDIUM finding is resolved.

### taxonomy-gate-baseline | medium | Two import assertions and two closed sets remain weakly enforced

The fresh-process probe imports `cadrumo.entrypoints.cli` before taking its
module baseline. That package import already loads Pydantic and
`cadrumo.core.json_contract`, so the incremental `pydantic` and `json_contract`
assertions stay false even if `_command_schema` later reintroduces eager imports
of those already-loaded families; only the operator-surface assertion currently
bites independently. In addition, exact-set reconciliation covers
`CommandCapability` but not `CommandSideEffectClass` or
`CommandPerformanceClass`, so additions to either literal remain unenrolled by
the closed-set test. The implementation itself is currently lightweight and the
original capability set is exact, but the regression gate does not fully prove
those properties.

### taxonomy-gate-baseline-resolution | low | Remaining MEDIUM finding resolved on final re-review

The corrected exact-set test now reconciles all three production literals:
command capabilities, side-effect classes, and performance classes. The import
contract additionally parses the production module and rejects direct top-level
imports of Pydantic, operator-surface, JSON-contract, and schema-surface owners,
so its proof no longer depends on whether the CLI package preloaded those
families. The incremental fresh-process operator-surface probe remains as an
executed complement. The focused suite passes all fourteen tests and Ruff
reports no findings. The prior MEDIUM is resolved; final re-review found no
open LOW, MEDIUM, HIGH, or CRITICAL issue in the assigned diff.

## Recommendations

- For `capability-metadata-import-boundary`, place the taxonomy in the
  metadata-only command authority or make `_command_schema` itself defer all
  Pydantic, schema-registry, and application imports; add a clean-process import
  exclusion test that proves consuming the taxonomy does not load those
  families.
- For `state-free-performance-coupling`, keep authority, effects, and
  performance orthogonal except where a real semantic implication exists;
  explicitly prove an effect-free authority-free `compute` classification.
- For `closed-taxonomy-test`, assert exact equality between the expected token
  sets and the production `Literal` arguments, then plant one invalid case for
  every validation branch so each guard is independently demonstrated to bite.
- For `taxonomy-gate-baseline`, make the import probe observe targeted families
  before the CLI package can preload them, or add a structural top-level-import
  exclusion check, and assert exact token sets for the side-effect and
  performance literals as well as capabilities.
