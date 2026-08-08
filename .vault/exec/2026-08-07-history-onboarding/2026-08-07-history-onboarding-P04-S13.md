---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d60e5f9180eafcd6ffb63b8104e8c78492797db8947769ec0101e51116013d7b'
step_id: 'S13'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
# add the error-registry default_suggestion entries for the new discover and pull-all verb refusals, verified by the existing suggestion-command conformance test

## Scope

- `src/cadrumo/core/errors/registry`

## Description

- Enumerated the whole error registry through the live mapping rather than by reading files: 606 entries, 377 of them (62 per cent) carrying no suggestion at all, 62 relating to live, auth or the access gate, and exactly 2 whose suggestion already cited a filed verb.
- Traced both new verbs' refusal paths to decide which entries they can actually reach, and confirmed no exception class exists that only these verbs raise.
- Added the missing suggestion to the live application failure entry, citing discovery then the sweep, with a comment recording why those two and in that order.
- Swept the remaining surfaces the CLI-contract rule names as ungated, to confirm the two verbs were already carried there rather than assuming the sibling rows had done it.

## Outcome

The one operator-reachable gap in the registry is closed. Every direct raise of the live application error class -- seven sites, all in filed-observation persistence, the filed-capture finalizer, or IVA remote state -- lies inside one of the three stages the history sweep sequences, so an operator hitting it is mid-way through building AEAT history. The entry previously carried no suggestion, meaning that operator received no next step from the first instructive surface. It now names discovery first, because discovery persists nothing and re-reads what AEAT holds without repeating a long authenticated sweep, then the sweep.

What the row asks that this does not deliver, stated rather than quietly narrowed: the row's plural implies a separate entry per verb, and no second registry home for the sweep verb alone could be justified. Two things stand in the way. There is no exception class raised only by these verbs -- both surface refusals already registered and already shared with the pre-existing filed verbs, so nothing was missing in the literal sense. And the sweep is the correct action only when a profile has no AEAT evidence at all, which is a per-finding condition no error class encodes; that is precisely why the sibling cross-period row placed it on the next-action builder's fallback branch and left the targeted capture verb as the static default. Attaching a static sweep suggestion to an existing entry would contradict that ruling. The standing goal still asks for a home for the sweep citation should a sweep-specific refusal ever be introduced.

Two entries were considered and rejected on evidence. The live-read gate refusal carries no suggestion, but it fires only under pytest, so an operator never sees it and the absence is correct. The generic snapshot-not-found base carries none while each of its five per-service subclasses cites its own list verb; a filed-specific citation on the shared base would misdirect a borrador or deudas miss.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py -m integration
    12 passed in 39.66s

    uv run --no-sync pytest -n0 -q src/cadrumo/core/errors/tests/
    42 passed in 43.33s

The integration lane of the error-registry suite was checked rather than assumed: it reported "42 deselected", so all 42 are unit-marked and the run above is the whole suite.

Mutation proof that the named gate actually validates the new citation. A pytest plugin resident OUTSIDE the repository rebound the gate module's registry view so the entry cited two invented verbs; no tracked file was modified, so a peer sweep could not commit the mutation. The canonical registry is a mappingproxy and refused assignment, which the plugin surfaced rather than silently skipping, so the rebinding targets the module-level name the gate reads. The plugin asserted the live citation was present before mutating and asserted the mutation took, printing "MUTATION APPLIED ... holder found".

    1 failed, 11 deselected in 6.99s
    FAILED ...::test_error_registry_suggestions_cite_live_commands
    cites 'aeat app live filed rediscover' but 'rediscover' does not resolve in the live CLI tree
    cites 'aeat app live filed pull-everything' but 'pull-everything' does not resolve in the live CLI tree

Both halves of the compound citation are independently resolved by the gate, so neither verb name can rot unnoticed.

Type and lint gates: ty check "All checks passed!", ruff format already formatted, ruff check clean.

## Notes

The cross-surface sweep found the two verbs already present in every other ungated surface: both appear in the profile-bound write allowlist, both register an envelope schema identifier, both carry curated operator-help rows, the sweep verb is named by the overview no-history advisory and by the cross-period next-action fallback, and the harness routing rule already instructs discovery first then the sweep. The error registry was the only surface still silent, which is consistent with this being the one row of its family left open.

The suggestion is a plain command string rather than a translation key, matching every sibling entry, so no locale catalogue work was required and none was done.
