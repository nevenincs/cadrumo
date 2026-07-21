---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S319'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# standardise explicit --json flag across CLI verbs

## Scope

- `today _emit_envelope and _emit handle JSON internally without a visible signature parameter`
- `expose --json explicitly so operators know per-verb whether structured output is available`
- `document the flag in --help text`
- `src/aeat/entrypoints/cli/`

## Description

Verify-close as satisfied-by-the-global-option, with the per-verb variant explicitly rejected. The Step's premise — that structured output is invisible per verb — is answered at HEAD by a single uniform mechanism, and the fix it proposes would degrade that mechanism.

- Confirm a uniform global `--format` option is declared once on the root Typer callback in `src/aeat/entrypoints/cli/__init__.py`, setting the output format on the shared context state that `_emit` / `_emit_envelope` read in `_common.py`. It applies identically to every leaf verb: `aeat --format json app ...` selects the JSON `SchemaEnvelope` spine for any command, and the whole test suite exercises structured output through this one global flag.
- Reject the Step's proposed per-verb `--json` boolean. Adding a `--json` flag to each of the ~100 verbs would fragment the single uniform output surface, create two independent ways to request JSON (the global `--format json` and a per-verb `--json`), and contradict the two-root, single-surface CLI architecture. Coordinator-confirmed: this is an anti-pattern; do not build it.

## Outcome

No code change. The Step's intent — operators can access structured output uniformly — is already satisfied by the global `--format json` option, which is the standardised surface (more standardised than per-verb flags, not less). The per-verb `--json` variant is explicitly declined as fragmentation. Any future need for per-verb `--help` discoverability of structured output is a separate design decision (an ADR), not this Step. The plan checkbox is deferred to the coordinated plan-reconciliation pass.

## Notes

This is a design-disposition verify-close: the Step as literally worded proposes a change that would regress the architecture, so it closes as intent-satisfied-by-global-option rather than by implementing the per-verb flag.
