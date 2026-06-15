---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S21'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Route every domain and outbound secure-object namespace literal through its STORAGE_NAMESPACE_REGISTRY definition constant

## Scope

- `src/aeat/domain/`

## Description

- Route the `adapters/outbound/` secure-object namespace literals through their
  registry definitions: LLM cache/usage, Google OAuth client/token/metadata +
  Drive config, and the AEAT sede filed-declaration artefacts/observations + IVA
  wallet observations. Each local constant now derives from
  `<DEFINITION>.namespace`.

## Outcome

PARTIAL + CORRECTED. Two pieces landed:
1. Outbound subtree literals routed through the registry constants (committed
   `1a06c2e47`).
2. The `aeat.domain.*` namespace definitions promoted from anonymous inline tuple
   entries to named, exported module-level constants (committed `ea0a4c99d`; 35
   registry + smoke tests green) so they are addressable by the gate and by
   non-lazy consumers.

CORRECTION TO THE AUDIT FINDING (HEAD-verified): the audit's prescribed fix
("route each domain repository's namespace literal through the registry
constant") is INFEASIBLE for the domain modules and was NOT applied. Those
repositories (transactions, invoices, submission, filing, modelos, etc.)
deliberately DEFER all `aeat.adapters.persistence.storage` imports (inside
`TYPE_CHECKING` / function bodies) to preserve the json-pipe-safety contract: a
module-level `from ...storage import <CONSTANT>` would eagerly trigger the heavy
storage `__init__` (Alembic plugin discovery) and break the import-isolation tests
(`test_lazy_boundary.py`, `test_lazy_command_tree.py`, `test_wizard_catalogue.py`).
The namespace literal is duplicated precisely to avoid that eager import. So the
literal must STAY; the correct enforcement is a gate that CROSS-CHECKS each domain
literal against the registry namespace values (no drift) rather than requiring a
constant import.

STEP OPEN for the corrected remaining work (folds into S22): refine the adoption
gate to (a) recognise a string literal that equals a registry-declared namespace
value as compliant, and (b) restrict the "must come from registry" check to
non-lazy modules, so it stops over-flagging the lazy domain literals and the
legitimate non-registry `_NAMESPACE` constants (mirror keys, `"_probe"`).


## Notes

GATE BLOCKER for S22: extending the adoption gate to scan `adapters/outbound`
(and `domain`) is not clean as-is — the gate's third heuristic ("namespace
constant must come from storage registry") over-flags legitimate non-registry
`*_NAMESPACE` constants present in outbound (mirror-manifest sync-state keys,
`"_probe"` markers) and likely domain too. The gate needs refining (restrict the
check to constants actually passed as secure-object namespaces whose string
matches a registry namespace value) before the scope can widen without redding
the build. Tracked as part of S22.
