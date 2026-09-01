---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8da6020d1645b375f895ccbdbd09109595ad63a0df3192db88ab7ffdae93666d'
related: []
---

# `semantic-consolidation` audit: `private module cross package debt`

## The finding

`aeat-architecture-boundaries` states that leading-underscore modules "are
private to their package and are not cross-package APIs", and that a contract
required outside its package "must hard-move from an underscore-private module
to a public defining module".

The working tree currently contains **270 private modules imported from outside
their own package, across 1,586 consumer files**.

This is not pre-existing debt. Comparing the committed tree against the working
tree, on the twelve heaviest targets only:

| private module | files at HEAD | files now |
| --- | --- | --- |
| `core.resources._boundary` | 2 | 378 |
| `core.time._clock` | 3 | 220 |
| `core.i18n._render` | 13 | 174 |
| `storage._secure_object_namespaces` | 16 | 160 |
| `application.operator_actions._models` | 28 | 126 |
| `core.time._utc` | 2 | 114 |
| `application.operator_actions._preconditions` | 33 | 71 |
| `storage.master_key._active_session` | 11 | 69 |
| `domain.submission._protocols` | 5 | 61 |
| `storage.envelope._envelope` | 6 | 52 |
| `core.decimal._coerce` | 1 | 47 |
| `core.decimal._grammar` | 2 | 35 |
| **sampled total** | **122** | **1,507** |

## Why the campaign produces it

Retiring a re-export facade means repointing every consumer at the module that
DEFINES the symbol. Where the facade was the package's only public surface and
the definition lives in a private module beneath it, the repointing is correct
in one dimension and wrong in another: it removes the facade, and it creates a
cross-package private import in the same edit.

Both halves are this campaign's own rules. Nothing in the retirement tooling
notices the trade, because a private module resolves and imports perfectly well;
the violation is a naming convention that only a boundary check enforces.

This is a campaign-wide effect, not one lane's. The committed history already
carries `relocation:core.errors split the errors namespace into its canonical
defining modules` and `relocation:deadlines,google,sede retire three large
facades` from other sessions, and the uncommitted tree carries several lanes'
work at once.

## What the correct remedy is, and why it is blocked

The rule states it directly: hard-move the contract to a **public** defining
module. `core/time/_clock.py` becomes `core/time/clock.py`, and the 220
consumers keep working with a one-token change.

A rename is a create plus a delete. The operator's standing instruction forbids
destructive commands, deletion explicitly included, so the campaign can create
the public module but cannot remove the private one -- and leaving both is
duplication, which is the exact defect this campaign exists to remove.

So the campaign can currently only make this worse: every further facade
retirement adds consumers to a private module that should have been renamed
first.

## What this means for the open steps

`P07.S118` is one instance of this class, not a special case. It asks to
"publicise the mirror-manifest module so its remote-naming contracts are
reachable without going through the storage namespace" -- which is precisely the
hard-move above, for one module out of 270. The two `_service.py` relocations
recorded under `P07.S164` are two more.

They are not three separate blockages. They are three visible members of a
1,586-file class, all waiting on one decision.

## The decision needed

Whether the campaign may rename private defining modules to public ones, which
requires deleting the private path in the same change.

If yes, the work is mechanical and the tooling already resolves every consumer
correctly; the rename is the same repointing operation already proven at scale.
If no, then facade retirement should STOP at packages whose definitions are
private, because continuing converts one violation into another at roughly a
hundred consumers per package.

A partial answer is also usable: permission scoped to modules this campaign
itself made cross-package, which is the 1,507-file delta above rather than the
122 that predate it.

## Every remaining facade, categorised by what actually blocks it

Seventeen eager facades remain. Each was dry-run through the retirement tool,
which now refuses rather than writing, so this is what the tool says rather than
what the campaign assumes:

