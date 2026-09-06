---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:9917be74c2e1224308ba47fa519ee78944e9defb965a7b7f762aebb9b4a02ca2'
step_id: 'S487'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prepare the parity prune as a reviewable removal manifest without applying it, deriving the one hundred and thirty two keys and a per key verdict from the live authority owning each namespace, and confirm none of them is declared anywhere so the list cannot remove a key the product resolves

## Scope

- `dev/locales` (manifest prepared in scratch; NOTHING APPLIED)

## Changes

NO CATALOGUE WAS TOUCHED. The prune is prepared as a reviewable artifact so the
decision is a yes or no on a concrete list rather than on a count I keep
quoting.

    scratchpad/PRUNE-MANIFEST.json   the exact input `dev.locales remove-batch` takes
    scratchpad/PRUNE-VERDICTS.json   one authority verdict per key

    locales: 4   distinct keys: 132   es/en/ca/hu: 132 each
    by root: cli 123, application 5, tui 4
    keys a live authority DOES declare (must not be removed): 0

THE ZERO IS THE POINT. The builder does not assume the earlier findings -- it
re-queries all three authorities live (the command-spec registry, the error
registry, and the workbench naming table) and marks any key they declare
"DECLARED -- DO NOT REMOVE". None of the 132 is. Had one been, the manifest
would have named it rather than quietly including it.

THE VERB ALREADY REFUSES THE FAILURE MODE THIS INVITES. `remove-batch` (S4xx,
target 6) refuses an absent key by default: "The batch remover underneath
silently ignores a key it cannot find in a sharded catalogue, which turns a
typo, a stale list or an already-applied manifest into a successful-looking
no-op". So a stale manifest reds rather than reporting success -- which matters
because this one will go stale the moment anyone edits a catalogue.

## Notes

WHY PREPARE RATHER THAN APPLY. Deleting 132 shipped translations across four
languages is the operator's call and nothing in this step changes that. What it
changes is the shape of the ask: the evidence for each key is now attached to
the key, in a file, rather than distributed across eleven execution records.

TO APPLY IT, one command, and I will not run it without being told to:

    uv run --no-sync python -m dev.locales remove-batch \
        scratchpad/PRUNE-MANIFEST.json

Afterwards `test_codebase_to_locale_parity` and the two `test_audit` gates
should go green, and `test_every_key_the_live_registry_declares_is_translated`
is the reverse-direction guard that fails if the removal took a key the CLI
resolves. REBUILD THE MANIFEST FIRST if any catalogue has changed since; the
builder is `scratchpad/build_prune_manifest.py` and takes seconds.

STANDING POSITION, unchanged:

* THE PRUNE -- prepared here, yours to authorise.
* THE EXPORT TREES -- their owner's: an active writer's surface, a large
  generated diff I would have to leave uncommitted, and `m390-2022`'s
  filing-grade pin (S472, S474, S486).
* THE TWO CUSTODY CASES -- environment-limited on this host (S479).
* THE PACKAGING BUILDS -- sound, over their 300s budget under this machine's
  normal shared load (S484, S485).
