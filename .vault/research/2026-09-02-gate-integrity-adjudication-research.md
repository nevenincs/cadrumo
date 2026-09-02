---
tags:
  - '#research'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:50da274c53c8a122dc9eed3cc1926e8f37784117949df3a2d63a3429335f4a5e'
related: []
---

# `gate-integrity-adjudication` research: `measurement of the three blocked gate calls`

Three gate results were reported as blocked on a design call: two broken TUI
import contracts, a population of type diagnostics attributed to deliberate
negative tests, and four mechanical gates regressing repeatedly. Each was
presented with a premise attached. This record measures the three premises
against the live tree so the decisions can rest on what is there rather than on
what the reports imply. Every premise turned out to be materially wrong, and in
two cases the correct decision is the opposite of the one the premise pointed to.

## Findings

### The broken TUI contracts do not report the consolidation

`lint-imports` reports 8 kept and 3 broken, and the two TUI contracts break on
edges that have nothing to do with retiring the second console script.

The backend prohibition breaks on five in-process imports from two CLI modules:
`_modelo_work_review_cli` reaching `tui.modelo.view.work_review`, and
`_modelo_work_select_cli` reaching `tui.components.host`, `tui.modelo.routes`,
`tui.modelo.view.controller` and `tui.modelo.view.work_select`. Both construct
Textual applications and call `run()` inside the CLI process.

The module that actually implements the consolidation keeps the contract. The
session bridge names the TUI as a module string and spawns it as a child
interpreter, and its own docstring states that a CLI entrypoint may not import,
load, re-export, annotate against, or register from the TUI. The consolidation
commit that removed the second console script introduced no import edge; the
five edges arrived with the modelo work-surface lane.

The sibling prohibition breaks on exactly one edge, and it is a test:
`tui.tests.test_installed_entrypoint` reads the session bridge's two constants
to assert that the command the CLI builds is the module-execution surface. Its
purpose is to prove the boundary is kept.

The dependency direction the contracts encode is current, not superseded.
`2026-08-11-tui-architecture-adr` D11 states it, and
`2026-09-02-unreachable-capability-tui-navigation-join-adr` restates it as a hard
constraint on the join the consolidation created.

The aggregate gate cannot reach a clean exit from these two contracts in any
case: the layered-architecture contract is independently broken across a large
application-to-adapters population.

### The deliberate-wrong-type population is empty

The `invalid-argument-type` diagnostics were measured after deduplication by
file, line and column. The reported figure counts diagnostics, not sites: a
single mapping splatted into a typed constructor emits one diagnostic per
candidate parameter, and one call site in the runtime-compatibility tests
accounts for 63 of them on its own. 275 diagnostics collapse to 202 unique sites.

Of those, 23 sit within reach of a refusal assertion, and 3 of the 23 are in
production modules rather than tests. The remaining 18 were each read against
the assertion they accompany.

Not one asserts that a wrong type is refused. Every refusal is a value or
constraint refusal on a well-typed value: an empty actor label, a label past a
length bound, a malformed digest string, a negative count against a non-negative
bound, an out-of-set token against a narrowed enumeration, an empty or
one-element tuple against a completeness rule, contradictory operands against a
coherence rule. The constraints are carried by annotated string and numeric
types whose static form is the plain base type, which is why a bad value and a
good one are the same type to the checker.

The diagnostics at those sites come from five causes independent of the
assertion: a payload builder declared as a mapping of `object` splatted into a
typed constructor; a dynamic splat keyed by a loop or parametrize variable,
which makes the checker union every candidate field; a bare string standing in
for an enum member in a fixture; an over-broad `object` annotation on a helper
parameter or return; and mapping value-type invariance, where a status-enum
value is not accepted against a declared integer.

The nearest miss is a test whose docstring says the narrowing rejects a value
the bare string accepted. Its diagnostic sits on a fixture helper returning
`object`, not on the refused expression, and the refused token is a well-typed
string inside an untyped mapping.

Several candidate sites already carry a suppression comment in a checker dialect
the active checker does not honour, so those suppress nothing.

### The commit-time proposal was already decided here, from an incident

`prek.toml` records the policy in its own header: every hook is verify-only, no
autofixer runs at commit time, and the commit hook script is deliberately not
installed. Its stated rationale is an incident in this repository, where the
runner's stash and restore step lost work because an autofixing hook modified
the staged tree mid-commit and the rollback conflicted with concurrently-edited
files.

The formatting and lint gates are already declared there in verify-only form.
What is absent is the installed commit-time trigger, which is the part withheld
on purpose.

Measured on the live tree: format and style are red, relative-imports and
dependencies are green. The two red gates report drift in files other
contributors are currently editing, so a commit-time autofixer would have
rewritten another writer's in-flight work.

Cost is not the constraint. Over the whole tree, format runs in 9s, style in 4s,
dependencies in 5s, and relative-imports in 40s. Scoped to the paths of a change
instead, the same three file-decomposable checks complete in about 2s.

Three of the four gates decompose to individual files; the relative-import
scanner already accepts explicit paths for per-file runs. The dependency gate is
a usage-versus-declaration predicate over the whole tree and does not decompose.

The repository already has the shape a change-scoped check would take: a
change-scoped documentation verb bounds work by the change, and one locale hook
is written to read committed blobs and write nothing so it stays compatible with
the verify-only policy.

## Sources

- `.importlinter` - the two TUI contracts, and the launcher-only contract whose
  test allowances are the file-local precedent for separating production edges
  from test edges.
- `src/cadrumo/entrypoints/cli/_tui_session.py` - the out-of-process session
  bridge and its statement of the boundary.
- `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py:29` and
  `src/cadrumo/entrypoints/cli/_modelo_work_select_cli.py:46,60,61,62` - the five
  in-process edges.
- `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py:99` - the
  single sibling-direction edge.
- `src/cadrumo/entrypoints/tui/__main__.py` - the module-execution surface, which
  currently accepts only a self-test flag.
- `pyproject.toml:128` - the two declared console scripts.
- `prek.toml` - the verify-only policy and its recorded incident rationale.
- `justfile` - the four mechanical gate recipes and the change-scoped
  documentation precedent.
- `dev/quality/relative_imports.py` - the scanner's documented per-path
  invocation mode.
- `2026-08-11-tui-architecture-adr` D11, and
  `2026-09-02-unreachable-capability-tui-navigation-join-adr` - the current
  dependency-direction authority.
- `2026-09-02-cli-distribution-consolidation-adr` - the consolidation whose scope
  is the console-script count, not the import boundary.
- `2026-09-02-registry-enum-canonicalization-adr` - the campaign that owns the
  bare-string-for-enum sites.
