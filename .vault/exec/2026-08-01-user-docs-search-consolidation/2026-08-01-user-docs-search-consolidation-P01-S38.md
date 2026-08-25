---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9c67c72203d5e9a3e65b40e506df242a47df29dfa44a314a38e24b1f64b40f59'
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

### Follow-on: the retired slug is now greppable from the rules side

The locating trap recorded above was closed at its source rather than only here. The merged licence section now spells out the retired slug `shipped-search-licence-clean` in its own text, with a sentence explaining that no file of that name exists or should exist, because merging the mandate into the nearest existing rule beats shipping a file that taxes every session forever.

Recording the trap in an execution record helps only a reader who already found this record. The person who needs it is the one grepping the rules directory for a slug that returns nothing and concluding the amendment never landed, and that person is not reading the vault. Putting the string where the failed search happens is what actually closes it.

Propagated by the same sync path, four generated provider copies and the aggregated Gemini surface, with every rule source and generated copy confirmed clean immediately beforehand so the output is purely this change.
