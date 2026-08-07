# Dynamic import targets the public facade

## Rule

A deferred or circular-import workaround built on `importlib.import_module` (or
an equivalent runtime string-target import) is a SANCTIONED technique, but the
module string it names is bound by the same ownership rule as a static import:
it MUST name the owning package's public top-level facade, never a private
`_submodule`. The cycle-break technique is never the problem; an unqualified
private-module target is.

## Why

The AST import scanner cannot see a dynamically constructed module string, so
this class of violation is invisible to the automated gate and would otherwise
persist indefinitely inside an already-sanctioned pattern. Deferred helpers were
found targeting private submodules while public facades already re-exported the
same names; retargeting the strings closed it without touching the technique.
The technique and the target are independent concerns, and only the target is
governed by ownership.

## How

- **Good:** `importlib.import_module("cadrumo.domain.deadlines.taxpayer_model")`
  inside a deferred cycle-break helper — the string names the public facade.
- **Good:** `importlib.import_module("cadrumo.domain.contribuyente")` — the
  package's own top level.
- **Bad:** `importlib.import_module("cadrumo.domain.contribuyente._ccaa")` from
  outside that package — the technique is fine, the target is private.

Because the scanner cannot see string-built targets, this is author discipline:
read the target string exactly as if it were `from X import Y` and apply
`service-imports-via-top-level-reexports` to it.

## Source

ADR `2026-07-01-import-centralization-adr` (Ruling 6). Companion to
`service-imports-via-top-level-reexports`, the static-import rule this extends.
