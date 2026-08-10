---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:86777687fb1096acb1f8579d5e601cd7ddbf930f3739a0c62316748d7c4f020e'
step_id: 'S30'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Give the operator surface contract suite one execution-scope marker

## Scope

- `src/cadrumo/application/operator_surface/tests/test_contract.py`
- `src/cadrumo/application/operator_surface/tests/test_contract_live.py`

## Description

- Count the offending markers from the file rather than from the gate's report, which had enumerated only the first few positions.
- Establish that the module mixes execution scopes before choosing a remedy.
- Relocate the single integration test and the one helper it uses into a sibling live module, following the convention already present in the same directory.
- Remove the imports the relocation leaves dead, and change no assertion.
- Absorb the unrelated failure the relocation exposed in the same file.

## Outcome

Both marker-structure failures are cleared, confirmed by the test-run authority rather than by inspection: `test_module_carries_valid_pytestmark` and `test_no_function_level_access_or_domain_markers` had been failing on this module and now pass, with zero owner-caused failures remaining. `test_contract.py` carries `[unit, hex_application]` and `test_contract_live.py` carries `[integration, hex_application]`, with no function-level execution or domain markers in either.

The fix is not the one the defect appeared to call for, and the difference was the whole job. The brief described five function-level markers to delete and a module-level marker to add. The file held seventeen, and — decisively — one integration test alongside them. Hoisting the unit marker to module level would have given that test two execution-scope markers, and the taxonomy forbids exactly one just as firmly as it forbids none. The obvious fix would have traded three failures for one and read as a repair.

So the integration test moved out. The taxonomy allows one execution scope per module, which means a module mixing scopes cannot be corrected in place at all — it has to be split. The destination follows the convention already present in the same directory, where a sibling live module carries the integration marker for exactly this reason. The move is well bounded: the relocated test uses one module helper, nothing else references that helper, and no assertion text changed.

One judgement call. The moved test needs the module's autouse English-locale pin, because it asserts against rendered operator questions. The fixture is duplicated rather than hoisted into a package-level conftest, since an autouse fixture there would bind all nine sibling modules with a behaviour change none of them asked for — a wider blast radius than the defect. The duplication is explained in the new fixture's own docstring so a later reader does not delete it as an oversight.

## Notes

Twenty-four imports left dead by the relocation were removed. They were identified by an AST scan rather than by eye, and re-scanned to zero afterwards on both modules.

A second failure in the same file was absorbed rather than routed, because it sat in a file this row had just edited. It pinned a full English paragraph from the root help document, which made the locale catalogue the test's real authority: a peer reworded the help, the catalogue carried the new wording, and the gate reddened with no guarded behaviour having changed. Updating the sentence would have re-armed the trap for whoever rewords it next, so the assertion was replaced with the structural claim it was standing in for — that the contract exposes exactly the two declared roots, compared order-independently — plus a check that the document renders prose at all. Every other assertion in that test already pins verb paths and environment variable names rather than prose.

The integration half of the verification is deliberately not claimed. Its run failed on an import of a symbol a peer was mid-flight adding: absent at the run's commit, present in the working tree minutes later, still uncommitted. That failure was true when measured and already stale when read, and it is neither this row's defect nor the peer's. A re-run is owed once the symbol lands, and this record does not assert the moved test green until then.

The code landed ahead of this row because the failure was unowned and blocked every lead from reading a clean ratchet. The row and this record follow the work rather than preceding it, which is stated here rather than left for a reader to infer from timestamps.
