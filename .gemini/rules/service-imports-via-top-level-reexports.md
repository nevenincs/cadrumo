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

The BucketMaintenanceService composition pattern landing on 2026-06-03 first
surfaced the consequence of letting one consumer dot into a package's
internals: every later consumer reads the precedent as permission to do the
same. The `2026-07-01-import-centralization-research` scan then quantified the
cost of leaving the constraint scoped to "new application-layer services": 2465
cross-package private imports (866 production, 1599 test) across 250 files and
34 owning packages, plus a genuine naming collision
(`_withholding_observations_repository.py` masking two distinct M180/193 vs
M190 stores) and three latent Ruling-1 violations hiding inside a legitimate
circular-import workaround. The `2026-07-01-import-centralization-adr`
(Rulings 1, 2, 3, 4) generalized the constraint project-wide: ownership-first,
promotion-before-rewrite, one canonical facade per symbol, with the
promotion-mechanism and underscore-judgment detail this rule now carries.
Enforcement moved from a single regression test pinning one package's surface
to the project-wide AST scanner `dev/import_hygiene_scan.py` and its CI gate
`src/aeat/tests/test_import_hygiene_gate.py`, which ratchets a checked-in
production baseline toward zero and treats the Family-2 documented-bridge
allowlist and the Family-3 pinned-symbol set as structural data.

## How

- **Good:** a new ``aeat.application.bucket_maintenance`` service imports
  ``rename_profile`` from ``aeat.application.user_profile`` (the package
  ``__all__`` re-export). The symbol was promoted to that surface before the
  service file was authored.
- **Good:** a cross-package consumer that needs
  ``domain.modelos.CalculationRevision`` imports it from ``domain.modelos``
  directly, never from ``application.modelo`` even though the app-layer
  package used to re-export it — the ADR's Ruling-5 umbrella RETIRE makes the
  domain package the sole canonical source once a duplicate re-export is
  identified.
- **Good:** ``registry/applicability.py``, ``deadlines/taxpayer_model.py``,
  ``transactions/_ids.py``, ``cli/_schemas.py``,
  ``outbound/aeat/_playwright.py``, and ``workflow/_utils.py`` are documented
  non-``__init__`` bridge modules and remain acceptable canonical sources
  under Ruling 4 — a consumer importing from one of these is not a violation.
- **Good:** an underscore-named symbol reached by two or more unrelated
  production packages is renamed to public and promoted to ``__all__``
  (Ruling 3.i); one reached by exactly one narrow caller instead gets a
  purpose-built narrower public API (Ruling 3.ii) rather than a blanket
  ``_foo`` -> ``foo`` rename.
- **Bad:** a service file imports ``from ....application.user_profile._orchestration
  import rename_profile`` (dotting into the private submodule). The next agent
  who needs the same symbol reads the precedent and does the same; gradually
  the package boundary is eroded.
- **Bad:** mechanically stripping the leading underscore from every reached
  private symbol and adding it to ``__all__`` without judging whether it is a
  shared primitive, a single-caller need, or a design defect — this is the
  blanket promotion Ruling 3 forbids.
- **Bad:** an undocumented pure-reexport shim module invented to avoid a
  proper facade promotion — only the six named, documented bridges (plus any
  future one authored with the same one-line-docstring discipline) count as
  canonical sources under Ruling 4.

## Status

Active; generalized project-wide. Supersedes the prior narrower scope ("a new
application-layer service"), which is now a worked example (the first `Good`
entry above) of the project-wide Ruling-1 ownership policy rather than the
rule's full scope.

## Source

Operator directive recorded 2026-06-03 during the BucketMaintenanceService
composition-pattern landing on the ``chore/eliminate-shims`` branch (backing
ADR ``2026-06-03-cli-workflow-redesign-adr``; research
``2026-06-03-cli-workflow-redesign-research``; exec record
``2026-06-03-cli-workflow-redesign-exec``). Generalized project-wide by ADR
``2026-07-01-import-centralization-adr`` (Rulings 1, 2, 3, 4), research
``2026-07-01-import-centralization-research``. Enforced by
``dev/import_hygiene_scan.py`` and ``src/aeat/tests/test_import_hygiene_gate.py``.
