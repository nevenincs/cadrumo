---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S16'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Express the re-sequenced catalogue on the substrate FlowDefinition with copy-reference slots only, preserving the register_wizard_catalogue and register_project_answers feeds

## Scope

- `src/cadrumo/application/wizard/`

## Description

Executed by two dispatched executors; verified and closed by the
coordinator.

- The catalogue is expressed on the substrate FlowDefinition through the
  one-way bridge at the interactive entry (`_commands.py`), checkpoint
  declared UNAVAILABLE both modes for this slice; both core
  registration slots keep being fed (catalogue untouched).
- Interactive `config profile create` / `edit` now run the paged
  full-screen flow: capability-selected frontend via an
  entrypoint-injected runner (the application layer cannot import the
  TUI adapter; injection preserves the hexagonal boundary), on-record
  `registered_values` in edit mode, committed answers replayed through
  the existing projection into `SetupAnswers` and the UNCHANGED
  persistence calls; non-interactive and flag paths byte-identical.
- Copy references resolve through the two namespace-prefixed resolvers
  (`profile-schema:`, `profile-terminology:` over the production
  corpus_search loader, approved-only); the legal zone exists as typed
  per-page data pending the substrate render-slot decision.

## Outcome

Commits `d488e0d44f` (cutover, 4 files) and `3bc78daa71` (copy sources,
legal zone, construction validator, 7 files), both explicit-pathspec.
Coordinator verification: formerly-red pointer-atomicity tests green,
wizard suite 254/254, new frontend + cluster tests 5/5 and 19/19,
CLI conformance 501, full-tree collection clean.

## Notes

Known slice boundaries, tracked on their own Steps: line-mode
auto-degrade becomes reachable when the substrate capability contract
lands (a four-line seam swap is prepared); mid-walk output-language
re-render deferred; per-IdentityDocument failure copy and the three
specific verifier verdict keys queue on the locale lane; the legal-zone
render slot is a substrate-contract decision in flight. Peer-owned gate
reds at landing time (lazy-import, import-hygiene, prompter-singularity
coordinates all in substrate-stream files) are owner-triaged, not this
Step's surface.
