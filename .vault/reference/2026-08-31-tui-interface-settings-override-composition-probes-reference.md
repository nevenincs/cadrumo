---
tags:
  - '#reference'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ca557d3a404411f8418372cba436834748e083ad2a6fdc3e36590ff4fb277e4a'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# `tui-interface` reference: `settings override composition probes`

Three probes run against the live tree on 2026-08-31, recorded because one of
them REFUTES the fix the code most invites and would otherwise be re-attempted.
The question behind them: why does a scope that sets an environment variable
and drops the settings cache fail to change the resolved output language.

## Summary

### Probe 1 -- the failure reproduces in both directions

With no override active, setting the environment variable and dropping the
cache resolves `en`. Inside an override opened for an UNRELATED field, the same
sequence resolves `es`. The scope is not inert; the override is opaque to it.

### Probe 2 -- the field is not wrongly marked explicit

Inside the override, the language reports as NOT explicitly set, and the
settings value the resolver reads is the snapshotted one. This eliminates the
reading that suggests itself from the merge code: the override helper already
restores the explicit-field set correctly, so the leak is the VALUE, not the
explicitness. Any remedy aimed at the field-set is aimed at the wrong thing.

### Probe 3 -- carrying only explicit fields forward does NOT fix it

Implemented and measured: build the merged settings from only the fields the
source had explicitly set, so everything else re-derives at validation time.
Still `es`. This is the fix any reader of the flattening will propose, and it
fails because the merged dict was never the mechanism -- the override object is
constructed ONCE at block entry and every later read returns that same object,
so no care about what goes into it changes what comes out after the
environment moves.

### Probe 4 -- rebuilding the pinned override DOES fix it

With an unrelated override open, setting the environment and rebuilding the
pinned override resolves `en`; the unrelated override's own field still
applies; and removing the environment variable and rebuilding returns to `es`.
The last step matters: it shows the value TRACKS the environment in both
directions rather than latching once, which a one-directional probe could not
have distinguished.

### What this constrains

The remedy must rebuild, not re-merge. The rebuild can live inside the cache
reset, because the override is held in a context variable the reset can read
and replace, and a context-variable token restores the value current when it
was created, discarding intermediate sets. Its real cost is that cache reset
stops being a free memo drop and becomes a state mutation.

The generalisation is not about language: any test that changes the environment
expecting a settings read to follow is unreliable while ANY override is open,
and a session-scoped autouse fixture means one is open for the whole run.
