---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a52f15366acb102c331ed3cf98ee0d70c6cebe54e7511910f60237a997e7bd36'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

