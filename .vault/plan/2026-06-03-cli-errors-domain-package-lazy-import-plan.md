---
tags:
  - '#plan'
  - '#cli-errors-domain-package-lazy-import'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-cli-errors-domain-package-lazy-import-adr]]'
  - '[[2026-06-03-cli-errors-domain-package-lazy-import-research]]'
  - '[[2026-06-03-user-profile-lazy-import-adr]]'
---


# `cli-errors-domain-package-lazy-import` `Lazy domain-package boundary execution` plan

### Phase `P01` - make the domain-package boundary lazy

Convert aeat.domain.user_profile/__init__.py to dispatch UserProfilePortableExport through PEP 562 __getattr__ and land the producer-side probe.

- [x] `P01.S01` - convert to dispatch UserProfilePortableExport via module-level __getattr__ (PEP 562); `src/aeat/domain/user_profile/__init__.py`.
- [x] `P01.S02` - add producer-side regression probe asserting fresh-interpreter import places zero registry modules; `src/aeat/domain/user_profile/test_lazy_boundary.py`.

### Phase `P02` - verify the CLI gate is green end-to-end

Run the CLI lazy-command-tree gate plus the producer probes to confirm 6/6 green and the application-package boundary is preserved.

- [x] `P02.S03` - run pytest test_lazy_command_tree and confirm 6/6 green; `src/aeat/entrypoints/cli/test_lazy_command_tree.py`.
- [x] `P02.S04` - re-run application-side probe to confirm parent boundary preserved; `src/aeat/application/user_profile/test_lazy_boundary.py`.
- [x] `P02.S05` - re-run cli suite and confirm no new reds beyond pre-existing baseline; `src/aeat/entrypoints/cli`.

## Description

Successor execution to the application-package boundary fix that landed under the parent ADR. The parent ADR's accepted scope made `aeat.application.user_profile` lazy-by-default via PEP 562 dispatch and the producer probe at `src/aeat/application/user_profile/test_lazy_boundary.py` confirms that contract. The CLI-side gate at `src/aeat/entrypoints/cli/test_lazy_command_tree.py` remains red for all five state-free-surface tests because the leak vector is one layer deeper than the parent ADR's scope: the eager re-export of `UserProfilePortableExport` from `aeat.domain.user_profile/__init__.py` (which transitively pulls `aeat.domain.modelos._calculation_revision`, which imports the registry at module scope).

The successor ADR adopts Pattern (a) / (E) - lazy domain-package boundary via PEP 562. The fix mirrors the parent ADR's mechanism one layer down the import graph: dispatch `UserProfilePortableExport` through a module-level `__getattr__` while keeping every lightweight re-export (errors, values, schema, loader, registry-contract) eager. No consumer code changes; the public surface is unchanged. The producer-side regression probe lands in the same atomic commit.

## Steps







## Parallelization

Phase `P01` and Phase `P02` are sequential: `P02` runs the gate that confirms `P01` met its contract. Within `P01`, `S01` and `S02` are designed to land atomically in one commit (the source change and the producer-side probe share a single explicit-path commit per the relocation-atomicity clause), so they are not run as independent units. Within `P02`, `S03`, `S04`, and `S05` are independent test invocations that may run in parallel; verification is complete only when all three are green.

## Verification

The plan is complete when every Step closes against a verifiable gate:

- All six tests in `src/aeat/entrypoints/cli/test_lazy_command_tree.py` are green (the five originally-red state-free-surface tests plus `test_dispatching_a_subcommand_loads_its_module` which must remain green).
- The producer-side probe at `src/aeat/domain/user_profile/test_lazy_boundary.py` passes: a fresh-interpreter `import aeat.domain.user_profile` places zero `aeat.domain.calculations.registry*` modules in `sys.modules`.
- The producer-side probe at `src/aeat/application/user_profile/test_lazy_boundary.py` continues to pass: the parent campaign's application-package boundary is preserved.
- The CLI suite under `src/aeat/entrypoints/cli/` shows no new reds beyond the pre-existing baseline at the start of this campaign.
- The relocation lands as one atomic explicit-path commit per the `aeat-architecture-boundaries` symbol-relocation atomicity clause.
