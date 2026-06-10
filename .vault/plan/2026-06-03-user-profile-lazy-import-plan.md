---
tags:
  - '#plan'
  - '#user-profile-lazy-import'
date: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-user-profile-lazy-import-adr]]'
  - '[[2026-06-03-user-profile-lazy-import-research]]'
---


# `user-profile-lazy-import` `Lazy user_profile package boundary via PEP 562` plan

### Phase `P01` - Instrumentation and probe

Establish the structural baseline before relocating any symbol: confirm the 69-submodule registry pull comes from aeat.application.user_profile importing aeat.domain.user_profile, capture the current red set in test_lazy_command_tree.py for a clean before/after diff, and land a producer-side probe that asserts import aeat.application.user_profile does not place aeat.domain.calculations.registry in sys.modules. The probe is the producer-side counterpart to the existing consumer-side gate and prevents future eager-import regressions at the boundary itself.

- [x] `P01.S01` - Capture the current red set from the lazy-loading discipline gate; `src/aeat/entrypoints/cli/test_lazy_command_tree.py`.
- [x] `P01.S02` - Trace the registry-pull chain from the application boundary down to aeat.domain.user_profile._registry_contract; `src/aeat/application/user_profile/__init__.py, src/aeat/domain/user_profile/__init__.py`.
- [x] `P01.S03` - Author a producer-side regression probe asserting import aeat.application.user_profile does not place aeat.domain.calculations.registry in sys.modules; `src/aeat/application/user_profile/test_lazy_boundary.py`.

### Phase `P02` - Lazy-thunk landing and verification

Relocate the Pydantic command and result models out of aeat.application.user_profile/__init__.py into a sibling _commands.py module, strip the top-level domain import from __init__.py, and extend the existing PEP 562 __getattr__ block to resolve the relocated classes and the four domain records on demand. The relocation lands in one atomic explicit-path commit per the aeat-architecture-boundaries symbol-relocation discipline. Verification confirms all five red tests in test_lazy_command_tree.py turn green, test_dispatching_a_subcommand_loads_its_module stays green, the producer-side probe added in P01 stays green, and no consumer of aeat.application.user_profile.* needs to change.

- [x] `P02.S04` - Relocate the Pydantic command and result classes plus the _PROFILE_SNAPSHOT_HASH_KWARGS constant into a new sibling module; `src/aeat/application/user_profile/_commands.py`.
- [x] `P02.S05` - Strip the top-level aeat.domain.user_profile import and the Pydantic model declarations from the package __init__.py while keeping the docstring, _register_language_resolver call, and __all__ intact; `src/aeat/application/user_profile/__init__.py`.
- [x] `P02.S06` - Extend the existing PEP 562 __getattr__ block to resolve the relocated command and result classes and the four domain records (UserProfileFact, UserProfileFactValue, UserProfileRecord, UserProfileStatus) on demand; `src/aeat/application/user_profile/__init__.py`.
- [x] `P02.S07` - Verify the lazy-loading gate is green end-to-end and no consumer required adjustment; `src/aeat/entrypoints/cli/test_lazy_command_tree.py, src/aeat/application/user_profile/test_lazy_boundary.py`.

## Description

This plan restores the lazy-loading discipline at the `aeat.application.user_profile` package boundary so the state-free CLI surfaces (`aeat`, `aeat --help`, `aeat --version`) stop transitively importing the registry. The decision recorded in the ADR is to extend the package's existing PEP 562 `__getattr__` dispatch to cover both the Pydantic command and result models (which currently sit in `__init__.py` body and pin the domain records as field types) and the four domain records they consume. The relocation moves the models into a sibling `_commands.py` module so Pydantic v2 field-type resolution at class-creation time stops dragging the domain layer in at boundary-import time.

The research document enumerates the boundary's re-export surface and traces the 69-submodule registry pull through `aeat.domain.user_profile._registry_contract`. The ADR captures the decision, the rejected alternatives (`TYPE_CHECKING` guard, package split, revert of the boundary-tightening commit), and the regression-gate contract: the existing `src/aeat/entrypoints/cli/test_lazy_command_tree.py` ratchet stays canonical, augmented by a new producer-side probe at the application-layer boundary.

## Steps







## Parallelization

Phase P01 and Phase P02 carry a hard ordering: P02 lands the relocation that flips the gate state from red to green, and the producer-side probe added in P01.S03 must be authored against the unfixed boundary so the probe itself is exercised against the regression before the fix. Within P01, the three Steps run sequentially because S02 depends on S01's evidence capture and S03 depends on S02's chain trace to know what assertion to encode. Within P02, S04 (relocate to `_commands.py`) and S05 (strip from `__init__.py`) belong in one atomic explicit-path commit per the `aeat-architecture-boundaries` symbol-relocation discipline; S06 (extend `__getattr__`) is part of the same commit because the strip and the extension must land together to keep the package's public surface unchanged. S07 (verification) runs after the commit lands and is the gate that promotes the plan to closed.

## Verification

The plan is verified complete when every one of the following checks is green:

- The five currently red tests in `src/aeat/entrypoints/cli/test_lazy_command_tree.py` pass: `test_version_cold_start_completes_under_budget`, `test_importing_cli_package_does_not_import_registry`, and the three parameterised instances of `test_state_free_surface_does_not_import_registry` (`["--version"]`, `["--help"]`, `[]`).
- `test_dispatching_a_subcommand_loads_its_module` in the same file stays green, proving on-demand import still wires up correctly through `__getattr__`.
- The producer-side probe authored in P01.S03 at `src/aeat/application/user_profile/test_lazy_boundary.py` asserts that `import aeat.application.user_profile` does not place any `aeat.domain.calculations.registry*` module in `sys.modules`, and passes.
- No file outside `src/aeat/application/user_profile/` is modified in the relocation commit (consumer code stays untouched per the ADR's "no consumer code changes" contract).
- `uv run --no-sync pytest --collect-only -q` is run immediately before the relocation commit and observed clean, per `aeat-architecture-boundaries` relocation atomicity.
- The fix carries no skip, xfail, mock, fake, or stub per `aeat-quality-gates`.

The plan is complete when every Step is closed (`- [x]`) and the verification checks above are confirmed green by the reviewer.
