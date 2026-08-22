---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:27a09a2511e6fca7128bc9b2170b05c31b438d41651e561232ff8f45880e09d0'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-research]]"
---

# `source-casilla-integration` audit: `W01 P01 S04 core facade review`

## Scope

Reviewed commit `a31df525b9` against `W01.P01.S04`, the accepted source-casilla
integration decision, and the core-facade ownership rules. The review covered
only the public-surface additions in `src/cadrumo/core/__init__.py`; the execution
record and plan checkbox were inspected for scope leakage but were not treated
as implementation.

The owner module's sixteen public names exactly match the sixteen names added to
the core facade and its lazy-export map. Fresh-interpreter imports, owner/facade
object-identity checks, duplicate detection, lazy target checks, the focused
early-initialisation and facade-export tests, Ruff, compilation, and diff
whitespace checks all passed. The change introduces no eager import, private
cross-package import, bridge module, or test work belonging to `W01.P01.S05`.

The broader core suite completed with 1,519 passes and eight failures unrelated
to the reviewed diff. The import-hygiene gate likewise reports pre-existing
test-only private-import census drift (110 current sites against 69 documented);
the reviewed commit adds no import statement or consumer site, so that baseline
debt is not attributed to `W01.P01.S04`.

## Findings

No findings. In particular, there are no HIGH or CRITICAL findings blocking
`W01.P01.S05`.

## Recommendations

Proceed to `W01.P01.S05`. Keep the existing unrelated import-hygiene and core
suite failures assigned to their owning campaigns; do not expand this facade
step to absorb them.
