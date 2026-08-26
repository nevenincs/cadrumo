---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fdc480c7a8281c6f9e847e9ba8e8239d773e01d88f43ff6f24744acbeb5b5ba4'
step_id: 'S160'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Extend the sole public application/modelo/work_addressing.py defining module with the work-only native atomic capture/current-coordinate pair over the canonical visible or exact operand that returns the strict frozen ModeloWorkResolution, native generation, and neutral opaque physical-scope/process comparison domain, migrate every production, S126-registration, test, dynamic, and tooling consumer to direct imports from that module, compose implicit pointer and one-record catalogue coordinates with bounded retry/currentness and an injective order-preserving generation, preserve the explicit catalogue generation while excluding the pointer limb, keep physical root, bucket, namespace, and key identity private, and prove pointer/catalogue ABA, same-observation singleflight, distinct-root independence, defining-module ownership, and zero registry access, second read, Workspace dependency, package binding, shim, alias, fallback, bridge, or re-export

## Scope

- `src/cadrumo/application/modelo/work_addressing.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate`
- `every affected production/S126-registration/test/dynamic/tooling consumer`
- `and focused work-capture/root/pointer concurrency and direct-import tests`

## Changes

- `M` `src/cadrumo/application/modelo/work_addressing.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_addressing.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_work_addressing.py -n0` -> `pass`

## Notes

The tree-wide `dev/tests/test_import_hygiene_gate.py` is red on five
assertions about stale test-debt entries that no longer answer a live reach
(`application/auth/tests/test_diagnostics.py`, `application/modelo/tests/
test_actions.py`, `application/modelo/tests/test_participation_co_emission.py`
and others). Those entries belong to unrelated modules and went stale through
concurrent relocations; this Step adds no cross-package underscore reach. The
inert-namespace requirement this Step names is proven directly by
`test_work_capture_contract_is_owned_by_its_defining_module`.

During this Step the bundled registry was transiently invalid at HEAD
(`modelo 200 revision 2024: construct 'modelo-200-2024-foundation' does not
include legal refs ['ley-49-2002:art-20']`), which failed every
registry-touching test in the module. A re-run after the tree settled was
fully green.
