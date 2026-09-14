---
tags:
  - '#research'
  - '#canonical-exception-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:783036ad372f733d4d3657941d4f0d57287a3649a9a47b7ab53aa6869c480f91'
related:
  - "[[2026-09-14-canonical-exception-remediation-production-inventory-reference]]"
---

# `canonical-exception-remediation` research: `migration taxonomy`

The repository must choose whether Cadrumo-owned built-in exception roots remain local
acknowledgements or become registered failures. Rationale metadata leaves 67 owned
direct production roots and 13 newly reachable descendants without stable envelopes. Package-
owned registered classes, with external translation only where a protocol proves it,
are the only option that satisfies downstream machine-readable behavior.

## Findings

### Rationale metadata is not a failure contract

The repaired gate's rationale field makes source findings reviewable but gives a
failure no registry identity, category, retryability policy, translation key, or
serializable envelope. The live inventory in the related reference therefore remains
migration work, not an exemption catalogue. `CadrumoError.__init_subclass__` already
provides the binding point required for exact class-to-code ownership
(`src/cadrumo/core/errors/hierarchy.py:110`).

### Definitions remain package-owned

Moving concrete exceptions into a central facade would invert dependencies and make
callers import names away from their owning failure boundary. Each definition should
remain in its current narrow module and derive from `CadrumoError`, `CoreError`, or a
more specific registered package root. Only code declarations are centralized in the
existing layer registry shards (`src/cadrumo/core/errors/registry/declared_codes.py:15`).

### Catch compatibility must be explicit

Internal catches that currently rely on `ValueError`, `RuntimeError`, `KeyError`, or
another broad built-in should catch the migrated concrete type. Dual inheritance is
not justified by internal convenience. A built-in outward type is retained only where
a third-party callback contract requires it, with translation at that boundary and a
registered internal failure on the Cadrumo side.

The optional Playwright import is the only candidate found. When Playwright is
installed, its own `Error` class is used; when absent, the local fallback merely keeps
typed catch sites importable (`src/cadrumo/adapters/outbound/aeat/_playwright.py:46`).
It is not a Cadrumo-owned operational failure and should not become a registry alias.

### Retryability describes the same operation

Persistence provenance alone does not imply retryability. A code is retryable only
when repeating the same operation can succeed because time passes or another actor
releases the condition. The identified compare-and-swap/lock conflicts qualify;
malformed input, missing authority, integrity mismatches, and deterministic lookup
refusals do not (`src/cadrumo/core/errors/error_codes.py:86`).

### Registry closure includes descendants

Changing a bare parent to inherit from `CadrumoError` causes every unregistered
descendant to participate in import-time binding. The direct-root inventory therefore
expands to 80 new identities: 67 direct targets and 13 currently unregistered
descendants. Registering only the direct roots would make affected modules fail during
class creation rather than produce valid envelopes.

## Sources

- `src/cadrumo/core/errors/hierarchy.py:110`
- `src/cadrumo/core/errors/error_codes.py:86`
- `src/cadrumo/core/errors/error_codes.py:300`
- `src/cadrumo/core/errors/registry/declared_codes.py:15`
- `src/cadrumo/adapters/outbound/aeat/_playwright.py:46`
- `src/cadrumo/application/operations/persistence/journal.py:200`
