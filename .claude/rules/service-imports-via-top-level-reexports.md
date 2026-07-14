---
name: service-imports-via-top-level-reexports
trigger: always_on
---

# Service imports via top-level re-exports

## Rule

Every cross-package import project-wide MUST resolve to the SOLE canonical
public top-level ``__all__`` facade of the symbol's owning package; a
cross-package consumer MUST NEVER import from another package's private
``_module`` (ownership of ``A.B._C...`` is ``A.B``). Intra-package private
imports and a package building its own facade out of its own private modules
are fine. When the symbol is not yet exported, promotion to ``__all__`` is a
precondition of the consuming change, not a follow-up: add the symbol to the
owning package's ``__all__`` (eager ``from .module import Name`` by default;
lazy ``__getattr__`` / PEP 562 ONLY if the owning package already uses that
pattern or an eager import risks a circular-import cost — never retrofit an
existing eager facade to lazy). Never mechanically rename a private ``_name``
straight into ``__all__``; per-symbol, either rename-to-public and promote a
genuinely shared primitive, or expose a narrower purpose-built public API for a
single caller's need, or treat the reach as a design defect to remove. A
single DOCUMENTED non-``__init__`` public re-export bridge module (a stated,
one-line-docstring purpose) is an acceptable canonical source; an undocumented
pure-reexport shim is not.

## Why

Per `2026-07-01-import-centralization-adr` (Rulings 1-4), letting one consumer dot
into a package's internals reads to every later consumer as permission to do the
same; the `2026-07-01-import-centralization-research` scan quantified 2465
cross-package private imports across 250 files plus a naming collision and three
latent violations hidden in a circular-import workaround. The constraint is
ownership-first, promotion-before-rewrite, one canonical facade per symbol, enforced
by the project-wide AST scanner `dev/import_hygiene_scan.py` and CI gate
`src/cadrumo/tests/test_import_hygiene_gate.py` (ratcheting a checked-in production
baseline toward zero; Family-2 documented-bridge allowlist and Family-3 pinned-symbol
set are structural data).

## How

- **Good:** a new ``cadrumo.application.bucket_maintenance`` service imports
  ``rename_profile`` from ``cadrumo.application.user_profile`` (the package
  ``__all__`` re-export), promoted before the service file was authored; the six
  documented non-``__init__`` bridge modules — ``registry/applicability.py``,
  ``deadlines/taxpayer_model.py``, ``transactions/_ids.py``, ``cli/_schemas.py``,
  ``outbound/aeat/_playwright.py``, ``workflow/_utils.py`` — remain acceptable
  canonical sources under Ruling 4.
- **Good:** an underscore-named symbol reached by two or more unrelated production
  packages is renamed to public and promoted to ``__all__`` (Ruling 3.i); one
  reached by exactly one narrow caller instead gets a purpose-built narrower public
  API (Ruling 3.ii), never a blanket ``_foo`` -> ``foo`` rename.
- **Bad:** ``from ....application.user_profile._orchestration import rename_profile``
  (dotting into a private submodule) — the next agent reads the precedent and
  erodes the boundary; or an undocumented pure-reexport shim invented to avoid a
  proper facade promotion (only the named documented bridges count under Ruling 4).
- **Bad:** mechanically stripping the leading underscore from every reached private
  symbol into ``__all__`` without judging shared-primitive vs single-caller vs
  design-defect — the blanket promotion Ruling 3 forbids.

## Status

Active; generalized project-wide. Supersedes the prior narrower "new application-layer
service" scope, now the first `Good` worked example.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr``; generalized by
``2026-07-01-import-centralization-adr`` (research ``2026-07-01-import-centralization-research``).
Enforced by ``dev/import_hygiene_scan.py`` and ``src/cadrumo/tests/test_import_hygiene_gate.py``.
