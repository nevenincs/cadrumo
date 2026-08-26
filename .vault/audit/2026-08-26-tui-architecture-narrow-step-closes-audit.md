---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5d088fd4f134162c61beefeb5973c1dc611489ecd614ccff3be9bbb33bbe8bf6'
related: []
---

# `tui-architecture` audit: `Steps closed narrower than their row text`

## Scope

## Findings

## Recommendations

## Finding

Sixty execution records under this feature state that no source change was
needed. Audited against their own Step row text, five of those rows ask for
more than the record delivered.

The rows read "Retain X as public only for locally defined contract symbols and
direct-import every borrowed owner". The records verified only that the hard
move had landed and the retired private module was gone. The export surface was
never examined, so each module remained a re-export facade of exactly the kind
the architecture boundary forbids.

### Rows closed narrower than their text

- `W03.P20.S236` schema.py - 66 borrowed exports, marked complete
- `W03.P20.S229` record_design.py - 25 borrowed exports, marked complete
- `W03.P20.S191` export.py - 3 borrowed exports, marked complete
- `W03.P20.S232` relations.py - 1 borrowed export, marked complete
- `W03.P20.S181` bindings.py - 59 borrowed exports, still open
- `W03.P20.S227` queries.py - 13 of 14 exports borrowed; corrected in a second pass

`W03.P20.S193` export_value_policy.py was flagged and cleared: the detector
missed PEP 695 `type X = ...` statements and counted a locally defined alias as
borrowed.

## Remediation

S181, S191, S227, S229 and S232 now export only locally defined symbols. The one
real cross-module borrow, `WithholdingObservation` reached through `bindings`,
was repointed to its owner `withholding_bindings`. Removing the export lists let
ruff remove seventy-two imports that existed only to re-export.

S236 was corrected too: schema declared eighty-two names, sixty-six borrowed
from schema_base, schema_surfaces, schema_formula, schema_exports and
schema_references, reached by twenty-one modules. Each now imports from the
defining module. Five smaller lists followed, and the registry package now has
no module exporting a symbol it does not define.

A gate holds the property: `test_no_registry_module_exports_a_symbol_it_does_not_define`
in `test_public_api_boundaries.py`. It asserts its own denominator, which caught
a wrong root path while it was being written, and it was proved to bite by
planting a borrowed name.

## Lessons

An "already delivered at HEAD" close must be judged against every clause of the
row, not against the clause that first looks satisfied. A hard move landing is
not evidence that the export surface it left behind is correct.

Any "is this symbol defined here" walk must handle `ast.TypeAlias` alongside
FunctionDef, AsyncFunctionDef, ClassDef, Assign and AnnAssign. Omitting it
reports locally defined type aliases as borrowed and manufactures false findings.

A verification that reads a module's `__all__` without comparing it to what the
module defines cannot distinguish a contract from a facade.
