---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app registry boundary`

## Topic

Design the boundary for `aeat app registry`.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §4.5, the
app-live-shape ADR, current registry CLI code, registry/query modules,
workbook and parity commands, `audit-oracles`, live-read filed-data verbs, and
the config-doctor shape.

## Rewrite Scope

This research supports a child ADR that locks what stays under
`aeat app registry`, what moves to `aeat app live`, and what must not move to
`config doctor`. It also defines the output contract and no-shim clean-refactor
requirement.

## Findings

Apex §4.5 says app registry is evolving and names read-only registry verbs such
as `list`, `describe`, `casilla`, and `calculate`. That conflicts with current
static introspection ownership because `aeat app modelo` already owns static
registry introspection through `list`, `describe`, `casillas`, `bindings`, and
`formulas`.

The app-live-shape ADR accepts `aeat app live filed list`, `capture`, and
`capture-sources`. It keeps registry focused on inspection, verification,
oracle binding audits, workbook verification, and parity run/replay.

Config doctor diagnoses readiness only. Filed list/capture, NIF-IVA/TGVI
operational reads, and registry parity runs stay out of config doctor.

Current registry behavior mixes three concerns:

- Local registry authority and structural validation.
- Verification against official corpus, workbooks, and parity tapes.
- Live AEAT filed-declaration reads.

The current registry imports live AEAT session handling, sede declaration
traversal, and filed-observation persistence. Current filed-data verbs traverse
remote AEAT declaration registers and persist observations. The live helper
calls `require_live_read()` before authenticated session access.

## Boundary

Keep these commands under `aeat app registry`:

```text
aeat app registry inspect [--registry-root PATH] [--format json|text]
aeat app registry verify [--registry-root PATH] [--source-root PATH] [--format json|text]
aeat app registry audit-oracles [--registry-root PATH] [--environment production|test_environment|both] [--format json|text]
aeat app registry verify-filed-state --observation PATH [--source-observation PATH ...] [--registry-root PATH] [--source-root PATH] [--casilla ID ...] [--format json|text]
aeat app registry workbooks verify [--root PATH] [--limit N] [--per-file-timeout SECONDS] [--output PATH] [--resume-from PATH] [--format json|text]
aeat app registry parity run --scenario PATH [--registry-root PATH] [--source-root PATH] [--store-root PATH] [--output PATH] [--format json|text]
aeat app registry parity replay --tape PATH [--registry-root PATH] [--source-root PATH] [--format json|text]
```

Move these commands to `aeat app live`:

```text
aeat app live filed list --modelo MODELO --from-year YYYY --to-year YYYY [--format json|text]
aeat app live filed capture --modelo MODELO --year YYYY [--period PERIOD] [--expediente ID] [--limit N] [--format json|text]
aeat app live filed capture-sources --modelo MODELO --year YYYY --period PERIOD [--format json|text]
```

Keep these out of config doctor:

- Filed list and capture operations.
- NIF-IVA/TGVI operational reads.
- Registry parity runs.

## Output Contract

Commands use shared `--format` and `_emit` typed reports.

Per-command `--json`, manual `json.dumps`, and metric-only rendering are
removed.

## Migration Notes

Move `list_filed_data`, `capture_filed_data`, and `capture_source_filed_data`
out of `registry.py` into the app live filed implementation.

Keep the `require_live_read()` invariant before authenticated live reads.

Persisted captures use `live.filed.capture_created`.

Reject filed data under registry, doctor, and root live. Reject compatibility
aliases, legacy `--json`, and shims.

The clean refactor removes or moves old registry filed-data registrations in
the same change. Tests assert absence of old paths and presence of the new
grammar.
