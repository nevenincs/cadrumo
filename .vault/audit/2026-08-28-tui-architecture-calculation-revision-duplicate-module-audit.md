---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b55d4b20bd6f4688552e32fbfb1c3b7a027be23a4d8751a9386a63e195503238'
related: []
---

# `tui-architecture` audit: `An incomplete relocation left an unimportable duplicate module with two live CLI references`

## Finding

`domain/modelos/_calculation_revision.py` and
`domain/modelos/calculation_revision.py` are two near-duplicate modules — 1662 and
1680 lines — that define the same classes. The private one **cannot be imported at
all**, and two live CLI value contracts still name it.

## Proof

Importing the private module raises at class-definition time:

```
>>> import cadrumo.domain.modelos._calculation_revision
ValueError: CadrumoError subclass
cadrumo.domain.modelos._calculation_revision.LedgerFilingCoverageError is missing
a declared ErrorCode registry entry
```

`CadrumoError.__init_subclass__` calls `bind_error_code(cls)`, which refuses a
subclass with no registry entry. The registry declares the error once, at
`core/errors/registry/_domain_part2.py:661`, under the **public** path
`cadrumo.domain.modelos.calculation_revision.LedgerFilingCoverageError`. The
private copy of the same class has no entry, so defining it raises and the module
is unimportable.

That entry is the only one in the registry spelling a `domain.modelos` module
without a leading underscore; the registry references private modules freely
elsewhere (`_repository`, `_calculation_repository`, `_participation_index`,
`_filing_repository`, `_row_models`, `_verification_repository`). So the registry
is not inconsistent — it is pointing at the module the relocation intended to
survive.

## The live consequence: two unresolvable CLI value contracts

`entrypoints/cli/_modelo_core_command_specs.py` declares:

```python
_AMENDMENT_KIND = ValueContract(
    DeferredTarget("cadrumo.domain.modelos._calculation_revision", "CalculationRevisionAmendmentKind")
)
_M303_MOTIVE = ValueContract(
    DeferredTarget("cadrumo.domain.modelos._calculation_revision", "M303RectificativaMotive")
)
```

Both name the unimportable module. Because they are **deferred**, they do not fail
at import time — they fail when resolved:

```
DEFERRED TARGET UNRESOLVABLE: ValueError
```

So the amendment-kind and M303 rectificativa-motive option contracts are backed by
targets that cannot resolve. `aeat-architecture-boundaries` states the rule
directly: *dynamic imports name the canonical defining module exactly*, and a
deferred target is an import edge.

The third reference is `tests/test_docstring_core_struct_links.py`, whose
`CORE_STRUCTS` map still points `CalculationRevision` at the private module.

## How it presents, and why it went unnoticed

The visible symptom is eight failures in
`cadrumo-harness/.../mcp/tests/test_harness_delivery.py`, which reach the private
module transitively. That module was itself failing collection for an unrelated
import defect until it was repaired, so **the eight failures only became visible
once the module started collecting at all** — one defect was masking another.

The registry's refusal message advises *"the class may have been added by a
concurrent process mid-flight: run `git status` and rerun once the working tree
settles"*, which invites dismissing this as peer churn. It is not: the class is
present at HEAD in both modules and unchanged in the working tree.

## Direction

Not a liability miscalculation. The exposure is an operator-facing CLI surface
whose value contracts fail on resolution, plus the duplicated-identity hazard
inherent in two modules defining the same classes — an exception raised from one
copy is not caught by an `except` naming the other, and `isinstance` across them
is false. That hazard is currently masked because the private copy cannot be
constructed at all; it would surface the moment the registry gap were "fixed" by
adding a second entry rather than deleting the duplicate.

**Do not resolve this by adding a registry entry for the private class.** That
would make both copies importable and convert a loud failure into a silent
identity split.

## Remediation — owner's decision, two parts

1. **Repoint the two `DeferredTarget`s** at `cadrumo.domain.modelos.calculation_revision`,
   and the `CORE_STRUCTS` entry with them. Small, safe, and it restores the CLI
   contracts immediately.
2. **Delete `_calculation_revision.py`.** This is the relocation's missing half.
   `aeat-architecture-boundaries` requires a relocation to land the move, every
   consumer update and the old path's deletion in one commit; here the move and
   most consumers landed and the deletion did not. Deleting it needs the standard
   relocation discipline — `pytest --collect-only -q` clean immediately before and
   after, one explicit-path commit.

The two files differ by roughly eighteen lines, so before deleting, diff them and
confirm the public module is the superset. If the private copy carries anything
the public one lacks, that content moved nowhere and the diff is the record of
what a plain deletion would lose.

No production code, registry data or test was changed by this audit.
