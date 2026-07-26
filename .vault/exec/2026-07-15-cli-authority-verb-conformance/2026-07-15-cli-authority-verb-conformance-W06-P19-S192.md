---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S192'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run generated CLI reference and static-tree conformance

## Scope

- `dev/docs/tests/`

## Description

Run generated CLI reference and static-tree conformance.

## Outcome

FAILED, peer working-tree churn carrying a latent committed hazard.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
dev/docs/tests/test_cli_reference_conformance.py dev/docs/tests/test_cli_tree.py
dev/docs/tests/test_cli_anchor_parity.py`.
Collected 23, 22 passed, 1 failed, exit line `1 failed, 22 passed in 171.36s`, exit code 1, at
HEAD `1844ef2ea0`.

The failing case asserts every live CLI leaf has a registered output schema. Two leaves, the
profile create and edit verbs, are unregistered as far as the production discovery walk can see.

Root cause established by exact search: both schemas ARE declared, in a NEW UNTRACKED module
under the application wizard package named for results. The production discovery walk imports
only modules whose name contains the payload token, inside the declared payload packages. An
application-layer module named for results is outside both filters, so the registration
decorators never run and the registry never learns the two keys.

Re-run before reporting, at HEAD `593559067c`: `1 failed, 5 passed in 44.04s`, the same
live-leaf-schema case. The relocated wizard results module is STILL untracked at that HEAD, so the
hazard is standing rather than resolved.

## Notes

The gate is non-tautological and it is right: it compares the live tree against the
registry, two independent sources, and consults no generated page.

The hazard is real rather than cosmetic. If that relocation is committed as it stands, the two
leaves lose their schema in the contract manifest and in the MCP tool surface, not only in this
gate. The owning campaign should either keep the declarations inside a discovered payload module
or extend the discovery walk in the same commit.

The JSON schema conformance suite recorded under S188 is green over the same state, because it
does not compare the live leaf set against the registry.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Status at 2026-07-26: fixed, and the diagnosis held

CLOSED. The two profile-verb schemas ARE enrolled at HEAD `990ddbb860`. Measured
directly: the production discovery walk reports zero load failures, 295 registered
schemas, and both `config.profile.create` and `config.profile.edit` present. The
gate that originally caught this now passes 6 of 6, where it reported 1 failed and
5 passed when this record was written.

The finding above was correct when it was made and was fixed thirteen hours later,
not mistaken. The record is updated rather than withdrawn, and the distinction
matters for the reason below.

The fix is commit `92b0dfd10b`, "restore the two profile verbs to the MCP surface",
landed 2026-07-26 at 11:30 and a descendant of the HEAD this record measured at
2026-07-25 22:07. It does NOT change the discovery walk. It adds two module-level
imports of the wizard result classes into a module the walk already reaches, so
importing that module transitively runs the registration decorators. The fix's own
comment restates this record's diagnosis almost word for word: the registry is
populated from payload-named modules under the declared payload packages only, the
wizard module declaring these two schemas is under neither, and without the import
both verbs drop off the MCP surface.

So enrolment IS still filename-filtered. What changed is that a deliberate bridge
now spans the filter. Any later reading that concludes filename filtering was never
the mechanism will mis-describe why the bridge has to exist.

RESIDUAL FRAGILITY, recorded because the fix's shape invites removal. The bridge is
written in the re-export idiom, importing each name and rebinding it to itself. That
is visually indistinguishable from a redundant re-export, and the obvious tidy-up is
to delete it. Doing so silently drops both verbs from the MCP surface again. Two
things currently hold that line: the comment marking the import load-bearing, and the
live-leaf-versus-registry gate, which fails when either key goes missing. The gate is
the real guard; the comment is a courtesy. Confirmed by running the gate, not by
reading it.
