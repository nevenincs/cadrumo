---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e84eef4c47d7d10416656b13bacd60ec9d3dfbd4f330d3a55536a0590a2cbf65'
step_id: 'S38'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Record in the licence rule source that the narrow embedding exception has no consumer at HEAD

## Scope

- `.vaultspec/rules/aeat-documentation.md`

## Description

- Establish where the amended licence text actually lives before editing anything, because the plan row that landed the amendment names a rule slug that is not a file.
- Confirm the rule sources and every generated provider copy are clean, so the sync propagates one change and not a peer's drift.
- Add one paragraph to the licence section stating that the embedding exception has no consumer at HEAD and why it is kept open rather than re-narrowed.
- Propagate with the sync verb and commit only the copies carrying this change.

## Outcome

The permission now says out loud that nothing can currently exercise it.

The ruling was to record rather than re-narrow. Re-narrowing would have to be reversed if the removal that emptied the permission is itself reversed, and a permission that oscillates is worse than one that is documented. What the rule lacked was not tighter wording but an honest statement of its own status: as written it read as settled practice, when in fact no matrix, no compiler and no client tier exist to use it. The added paragraph frames it as a door that is deliberately unlocked and presently unused, and says that shipping a matrix through it is a first use needing the pending ruling rather than an already-sanctioned move.

One locating fact worth recording, because it cost time and will cost the next reader the same. The rule slug the amendment row names has no file of its own. The licence text was merged into the documentation rule instead, which is correct under the codification retirement, since that discipline prefers merging a mandate into the nearest existing rule over adding a file that then taxes every session forever. Anyone searching the rules directory for the slug finds nothing and may conclude the amendment never landed. It did.

The sync propagated the paragraph to the four generated provider rule copies and to the aggregated Gemini surface, five files, all sync output rather than hand edits.

## Notes

The sync reported three MCP launch entries differing from source, an unrelated refresh of the vaultspec server command from one launcher form to another. Those are not this row's change and were deliberately left uncommitted in the working tree for whoever owns that surface. They were not resolved with the force flag. Committing them under this row would have bundled an unrelated tooling change into a rule amendment, and the ledger would then attribute it here.

The rule sources and every generated copy were confirmed clean immediately before the sync, which is the coordinated quiet window the sibling amendment row asks for. No generated copy was hand-edited at any point.

No tests, gates or linters were run. This fleet has a single test-run authority.
