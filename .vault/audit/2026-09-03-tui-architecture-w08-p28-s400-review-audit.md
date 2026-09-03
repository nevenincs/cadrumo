---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_hash: 'sha256:bc85596b7100061261ae8076f3405f8624d8eeef0c1170dbd565a41e47859a87'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

Reviewed W08.P28.S400 in `application/workbench_generation.py`, its focused
application tests, the launcher generation adapter, and the installed child
entry path against the exact plan wording.

## Findings

### production-provider-absent | high | The child-owned provider does not compose production authorities

Open. `InstalledWorkbenchGenerationSourcesV1` is a collection of six injected
callbacks that already return application inputs or projections. Neither it
nor the launcher binds secure profile repositories to the canonical Ledger,
Declarations, calendar, AEAT Sync, Modelo, and Home projectors. The bare module
still calls `main` without a root-input provider and therefore mounts the
honest uncomposed shell. This is a useful seam, but it does not satisfy the
step's requirement to build the production provider.

### generation-capture-not-coherent | high | Independent sequential readers have no common capture proof

Open. The provider calls the clock and six source callbacks independently.
There is no single read-door transaction, shared bucket admission, or
generation token proving that their results belong to the same profile and
capture boundary. The test proves call count and order only; it cannot detect
a profile or source change between calls.

### admission-projection-contradiction | high | The public generation accepts opposing route and source states

Open. `WorkbenchGenerationInputsV1` verifies only the three destination names.
It accepts an AVAILABLE admission with a locked, never-captured, or unavailable
source, and also accepts a refused admission with a populated projection. The
focused application fixture currently constructs the first contradiction.
The launcher adapter detects it later for three routes, but the defining
application contract can already emit an internally contradictory public
generation and search decision.

## Verification

Focused result: 12 tests passed. Ruff lint and format checks passed; ty passed;
basedpyright reported zero errors, warnings, and notes.

Final result: **NO-CLOSE**. S400 has a sound pure assembly seam, but the actual
production provider, coherent-capture authority, and defining-module admission
invariants remain unfinished. S398 remains dependent on those missing pieces.
