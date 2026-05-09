---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline code. -->

# `calculation-truth-registry` `phase5` `step19`

Removed portal-owned modelo binding authority and moved filing portal lookup to
validated registry application links.

- Modified: `registry/aeat/modelos/130.toml`
- Modified: `src/aeat/domain/portals/_metadata.py`
- Modified: `src/aeat/domain/portals/_registry.py`
- Modified: `src/aeat/domain/portals/_entries/_common.py`
- Modified: `src/aeat/domain/portals/_entries/portal_m*.py`
- Modified: `src/aeat/domain/portals/test_modelo_cross_reference.py`
- Modified: `src/aeat/domain/portals/test_metadata.py`
- Modified: `src/aeat/domain/portals/test_registry.py`

## Description

Portal metadata now describes endpoints only. It no longer imports
`ModeloCode`, carries local modelo binding fields, or validates filing support
from portal entries. The `portals_for_modelo` lookup validates the calculation
registry, reads portal application links from the selected modelo definitions,
and then resolves those link consumers against the portal catalogue.

Modelo 130 now binds its filing portal through the registry TOML application
link. Portal tests were rewritten around that runtime behaviour instead of
asserting local portal-entry support coverage.

Portal behaviour tests now assert lookup through registry application links
rather than local portal-entry support coverage.

## Tests

- `uv run pytest src/aeat/domain/portals src/aeat/domain/calculations/registry -q`
- `uv run ruff check src/aeat/domain/portals src/aeat/domain/modelos src/aeat/domain/calculations/registry`
- `uv run ty check src/aeat/domain/portals src/aeat/domain/modelos src/aeat/domain/calculations/registry`
- `git diff --check -- src/aeat/domain/portals src/aeat/domain/modelos registry/aeat/modelos/130.toml`
