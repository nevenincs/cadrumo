---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `config doctor shape`

## Topic

Design the `aeat config doctor` diagnostics surface for the CLI workflow
redesign.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR, the bucket and
bucket-event ADRs, current config doctor command handlers, the diagnostics
application service, orphaned browser health CLI code, and secure-object
crypto/integrity/quarantine persistence code.

## Rewrite Scope

This research supports a child ADR that locks `aeat config doctor` grammar,
absorbs browser health, normalizes output rendering, and assigns
secure-object integrity and quarantine behavior to the config diagnostics
surface.

## Summary

`aeat config doctor` should be the single diagnostics surface for
configuration, runtime health, browser connectivity, secure-object
inventory, and secure-object integrity checks.

The redesigned CLI keeps the root shape exactly to `aeat config` and
`aeat app`. There is no root `aeat browser`, root `aeat doctor`,
compatibility alias, shim, or legacy browser health route. Storage diagnostics
and storage maintenance belong under `aeat config doctor`; they do not move
under `aeat app`.

## Live CLI Facts

Current mounted commands are:

```text
aeat config doctor
aeat config doctor logs [--lines N]
aeat config doctor quarantine [--yes]
```

`aeat config doctor --help` lists `logs` and `quarantine`.

JSON behavior is inconsistent:

- `aeat --format json config doctor` emits a typed `ConfigDoctorReport`.
- `aeat config doctor --format json` fails because `--format` is currently
  root-level only.
- `aeat --format json config doctor logs --lines 0` still emits text because
  `logs` ignores the active output format and does not use `_emit`.
- `aeat config doctor quarantine` refuses without `--yes`, but the refusal is
  plain text, not JSON.

Browser health is not mounted. The package exists under `entrypoints/cli/browser`,
but it is orphaned from root wiring and still uses legacy `--json`,
`emit_json_success("browser health", ...)`, and its own exit-code table.

## Backend Capabilities

`build_config_doctor_report()` already covers the core aggregate diagnostics
surface:

- Python/package/log path checks.
- Registry load.
- Workflow secure state load.
- Setup/profile/auth readiness.
- Secure-object decryptability across every populated namespace.

Secure-object integrity checking is real backend behavior, not a placeholder.
`SecureObjectRepository.list_namespaces()` feeds `probe_namespace_integrity()`,
which decrypts each encrypted payload with the current master key and counts
readable and unreadable rows.

Quarantine is also real backend behavior. `quarantine_unreadable_rows()` copies
unreadable encrypted rows into `secure_objects_quarantine`, then deletes them
from active `secure_objects`.

Crypto integrity is provided by AES-256-GCM with a 12-byte nonce, 16-byte tag,
and 32-byte key. `InvalidTag` becomes `DecryptionError("AES-256-GCM tag
verification failed")`. `decrypt_encrypted_bytes_column()` is the low-level
integrity probe.

## Drift And Contradictions

Browser health exists but is not absorbed into the supported diagnostics
surface. Keeping it as a separate CLI route would contradict the target root
grammar.

Doctor JSON output is currently manual `model_dump_json()`, not `_emit`.
Redesigned doctor commands need to use `_emit` so `--format json` behaves
consistently.

`doctor logs` lacks a JSON payload path.

Browser health still uses legacy `--json`; redesigned doctor commands must use
`--format json` only.

UX-019 is partially addressed. Aggregate doctor detection and overview warnings
exist, and `list_records()` is fault-isolated. Direct repository `load()` paths
still use `SecureObjectRepository.load()` and can surface decrypt failures
before the domain command can provide a tailored pointer to run
`aeat config doctor`.

Quarantine is a persisted mutation, but today it is not bucket-scoped, emits no
bucket events, and writes to a global `secure_objects_quarantine` table.

`setup_reset` also invokes quarantine, which conflicts with the target rule that
storage maintenance belongs under config diagnostics only.

## Proposed Grammar

```text
aeat config doctor [--format json|text]

aeat config doctor connectivity
    [--target browser|auth|sede|all]
    [--format json|text]

aeat config doctor integrity
    [--namespace NAMESPACE]
    [--format json|text]

aeat config doctor list <namespace>
    [--all|--unreadable]
    [--format json|text]

aeat config doctor quarantine
    [--namespace NAMESPACE]
    [--dry-run]
    --yes
    [--format json|text]

aeat config doctor logs
    [--lines N]
    [--format json|text]
```

The base command provides the summary and next actions.

`connectivity` absorbs browser health and future adapter probes.

`integrity` owns secure-object scans.

`list` provides drill-down inventory without creating app-scoped storage
maintenance commands.

`quarantine` is the only current mutation.

`logs` remains available, but must emit structured JSON through `_emit`.

## Output Contract

Every redesigned doctor command supports `--format json` through `_emit`.

Legacy `--json` is not retained on redesigned doctor commands.

Refusals and guardrails, including `quarantine` without `--yes`, honor the
active output format.

## Event Contract

Read-only diagnostics emit no bucket events.

Persisted diagnostics mutations emit bucket-scoped events in the same logical
transaction:

- `secure_object.quarantined`
- `secure_object.restored_from_quarantine`, if restore is added later
- `secure_object.repaired`, only if a real repair or rewrap backend exists
  later

`secure_object.quarantined` payload includes bucket id, namespace, count,
affected object refs or row ids, quarantine target, command context,
actor/source, and timestamp.

## Rejected Shapes

The following shapes are rejected for the redesign:

- Root `aeat browser`
- Root `aeat doctor`
- `aeat config doctor-logs`
- `aeat app doctor`
- `aeat app config doctor connectivity`
- `aeat app bucket`
- `aeat app quarantine`
- Other app-scoped storage-maintenance routes
- Legacy `--json` on redesigned doctor commands
- Compatibility aliases or shims for browser health
- `doctor repair` until an actual repair or rewrap backend exists

## Evidence Anchors

- Apex root/output/doctor requirements: apex lines 125, 138, 179, 327, 331,
  336, 744.
- Bucket ownership: bucket ADR lines 59, 103, 153.
- Bucket events: bucket-event ADR lines 64, 89, 91, 95.
- Current config doctor CLI: `_config.py:23`, `_config.py:31`,
  `_config.py:44`, `_config.py:58`, `_config.py:94`.
- Diagnostics backend: `application/diagnostics.py:107`,
  `application/diagnostics.py:222`, `application/diagnostics.py:245`,
  `application/diagnostics.py:272`, `application/diagnostics.py:340`,
  `application/diagnostics.py:352`.
- Browser health orphan: `browser/__init__.py:25`, `browser/health.py:50`,
  `browser/health.py:185`, `browser/health.py:211`.
- Secure-object integrity/quarantine: `secure_objects.py:130`,
  `secure_objects.py:147`, `secure_objects.py:248`, `secure_objects.py:328`.
- AES-GCM tag verification: `_crypto.py:32`, `_crypto.py:35`,
  `_crypto.py:38`, `_crypto.py:136`, `_crypto.py:166`.
