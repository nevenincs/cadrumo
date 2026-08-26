---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fea9d7e12f7d82b26e8309c39834726b0fe19cf82ef0585792b697aeffd8399c'
step_id: 'S30'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Amend the four enumerated aeat-cli-contract sentences on the rule source and propagate by sync

## Scope

- `.vaultspec/rules/aeat-cli-contract.md`

## Changes

- `M` `.vaultspec/rules/aeat-cli-contract.md`
- `M` `.claude/rules/aeat-cli-contract.md`
- `M` `.gemini/rules/aeat-cli-contract.md`
- `M` `.agents/rules/aeat-cli-contract.md`
- `M` `.codex/rules/aeat-cli-contract.md`
- `verify:` `vaultspec-core sync` -> `pass`

## Notes

Pulled forward out of W05. The `file` -> `import` renames in W03.P08 put the
tree in contradiction with the standing rule's `pull` + `file --file` mandate,
and the rule is always-on, so the gap was closed in the same session rather than
left open across two waves. Generated provider copies were propagated by
`vaultspec-core sync`, never hand-edited.
