---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b4fed9be1b16bb9b73aab0aa5368a77e86933f21ceba788e4accc152e03b2e1b'
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

S236 (schema.py, 66) is not yet corrected.

## Lessons

An "already delivered at HEAD" close must be judged against every clause of the
row, not against the clause that first looks satisfied. A hard move landing is
not evidence that the export surface it left behind is correct.

Any "is this symbol defined here" walk must handle `ast.TypeAlias` alongside
FunctionDef, AsyncFunctionDef, ClassDef, Assign and AnnAssign. Omitting it
reports locally defined type aliases as borrowed and manufactures false findings.

A verification that reads a module's `__all__` without comparing it to what the
module defines cannot distinguish a contract from a facade.