| blocker | count | namespaces |
| --- | --- | --- |
| needs the private-module rename ruling | 3 | `storage.sql`, `application.aggregation`, `entrypoints.cli` |
| a gate asserts the namespace's public surface, or it is reached as a module object | 6 | `core`, `core.i18n`, `core.identity`, `core.parsing`, `adapters.outbound.llm`, `domain.justificante` |
| verified broken, encoded as an exclusion | 3 | `aeat.browser`, `application.invoices`, `core.resources` |
| carries a lazy map the eager block does not cover | 3 | `adapters.inbound.pdf`, `core.errors.registry`, `cadrumo.tests` |
| parent must go first | 1 | `entrypoints.cli._config` (waits on `entrypoints.cli`, itself rename-blocked) |
| retirable now | 1 | `application.calculations` |

The single retirable one is the namespace another session holds STAGED, whose
staged content maps two symbols to modules that do not define them. Retiring it
would land 153 consumer rewrites on top of someone else's in-flight commit, for
the second time. It is left alone.

So the facade half of this campaign is blocked on decisions rather than on
effort, and the count is exact: three namespaces on the rename ruling, six on
whether a namespace may be a declared public API (of which `core` is the
thirteen-gate conflict recorded separately), and one on another lane's commit.

`P07.S82` -- retire the twelve heaviest facades -- is substantially done by
measurement rather than by its own list: `domain/iva` at 179 names, the heaviest
it named, is inert. `application.aggregation` at 156 is the heaviest survivor
and is rename-blocked.

## Two measurement hazards this shared worktree produces

Both bit within ten minutes of each other and neither is a defect in the tool
that reported them.

**A scan taken during another lane's write reports garbage that looks like a
finding.** The import scan reported 243 unresolvable relative imports; re-run
unchanged, it reported zero. Both runs were correct about the tree they saw. The
only defence found is to re-run before believing a number that moved a lot,
which is the same discipline a flaky test deserves and for the same reason.

**A transient failure reads as evidence about committed content.** Restoring a
file from `HEAD` produced 145 collection errors, and those were reported to
another session as proof that the committed version carried a defect. It did
not: the restored file imports correctly in a fresh interpreter, and a re-run
with nothing changed collects clean. The 145 were the file mid-write, or a stale
`__pycache__` from the inert version imported moments earlier. The claim was
retracted.

## Restoring from HEAD is not the undo it looks like

`HEAD` is the state before EVERY lane's work, not before yours. Restoring a file
this campaign has touched more than once silently undoes valid repointing
layered in the same file by earlier steps -- it turned a 19-import break into 35
collection errors here and cost a second repair pass.

The reporting session generalised it further and it is worth carrying: they have
restored no file at all today, even where another lane's sweep corrupted theirs,
and let the owners repair forward instead. In a tree with several concurrent
lanes that is the safer default, and the exception is narrow -- a file whose
only difference from `HEAD` is the change being undone, verified by reading the
diff first.

## A worked example of what the ruling decides: `core.parsing`

This one shows the shape better than the aggregate numbers, because the whole
problem fits on a page.

`core/parsing/__init__.py` defines five functions. Every one is a pure
pass-through:

    def parse_iso8601_date(raw: str | None) -> date | None:
        return _parse_iso8601_date_impl(raw)

The implementations live in `_dates.py` and `_utils.py`, both private. The
namespace exists to give them public names. **31 consumers outside
`core.parsing`** import those wrappers.

So the campaign has exactly three moves available, and the ruling picks one:

1. **Leave it.** The namespace stays, and five functions remain re-declared as
   wrappers around the functions they call -- the precise defect this campaign
   was created to remove.
2. **Relocate the wrappers to a public `dates.py`.** The namespace goes inert
   and the 31 consumers reach a public module, so no boundary is violated. But
   the wrappers survive, so the duplication survives; only its address changes.
3. **Promote `_dates.py` to `dates.py`, delete the wrappers.** The 31 consumers
   import the implementation directly, under its own name. One definition, one
   address, no wrapper. This is what `aeat-architecture-boundaries` prescribes:
   a contract required outside its package hard-moves from an underscore-private
   module to a public defining module.

Option 3 is the only one that removes the duplication, and it requires deleting
`_dates.py` in the same change as creating `dates.py` -- which the standing
prohibition on destructive commands forbids.

Option 2 is available today and was NOT taken, because moving a re-declaration
to a new address while recording it as consolidation would misstate what was
done. The step stays open and honest rather than closed and hollow.

This is the choice, multiplied by 270 private modules and 1,586 consumer files.
