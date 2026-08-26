---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a2783e2c93cc7513dc0feb1e716e2185a07c0f5c4ab0eb017457bb678d56d153'
step_id: 'S38'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep every leaf against the D2 grammar and amend it with the missing CREATING verb category

## Scope

- `.vaultspec/rules/aeat-cli-contract.md`

## Changes

- `M` `.vaultspec/rules/aeat-cli-contract.md`
- `M` `.claude/rules/aeat-cli-contract.md`
- `M` `.gemini/rules/aeat-cli-contract.md`
- `M` `.agents/rules/aeat-cli-contract.md`
- `M` `.codex/rules/aeat-cli-contract.md`
- `M` `.vault/adr/2026-08-26-cli-root-verb-homes-adr.md`
- `verify:` `vaultspec-core sync` -> `pass`

## Notes

Sweeping all 294 leaves against the campaign's own grammar found a gap in the
grammar. D2 had a credential-enrolment carve-out that was really a special case
of an unstated rule: a verb that CREATES a record names the record, not the
transport it performs to get the content. `app ledger evidence add`,
`evidence batch` and `inventory closing-authority-record` are the same shape and
were covered by nothing. The grammar now has three categories and the arbitrary
carve-out is gone.
