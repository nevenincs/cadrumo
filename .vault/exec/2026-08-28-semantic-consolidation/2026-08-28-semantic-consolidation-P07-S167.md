---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:943348842e70de6aae06f7b75b5e30cd51541daaf9c01ebab82270fb0d19422a'
step_id: 'S167'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the six remaining clean disguised-module namespaces onto public modules and move their error-registry entries with them

## Scope

- `src/cadrumo/`

## Changes

- `A` `src/cadrumo/domain/contribuyente/inventory/records.py` (58 symbols)
- `A` `src/cadrumo/core/redaction/rules.py` (61 symbols)
- `A` `src/cadrumo/domain/bienes_inversion/register.py` (28 symbols)
- `A` `src/cadrumo/domain/prorrata_register/register.py` (26 symbols)
- `A` `src/cadrumo/domain/contribuyente/assets/records.py` (11 symbols)
- `A` `src/cadrumo/core/corpus_manifest/manifest.py` (26 symbols)
- `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `M` six namespaces inert; 183 consumers repointed
- `verify:` `pytest contribuyente + redaction + bienes_inversion + prorrata_register + corpus_manifest + errors -n 0` -> 692 passed, 0 import failures
- `verify:` `--collect-only` -> 28950 collected, 6 errors, all pre-existing and peer-owned

## Notes

These six had been skipped in an earlier pass as peer-modified. Re-checking
rather than repeating that claim showed the peers had since settled and all six
were clean. The stale reading, not the tree, was the blocker.

Every new module is named publicly, so a consumer in another package reaches a
public module rather than converting a namespace import into a cross-package
private one.

### The error registry moved with the classes, again

Four exception classes broke 606 collections the moment their namespaces went
inert, because the error-code registry keys `CadrumoError` subclasses by
fully-qualified module path and refuses an unregistered subclass at import time.

This is the second time in this campaign, after `core.topics`. It is worth
stating as a standing consequence rather than a surprise: relocating any
exception class is also a registry edit, and the registry is not discoverable
from the moved code -- nothing in `bienes_inversion` mentions it.

The refusal message is well built. It names the class, says what to do, and
explicitly raises the possibility that a concurrent process added the class
mid-flight, which in a shared tree is the difference between a real defect and
someone else's in-progress work.

### Scope check

Namespaces defining production code directly: 28 at the start of this campaign
segment, 11 now. What remains is `core` and `entrypoints/cli` -- both governed
by the open ruling in
`2026-08-31-semantic-consolidation-core-facade-ruling-conflict-audit` -- plus
`tests` fixtures packages and two packages whose consumers import submodules
rather than symbols.
