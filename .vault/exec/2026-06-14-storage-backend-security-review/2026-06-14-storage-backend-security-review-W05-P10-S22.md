---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S22'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extend the namespace adoption gate to scan domain and adapters outbound in addition to application and ## Scope

- `src/aeat/application/tests/test_namespace_registry_adoption.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the namespace adoption gate to scan domain and adapters outbound in addition to application

## Scope

- `src/aeat/application/tests/test_namespace_registry_adoption.py`

## Description

- Rewrite the namespace-adoption gate (`test_namespace_registry_adoption.py`) to
  the cross-check enforcement: scan application + domain + adapters/outbound and
  require every `aeat.*` namespace string used as a secure-object namespace
  (assigned to a `*_NAMESPACE` target or passed as a secure-object call's
  `namespace`) to equal a value in `STORAGE_NAMESPACE_REGISTRY`.

## Outcome

The gate now enrolls the domain (and outbound, application) namespaces under the
registry authority across all three trees WITHOUT requiring an eager storage
import (which would break the json-pipe-safety lazy-import tests). A literal that
matches no registered namespace fails as drift; legitimate non-registry
`_NAMESPACE` constants (mirror sync-state keys, `"_probe"` markers) are not `aeat.*`
namespaces and are no longer over-flagged. Gate passes across the full codebase.
Committed in `a1175f9be`.

## Notes

This supersedes the original gate's "must import the constant" rule, which was
infeasible for the lazy domain modules. The named registry constants promoted in
S21 (`ea0a4c99d`) remain the authority the gate cross-checks against and are
available to any non-lazy consumer that wants the constant directly.
