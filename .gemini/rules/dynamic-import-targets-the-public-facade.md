---
name: dynamic-import-targets-the-public-facade
trigger: always_on
---

# Dynamic import targets the public facade

## Rule

A deferred / circular-import workaround built on `importlib.import_module` (or
an equivalent runtime string-target import) is a SANCTIONED technique, but the
module string it names is bound by the SAME ownership rule as a static import:
it MUST name the owning package's public top-level facade — or a documented
Ruling-4 bridge module — never a private `_submodule`. The cycle-break
technique is never the problem; an unqualified private-module target is.

## Why

ADR `2026-07-01-import-centralization-adr` (Ruling 6) found
`core/setup_answers.py`'s deferred `_m()` and `_ccaa()` helpers used
`importlib.import_module` to legitimately break an import cycle, but targeted
private submodules — `cadrumo.domain.deadlines._models` and
`cadrumo.domain.contribuyente._ccaa` — when public facades already re-exported
the same names (`cadrumo.domain.deadlines.taxpayer_model`,
`cadrumo.domain.contribuyente`). Because the AST-static import scanner
(`dev/import_hygiene_scan.py`) cannot see a dynamically constructed module
string, this class of violation is invisible to the automated gate and would
otherwise persist indefinitely inside an already-sanctioned cycle-break
pattern. The fix retargeted the strings to the public facades and closed the
gap as an ordinary Ruling-1 violation, without touching the deferred-import
technique itself — proof that the technique and the target are independent
concerns, and only the target is governed by ownership.

## How

- **Good:**
  `importlib.import_module("cadrumo.domain.deadlines.taxpayer_model")` inside a
  deferred cycle-break helper — the module string names the public facade.
- **Good:** `importlib.import_module("cadrumo.domain.contribuyente")` — the
  package's own top level, not a private submodule path appended to it.
- **Bad:** `importlib.import_module("cadrumo.domain.deadlines._models")` from
  outside the `deadlines` package — the technique is fine, the target is a
  private submodule of a package that already exports the same symbols
  publicly.
- **Bad:** `importlib.import_module("cadrumo.domain.contribuyente._ccaa")` for the
  same reason — retarget to the owning package's public facade.

Because the scanner cannot see these string-built targets, this rule is author
discipline: when writing or reviewing a deferred/dynamic import, read the
target string exactly as if it were a static `from X import Y` and apply
`service-imports-via-top-level-reexports` to it.

## Source

ADR `2026-07-01-import-centralization-adr` (Ruling 6), research
`2026-07-01-import-centralization-research`. Companion to
`service-imports-via-top-level-reexports` (the static-import ownership rule
this rule extends to dynamic targets).
