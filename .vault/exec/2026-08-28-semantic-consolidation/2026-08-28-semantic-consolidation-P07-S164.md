---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f2b0b7dcf90cf4d370a062510c987d68af5a80387f39e0b6d6e46e0d5ebe2696'
step_id: 'S164'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the production code out of the four namespaces that are modules in disguise, and repoint the forwarded names at the modules that define them

## Scope

- `src/cadrumo/`

## Changes

- `A` `src/cadrumo/core/money/rounding.py`
- `A` `src/cadrumo/domain/notifications/sancion.py`
- `A` `src/cadrumo/application/bienes_inversion/_service.py`
- `A` `src/cadrumo/application/prorrata_register/_service.py`
- `M` four namespaces made inert; nine forwarded imports repointed at their defining modules
- `verify:` `pytest prorrata_register + bienes_inversion + notifications + money + domain siblings -n 0` -> 111 passed
- `verify:` `pytest` on the three edited consumer suites -> 24 passed
- `verify:` `--collect-only` -> 28915 collected, 6 errors, all pre-existing and peer-owned

## Notes

Four packages whose `__init__.py` held a real class: the namespace was doing the
work a named module should. The class moves to a named module in the same
package and the namespace goes inert.

Two of the four are not pure disguised modules. `bienes_inversion` and
`prorrata_register` BOTH define a service and forward an adapter repository, so
a consumer reaching `BienesInversionIvaRegisterRepository` through the namespace
is reaching past it into `adapters.persistence.profile`. A defined name and a
forwarded name look identical at the import site and must go to different
places, which is why the first attempt refused rather than guessing.

### The relocation was wrong three times, each time about depth

- The body was written one level deeper on the assumption that a module inside
  the package resolves relative imports differently from its `__init__`. It does
  not: level 1 means the containing package from both. Every relative import
  gained a dot it should not have.
- The forwarded-name repointing concatenated the consumer's own module segment
  onto the forwarded path, producing
  `....bienes_inversion.adapters.persistence.profile.bienes_inversion`.
- `__all__` was stripped by line prefix, and it is routinely a multi-line list,
  so the opening line went and the closing bracket stayed. Two files stopped
  parsing.

The nine broken imports were finally repaired by looking up where each symbol is
actually DEFINED and computing the depth from that, rather than by adjusting the
old path -- the difference between deriving the answer and patching the symptom.

### The check that was supposed to catch this could not

An over-deep relative import escapes the package root. The damage scan computed
an empty anchor for that case and skipped it, so `....core.identity` in a
four-part module read as clean. Every one of the nine was invisible to the
instrument watching for exactly this.

That is the third time this campaign that a checking instrument was blind to the
specific defect it existed to find. The pattern is consistent: the blind spot
sits in the branch that handles the DEGENERATE case, and the degenerate case is
what a wrong answer produces.
