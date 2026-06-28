---
tags:
  - '#adr'
  - '#exception-restructure'
date: '2026-05-09'
modified: '2026-05-09'
related:
  - "[[2026-05-09-exception-restructure-research]]"
  - "[[2026-06-01-semantic-cluster-hardening-plan]]"
---

# `exception-restructure` adr: every domain error roots at AeatError via `_errors.py` convention | (**status:** `accepted`)

## Problem Statement

Domain-package exceptions accreted across the codebase under two
incompatible conventions: some packages name their error module
`errors.py` (`renta`, `iva`, `normatives`, `manuals`), others
already follow the underscore-prefixed package-private convention
`_errors.py` (`domain/_errors.py`, `attachments/_errors.py`,
`filing/reconciliation/_errors.py`, the adapter packages). The
inconsistency is invisible to runtime but visible to every reader
trying to locate the error surface of a domain package, and it
encodes an implicit signal that `errors.py` is part of the public
API while `_errors.py` is internal — a distinction the codebase
never actually relied on. A separate concern: the
`src/aeat/domain/_errors.py` module defines `DomainError` as a base
class with exactly one subclass (`DomainValidationError`) and no
direct usage anywhere in the tree. The class is a vestige of an
abandoned hierarchy plan.

## Considerations

Two conventions were weighed: rename every `errors.py` to
`_errors.py` for uniformity (the underscore-prefix convention used
elsewhere in `src/aeat`), or rename every `_errors.py` to
`errors.py` for "public-friendly" naming. The former is consistent
with the project's package-private file convention (every other
helper module uses an underscore prefix) and with the central error
registry's path-string references, which can be rewritten in one
sweep. The latter would require touching far more files for less
structural value.

For `DomainError`: three outcomes were considered. Delete it
outright (would orphan `DomainValidationError`'s inheritance chain);
re-parent `DomainValidationError` directly to `AeatError, ValueError`
(eliminates the intermediate class without losing functionality);
keep it as a "future hierarchy hook" (canonical metastate per
`metastate-zero-tolerance-adr` — rejected).

## Constraints

The central error registry (`core/errors/registry/_domain.py`) stores
fully-qualified import paths as strings. Every rename must include
the registry-path update in the same atomic commit per the
relocation-coordination convention. Test imports that touch the
error module by full path must move in the same commit; per-`.errors`
relative imports inside the domain package are simpler because the
new module name is the only delta. No re-export shims are
permitted (project rule `retire_means_delete_fully` and ADR Rule:
no compatibility layers).

## Implementation

Four atomic file renames, one commit per package, each combining
the canonical-site rename + every consumer update + the registry
path-string update:

- `src/aeat/domain/renta/errors.py` → `_errors.py`. Consumers:
  `renta/_maritime_exemption.py`, `renta/_ledger_expenses.py`,
  `renta/test_maritime_exemption.py`,
  `application/calculations/test_maritime_exemption_service.py`,
  registry entries at `core/errors/registry/_domain.py` lines 1030,
  1041, 1618, 1629.
- `src/aeat/domain/iva/errors.py` → `_errors.py`. Larger consumer
  surface across the iva package internals plus
  `iva/test_prorrata.py` and 14 registry entries.
- `src/aeat/domain/normatives/errors.py` → `_errors.py`. Consumers:
  `normatives/__init__.py`, `_lookup.py`, `_loader.py`,
  `_verify.py`, `_schema.py`, `core/resources/_repos/test_normatives.py`,
  registry entries at `_domain.py` lines 788, 799, 810, 1695.
- `src/aeat/domain/manuals/errors.py` → `_errors.py`. Consumers:
  `manuals/__init__.py`, `_verify.py`, `_schema.py`, `_rule_id.py`,
  `_loader.py`, `_fetch.py`, `test_verify.py`, `test_schema.py`,
  `test_loader.py`, `test_fetch.py`,
  `core/resources/_repos/test_manuals.py`, six registry entries.

`DomainError` is re-parented out: `DomainValidationError` becomes a
direct subclass of `AeatError, ValueError` in
`src/aeat/domain/_errors.py`; the unused `DomainError` class is
deleted from both the module and from the registry
(`core/errors/registry/_domain.py` line 1332). The deletion lands in
its own commit per the audit's separation request.

## Rationale

The `_errors.py` underscore-prefix convention is the project's
package-private convention everywhere else; aligning the four
holdouts to it is a one-shot consistency fix that future
contributors do not have to reason about. The atomic-commit rule
forces every move to land cleanly without a transitional
re-export shim, which the codebase rules forbid. Deleting unused
`DomainError` in a separate clearly-messaged commit makes the
removal auditable independently from the rename mechanics.

## Consequences

Every domain package will name its error surface `_errors.py`.
Future error-class additions follow the same convention without
need to re-litigate. The central error registry path strings stay
in lockstep because the rename commits update both sides. The
`DomainError` deletion removes one node from the error hierarchy;
`DomainValidationError` consumers see no behavioral change because
the inherited interface is identical. The semantic-cluster-hardening
plan W04 phase tracks the four renames + the DomainError deletion
as Steps S17–S22 + S23 verification gate.
