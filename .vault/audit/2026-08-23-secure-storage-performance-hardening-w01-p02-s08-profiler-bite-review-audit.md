---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:41968d7bf032f2ae8cb04b1ce4d9e9c98f0d96b5a94f153561a37c298abf5a27'
related:
  - '[[2026-08-22-secure-storage-performance-hardening-plan]]'
---

# `secure-storage-performance-hardening` audit: `W01.P02.S08 profiler bite review`

## Scope

Independently reviewed the uncommitted `W01.P02.S08` changes in
`src/cadrumo/tests/cli_performance.py` and
`src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py` against the
accepted campaign ADR, research, plan, and repository quality rules. The review
covered fresh-process timing of the planted work, source/store isolation,
registry-family attribution, filesystem attribution, root/group/leaf census
coverage, anti-tautology strength, platform behaviour, secret handling, and
scope containment.

## Findings

No open findings. Approved.

The external `sitecustomize` injector is loaded before the profiler module, but
its trace predicate fires only on entry to the real `__main__._resolve_cli_path`
or `__main__._invoke_cli` boundary. Both boundaries are entered after
`_child_main` snapshots `sys.modules` and the isolated storage tree, so the
planted registry import and storage writes are attributable in both independent
fresh processes. Root `--help` is a safe public invocation and still crosses
the `_invoke_cli` boundary before importing the CLI entrypoint.

The registry family now names the two live authority prefixes,
`cadrumo.application.registry` and
`cadrumo.domain.calculations.registry`; the planted import proves both are
observed after subtracting the independently measured control. Filesystem
evidence is exact for the planted directory and file and is corroborated by
native audit-event counters. Resolution and invocation operate on separate
clones, while the assertion over the source store proves neither child can
materialise the caller's fixture.

The census specimens independently plant an unclassified executable root, an
added nested group callback, and a leaf. The expected offending path is derived
from Typer registration and live walking rather than policy metadata or a
frozen command count. No mocks, monkeypatches, skips, allowlists, production
mutations, or threshold relaxations are present.

Verification evidence: the focused test module passed all nine selected unit
cases; the two fresh-process cases passed explicitly under `-m integration`;
`ruff check` and `ty check` passed for both scoped files. The integration cases
are enrolled by the repository's full integration lane rather than the default
unit-only pytest selection.

## Recommendations

No corrective action is required for `W01.P02.S08`. Preserve these planted
external-process proofs when the universal import and side-effect gates are
expanded in later campaign Steps.
