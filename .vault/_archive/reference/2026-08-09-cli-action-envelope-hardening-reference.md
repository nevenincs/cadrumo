---
tags:
  - '#reference'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0a4959ae7999175b564ca739e3e4d8b6077581995e5e55917a12f06df0ba74c2'
related: []
---
# `cli-action-envelope-hardening` reference: `Blast-radius census method and baseline`

This reference defines the repeatable census that must precede the campaign
plan. It combines calibrated semantic discovery, filesystem and exact-text
inventory, AST role classification, live command-schema projection, manual
negative dispatch, and set reconciliation. No single count is treated as the
blast radius.

## Summary

### Use a fixed-point behavior-to-authority census

Run separate semantic searches for recovery after refusal, workflow
continuation, guard preconditions, next-step rendering, error remediation, and
command-schema projection. Read the top cluster for each query in full. Every
new field name, model, helper, or locale family discovered becomes a new exact
search term and semantic query. Stop only when a complete iteration adds no new
producer, transformer, renderer, validator, or test cluster. RAG results are
seeds, never completeness proof; the current index warns that two published
sections are absent, so absence must be confirmed mechanically.

### Maintain three reconciled sets

1. **Candidate universe:** every production definition, assignment, call
   keyword, command literal, locale command, and test assertion associated with
   action guidance or refusals.
2. **Adjudicated canonicalization set:** each candidate labelled `canonical
   owner`, `producer`, `transformer`, `renderer`, `validator`, `test`, or
   `excluded`, with a reason. Exclusions are keyed by symbol and enclosing
   function, never line number.
3. **Live coverage set:** every registered CLI leaf joined to its input schema,
   mutability/profile guard, application preconditions, negative dispatch proof,
   structured failed-condition identity, recovery action, argument-binding
   sufficiency, recovery dispatch, and positive retry proof.

The plan may claim full blast radius only when every candidate has a disposition
and every in-scope live leaf/precondition row has all required proofs or an
explicitly grounded non-applicability reason.

### Baseline counts expose the scale and prevent premature scoping

On 2026-08-09, `fd -e py . src/cadrumo` found 4,608 Python files: 1,554
production and 3,054 tests. Exact search for `suggestion`, `next_action`,
`next_command`, `fix_command`, `remediation`, and `default_suggestion` touched
227 production files with 1,690 matching lines and 410 test files with 2,398
matching lines. Literal `aeat ` commands appeared in 331 production files, 729
test files, and 865 lines across four locale catalogues. The live contract
reported 311 registered command schemas, 24 mounted families, and only three
coarse lifecycle steps.

AST classification narrowed production constructor sites to 610
`default_suggestion`, 289 `suggestion`, 71 `next_action`, 50 `remediation`, 27
`next_command`, and five `fix_command` keyword arguments. These are occurrences,
not independent migration steps. The error registry alone contains 229 literal
command defaults, six prose defaults, and 375 null defaults. The 289 general
suggestions include 124 literal commands, 54 literal prose values, 27 f-strings,
21 call-derived values, 52 references, and smaller conditional/null groups.
An independent AST pass over `src`, `dev`, and `tests` found 1,472 production
occurrences and 437 test occurrences across the six field names. By role, the
production set contains 89 definitions, 32 assignments, 1,052 named-argument
producers, and 299 transformer reads. This independent count is intentionally
broader than the `src/cadrumo` constructor baseline and is retained as a
reconciliation check.

The six names are not a closed vocabulary. Semantic discovery found
`StorageWritePolicyDecision.recovery_hint` at
`src/cadrumo/application/storage_write_policy.py:74`; every newly found alias
must enter the next fixed-point iteration.

### The live coverage denominator is 308 callable leaves

Current runtime introspection reports 311 live schema keys with exact result
schema parity. Three are root callback surfaces, leaving 308 operator-callable
leaves. Click input projection resolves all 308; 156 leaves require inputs, with
279 required parameters. `PROFILE_BOUND_WRITE_VERB_PATHS` has 99 rows and
reaches 101 callable leaves. Bootstrap exemptions have 34 unique prefixes and
reach 63 leaves; three reset leaves overlap both sets, with bootstrap precedence.

These numbers form the initial coverage join, not the affected-site total. The
canonical campaign key is `(subject_leaf_key, condition_id, scenario_id)`.
Every leaf must be classified as having no preconditions, declared conditions,
or a grounded exclusion. Each declared condition row then carries its owner,
evidence, error code, recovery action, target input schema, bindings,
conditionality, negative dispatch, recovery dispatch, and retry proof.

