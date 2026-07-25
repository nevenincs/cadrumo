---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S01'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Build the export FlowDefinition at the entrypoint tier collecting profile as a SELECT over live bucket labels defaulting to the active profile and included only when no NAME argument was given, destination as a PATH, and transport as a SELECT over the canonical ProfileBundleExportTransport values with the encrypted arm as default

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`

## Description

- Build the export definition in `build_export_flow_definition`, at the entrypoint tier, the only tier permitted to name the TUI adapter.
- Gate each page on absence: the profile SELECT is built only when the command received no NAME argument and at least one bucket exists, the destination PATH only when `--to` was omitted, the transport SELECT only when neither transport flag was passed.
- Feed the profile SELECT from `list_profile_buckets`, pre-selecting the active bucket's label through `_resolve_active_bucket_id`.
- Resolve profile display names as data through a per-run `SCHEMA_FIELD` copy table keyed by an opaque run token, mirroring the modelo-work-wizard precedent, so the definition carries copy references only.
- Read the transport SELECT's choice values off the canonical `ProfileBundleExportTransport` enum members rather than raw strings, defaulting to the encrypted arm.
- Declare checkpointing UNAVAILABLE in both flow modes so nothing collected can persist mid-run.

## Outcome

Landed in commit `c4545973f9`, with the flow-substrate quality-gate sweep in `a092c1378b`. This pass verified the step rather than re-implementing it.

Verified green: `uv run --no-sync pytest src/cadrumo/entrypoints/cli/_config/tests/test_profile_bundle_flow.py -m integration -p no:randomly -n0` — 13 passed. The page-inclusion contract is pinned by `test_export_definition_declares_exactly_the_missing_pages` (full page set, argv-suppressed subset, and the no-profiles case), the enum-sourced choices by `test_transport_choices_are_the_canonical_transport_taxonomy` asserting the choice values equal the `ProfileBundleExportTransport` member set with the encrypted default, and the run-scoped copy table by `test_profile_choices_resolve_through_the_run_scoped_copy_table`. Both frontends render the real definition headlessly: a pipe-driven questionary walk in line mode and a Textual `Pilot` drive of the full-screen app.

## Notes

The `vaultspec-rag` code index is truncated while self-reporting healthy (roughly 1027 chunks against roughly 4546 files, `degraded_reasons: []`), so a miss carries no evidence. Discovery was therefore grounded by direct full reads of the flow substrate facade and the modelo-work-wizard precedent, with `rg` confirmation of the exact symbols, rather than by trusting an empty semantic result.
