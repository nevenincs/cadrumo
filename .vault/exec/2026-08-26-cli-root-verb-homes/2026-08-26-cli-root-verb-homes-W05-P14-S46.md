---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d70f8ebf2a47373d2468b364042b917144f858a94786cd92a30729d367518c34'
step_id: 'S46'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Clear the 20 unreferenced stale locale keys the shard-rewrite hazard restored, and record that `scaffold --check` cannot see an orphan until its replacement key exists

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `python -m dev.locales scaffold --check` -> `missing=0, extra=5 (all peer-owned flows.manager.edit.shape.*)`

## Notes

Twenty `cli.*` keys were present in all four catalogues and referenced by
nothing: the retired `config profile preflight` family, and `show_help` leaves
for profile, censo, capabilities, auth diagnostics, google credential-source,
storage and modelo work revision. They were audited by walking the loaded
catalogue and diffing against every dotted `cli.` literal in the tree, then
spot-checked by suffix grep so a dynamically-composed key could not be mistaken
for a dead one.

Two mechanisms had kept them alive.

First, the shard-rewrite hazard. Every bulk locale verb -- `remove`,
`move-revision` -- rewrites the shard from its own snapshot, so it silently
resurrects keys a previous `remove` had cleared and drops values a previous
`set` had written. An earlier removal pass in this campaign was undone wholesale
by a later `move-revision`. The rule is ordering: a catalogue edit must END with
the `set` pass, never begin with it.

Second, a real gap in the gate. `scaffold --check` reported `extra=0` while all
twenty sat in the tree, and only reclassified the `show_help` half as `extra`
once the matching `view_help` keys existed. `extra=0` therefore does not mean
"no orphans"; it means no orphan the scaffold could pair with a live key. An
unreferenced key whose replacement was never authored stays invisible to it.