### Classify by data flow before creating plan rows

Field definitions and error-code tables are schema owners. Constructors and
state gates are producers. Workflow detail maps and application DTOs are
transit. CLI/MCP/TUI helpers and locale functions are renderers. Conformance
tests and evaluator scenarios are validators. A migration step owns one coherent
producer-to-projection slice and names every affected symbol; it does not own a
directory or every textual match.

Known high-density clusters are `entrypoints/cli`, `application/modelo`,
`entrypoints/cli/_config`, `application/ledger`, the error registries, live AEAT
adapters, `application/overview`, `application/auth`, `application/workflow`,
`application/wizard`, and MCP projection. Semantically discovered aliases also
include deadline `Recovery.next_command`, TTY recovery, auth next actions,
wizard next steps, ledger-drift findings, and boundary error projection.

### Make the inventory executable and drift-sensitive

The implementation should add an AST-backed census command or test that emits
stable records keyed by path, enclosing symbol, role, field vocabulary, and
referenced command/action identity. A checked-in disposition table is acceptable
only when stale entries fail and new unclassified records fail. It must not gate
on an exact total count: the property is complete classification and live-schema
resolution, not preservation of today's 227 files or 1,690 lines.

The runtime matrix must be generated from the live leaf registry rather than a
hand-authored scenario list. Scenario fixtures supply states and real inputs;
the expected failed condition and recovery edge come from the same production
guard record being tested. Each negative row then resolves and executes its
recovery action and retries the original verb. Permanently forbidden actions
and live-AEAT/destructive operations use explicit safety dispositions rather
than fake execution.

### Reproducible discovery entry points

- Semantic code queries: operator recovery continuation after refusal; guarded
  CLI verb unmet prerequisite; free-form next-action and fix-command rendering;
  command input/output schema and action applicability.
- Exact filesystem census: `fd -e py . src/cadrumo`.
- High-recall vocabulary census: `rg -n` over the six known action field names,
  followed by `rg -n 'aeat '` over production, tests, and locales.
- Definition census: exact searches for `Recovery`, `Action`, `Verdict`,
  `Requirement`, `Precondition`, and typed action fields.
- Runtime universe: `aeat --format json app contract`, joined to MCP's live
  verb input-schema builder and storage write policy.
- Confirmation owners: `src/cadrumo/core/json_contract.py`,
  `src/cadrumo/core/errors/_registry.py`,
  `src/cadrumo/application/operator_surface`,
  `src/cadrumo/entrypoints/mcp/_input_schema.py`,
  `src/cadrumo/application/storage_write_policy.py`,
  `src/cadrumo/application/workflow`, and
  `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
## Historical error-code default preimage

The live candidate-disposition ledger deliberately contains only the current
source universe. Retired `ErrorCode.default_suggestion` declarations remain in
the dedicated non-runtime preimage ledger
`dev/quality/error_code_default_suggestion_preimage.json`. Its parser
`dev/quality/error_code_default_suggestion_preimage_ledger.py` reads immutable source
commit `930ef9f4017a23cccaf4990d287beb014fc9723c` through Git, AST-extracts every
former declaration, and requires ordered multiset equality with the checked-in
rows.

Each of the 612 rows retains the full source commit, error code, error qualname,
registry shard, exact old-value expression source, and source location. Its
existing `disposition_owner_step` value is immutable historical allocation,
called `historical_owner_step` in this rehoming boundary: it preserves the
former shard-to-Step evidence (`S50` through `S57` or `S64`) but is not an
active implementation owner.

Before any historical shard owner can be retired, `S50` must create a separate,
fail-closed per-record rehoming join for every historically non-null default.
Each join row must identify current producer locator(s), exactly one
`current_owner_step`, and one `disposition_kind`: a typed catalogue action
resolved through the live input schema, a typed terminal or safety no-recovery
outcome, or source-proven retired or unreachable state. Missing, duplicate, or
unscoped current-owner evidence fails the join. The rehoming data contains no
action, condition, command, or localized-text authority; runtime policy remains
at the current producer or guard and user-facing text remains locale keys plus
typed facts.

The historical preimage and its `historical_owner_step` remain immutable; the
new `current_owner_step` and `disposition_kind` evidence govern future work.
This removes the one-shard-one-active-Step implication without rewriting the
historical S28 execution and audit record.
