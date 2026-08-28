---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:676d4671043ced21db73bd4871a311bdea1844df5ef8ae980a2b88ea051b5942'
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

## The diff is done: the public module is a strict superset

The remediation above asked for a diff before deletion, on the grounds that
anything unique to the private copy would be content that moved nowhere. That
check is now complete, and the answer is unambiguous.

**Zero lines are unique to `_calculation_revision.py`.** Eighteen are unique to
`calculation_revision.py`, and all eighteen are docstrings — return descriptions
on the revision-catalogue accessors:

> Return the revision under this id, or ``None`` when the catalogue holds none. …
> Return a view of every revision in the catalogue. … Return how many revisions the
> catalogue holds. … Report catalogue membership for a revision record or a bare
> revision id.

So the public module carries the same code plus documentation. Deleting the
private module loses nothing.

### The apparent 1662-versus-1680 whole-file difference is line endings

A plain `diff` reports every line changed, which reads like two genuinely
divergent files. It is not: `_calculation_revision.py` is **CRLF** throughout
(1662 CRLF, 0 bare LF) and `calculation_revision.py` is **LF** throughout (0 CRLF,
1680 LF). Normalising with `tr -d '\r'` reduces the difference to the eighteen
docstring lines.

This matters beyond this audit. In a CRLF working tree a raw `diff` between a
pre-relocation file and its post-relocation copy will always look total, which
hides whether any content was actually lost. **Normalise line endings before
concluding two files differ**, or a relocation's diff is unreadable and the
"is anything unique to the old copy" question cannot be answered.

### What this changes for the remediation

Step 2 is now unblocked and its risk is measured rather than assumed: deleting
`_calculation_revision.py` is a pure removal of a duplicate, not a merge. It still
needs the relocation discipline — `pytest --collect-only -q` clean immediately
before and after, one explicit-path commit — because the module is referenced by
name in a `CORE_STRUCTS` map and possibly by string elsewhere, and because the
tree is shared.

Step 1 is partly done: the two CLI `DeferredTarget`s were repointed at
`cadrumo.domain.modelos._calculation_revision_amendment`, the module that actually
defines both enums. Neither `calculation_revision` module defines them — both
import and re-export them — so repointing at the public module would have been a
second re-export hop rather than a fix. The `CORE_STRUCTS` entry remains.

## The deletion precondition is now fully mapped

Exactly **two** references to `cadrumo.domain.modelos._calculation_revision`
remain, both string-based, both outside `src/cadrumo/domain/modelos/`:

| reference | kind | disposition |
|---|---|---|
| `src/cadrumo/tests/test_docstring_core_struct_links.py:44` — `CORE_STRUCTS["CalculationRevision"]` | names the defining module for the docstring-anchor gate | repoint to `cadrumo.domain.modelos.calculation_revision` |
| `dev/registry/analysis/load_census_classification.py:530` | one row of a module inventory listing `cadrumo.domain.modelos.*` | remove with the module |

**This corrects the earlier count in this audit**, which said three references and
named only `src/`. The `dev/` occurrence was missed because that search was scoped
to `src`. Two of the original three — the CLI `DeferredTarget`s — have since been
repointed at `_calculation_revision_amendment`.

The `dev/` row sits in a census that enumerates modules which exist. It is not a
consumer to redirect but an inventory to update, and the campaign has already
recorded that census rows are adjudications rather than derived data, so it should
be edited as part of the deletion rather than ahead of it.

### Neither reference is load-bearing today, which is why nothing failed

`CORE_STRUCTS` is used for name matching, not import: the gate resolves symbols by
dotted path against docstring anchors and never imports the mapped module. Running
`test_docstring_core_struct_links.py` confirms it — three of its seven tests fail,
but on unrelated counts (133 module uses lacking a cross-reference, 144 public
functions, 1297 dotted references naming a symbol their cited module does not
define). None mentions an unimportable module. Those three failures are
pre-existing documentation debt across the tree and are not addressed here.

### Why the two remaining edits are not being made in isolation

`aeat-architecture-boundaries` requires a relocation to land the move, every
consumer update and the old path's deletion in **one** commit, and explicitly
forbids splitting the move from the consumer sweep. Repointing `CORE_STRUCTS` now
and deleting the module later would be exactly that split. The two edits belong in
the deletion commit, with `pytest --collect-only -q` clean immediately before and
after.

So the remaining work is a single, fully-specified change: repoint one map entry,
drop one census row, delete `_calculation_revision.py`, verify collection either
side, commit with an explicit pathspec. Everything needed to judge it is now
recorded — the public module is a strict superset, and these are the only two
references left.
