---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:765b2b78759717b405fd2a3c4aff781faf27ebe4167bc0d38f78c30d62cfa13e'
step_id: 'S73'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Finish the staleness chain by telling the operator WHICH of eight upstream axes moved: carry the stale reasons on the review item as stable enum tokens and render them through describe_stale_reason in the queue projection, which is the boundary where a catalogue key becomes words and therefore the only place a reason may be described. The item's own summary is a Translatable and cannot absorb rendered prose, which is why an earlier attempt to concatenate into it was reverted. Pair the projection assertion with a control row carrying no reasons.

## Scope

- `src/cadrumo/application/review/models.py`
- `src/cadrumo/application/review/_adapters.py`
- `src/cadrumo/application/review/operator.py`
- `src/cadrumo/application/review/tests/test_adapters_approval_staleness.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/review/models.py`
- `M` `src/cadrumo/application/review/_adapters.py`
- `M` `src/cadrumo/application/review/operator.py`
- `M` `src/cadrumo/application/review/tests/test_adapters_approval_staleness.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1044 -> 1043, exact
  416 -> 415; all four staleness helpers now reached
- `verify:` `pytest .../test_adapters_approval_staleness.py` 5 passed
- `verify:` `python -m dev.quality.unreachable_module_ratchet` and
  `... secure_store_write_path` both exit 0
- `verify:` `ruff check` and `ty check` clean across `application/review/`

## Notes

This closes a chain that took three steps, each unblocking the next: nothing
wrote the draft store, so nothing could go stale; nothing recomputed the
verdict, so staleness could not be detected; and the row could not say what
moved, so detection was not yet useful. The whole approval-staleness lifecycle
is now reached.

The reasons ride on `FindingReviewItem` as enum tokens and are rendered only in
the queue projection. That placement is forced rather than stylistic:
`summary` is a `Translatable`, an abstract catalogue key, so the earlier attempt
to concatenate rendered phrases into it produced a value no catalogue could
translate. The projection is where a key becomes words, so it is the only place
a reason may be described.

Three sibling tests in `test_adapters` failed mid-step with
`ProfileCustodyRefusedError: KDF_RESOURCE_LIMIT` raised from
`open_test_profile_session`. Two of the three exercise transactions and invoices,
which this step never touched. All three passed when re-run alone. The refusal is
the memory-hard KDF declining to run under machine contention, not a regression.

The first projection test was written against `project_review_queue` inside a
profile session and hit the same refusal. Rewritten against `_to_row`, which is
pure: the assertion was always about rendering, not about storage, and routing it
through the capsule bought nothing but a dependency on available memory.
