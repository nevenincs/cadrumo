---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S15'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Give verify_source_file a companion-aware absent branch: present binary stays byte-exact hash-enforced, absent-but-companion-declared binary returns an accumulable advisory rather than hard-failing

## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py`

## Description

- Give `verify_source_file` the companion-aware absent branch: a PRESENT binary stays byte-exact SHA-256 hash-enforced exactly as before; an absent binary whose catalogue entry classifies into the corpus-binaries companion set returns an accumulable `CorpusCompanionAdvisory` instead of hard-failing.
- Derive the companion classification from the catalogue data (`is_companion_corpus_binary`), never a hardcoded list.
- Commit `8bcdf00eac`.

## Outcome

- Present-binary semantics unchanged; companion absence is representable without silence.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before reporting.
