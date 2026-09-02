---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9f7c6df76adc0f1b9d95eac1628aea750ba220d754cc3d1de6623e4157d78b2e'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s18 recipe tests review`

## Scope

Reviewed the S18 Justfile detector-teeth suite against the accepted object-name declustering
plan and the current recipe and CLI contracts. The review covered real `just` discovery and
execution, mutation-group metadata, the exact no-argument path to CLI-default rehearsal,
absence of implicit apply or receipt authority, exact explicit argument forwarding, child
exit propagation, shell metacharacter handling, live-tree safety, and platform skip behavior.
No recipe, CLI, or test code was modified.

## Findings

The four findings from the initial review below are resolved in the current test
bytes: dry-run output is read from the combined streams, the dump helper has an
explicit validated cast, the missing-manifest proof is scoped to the pre-S19 state,
and real PowerShell executions share the platform prerequisite.

### powershell-profile | medium | Recipe execution remains dependent on the operator profile

The real JSON dump and its test pin the script interpreter arguments to `-NoLogo`
and `-File`, without `-NoProfile`. PowerShell therefore loads the invoking user's
profile before executing the generated recipe script. A profile can define an alias
or function named `uv`, alter command lookup, emit output, mutate state, or fail,
making the mutation recipe and its argv probe dependent on ambient user code. The
probe fixture prepends a temporary `uv.cmd` to `PATH`, but that does not outrank a
PowerShell alias or function and therefore does not isolate the claimed exact argv
boundary.

### dry-run-stream | medium | The real dry-run assertion reads the wrong output stream

`just --dry-run` renders the recipe on stderr in the resolved local tool, while the test
loops over `dry_run.stdout`. The focused suite therefore fails even though the rendered
command is present and safe. This also means the dry-run no-apply/no-receipt assertions are
not currently executable evidence.

### dump-type-narrowing | medium | The recipe dump helper fails the required type gate

After JSON decoding and runtime dictionary checks, `_dump` returns a value still inferred as
`Any & dict[Unknown, Unknown]` under ty rather than its declared `dict[str, object]`. The
focused ty check reports an unsound return statement, so S18 does not meet the repository's
required static-quality gate.

### s19-absence-coupling | medium | A test forbids the next planned manifest artifact

The real no-argument refusal test asserts that the S19 manifest path does not exist. S19 is
explicitly planned to create that exact artifact, so the test is guaranteed to fail as the
approved plan advances. S18 should prove safe default forwarding independently of temporary
campaign state; the successful real default rehearsal belongs to the later pilot proof.

### incomplete-powershell-skip | medium | Only probe-backed recipe executions honor missing PowerShell

The `uv_probe` fixture skips when `pwsh.exe` is unavailable, but real invalid-mode and
missing-manifest invocations bypass that fixture while still executing the PowerShell recipe.
On a host where `just` is present but PowerShell is absent, those tests fail for interpreter
availability instead of skipping consistently, so platform behavior is not isolated.

## Recommendations

Read dry-run rendering from its actual stderr stream while retaining the zero-exit and
no-authority assertions. Narrow or cast the validated JSON recipe mapping to the declared
typed shape so ty passes. Remove the assertion that the planned manifest remains absent;
exercise fail-closed missing-manifest behavior with an explicit nonexistent `--manifest`
argument or isolated fixture instead. Apply one shared PowerShell availability marker or
fixture to every test that executes the script recipe.

Preserve the suite's existing strong evidence: real recipe list and JSON dump, exact
doc/group/script/body/parameter contracts, captured no-argument argv equal to the CLI prefix
with no apply or receipt arguments, exact explicit forwarding, child exit code 23, and real
metacharacter arguments remaining a single CLI choice with exit two.

Add `-NoProfile` to the recipe-local PowerShell interpreter arguments and update the
JSON-dump contract. Add a detector proof using a temporary profile that defines a
conflicting `uv` command or visible sentinel, showing that the recipe ignores it.

## Validation

The focused run produced 13 passes and one failure in the dry-run stream assertion. Ruff and
Ruff-format passed; ty reported one unsound return statement in `_dump`. Final review status
is four medium findings and no critical, high, or low findings.

Current-byte re-review: `14 passed in 22.24s`; Ruff and basedpyright passed, Python
compilation passed, the live JSON dump matched the asserted recipe, and diff checking
passed. Final review status is one open medium finding (`powershell-profile`).
