---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:71a71c1f409481c114d885816b56b8213904f3312721d87b1b663a9fe1beb8c1'
step_id: 'S01'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# Add an optional forbidden-text clause to the legal-catalogue entry schema alongside required_text, evaluated at registry build. The failure message names WHICH clause fired, because a missing required phrase and a present forbidden phrase diagnose opposite defects and one message conflates them

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/domain/calculations/registry/`

## Description

- Add an optional `forbidden_text` field to `LegalReference`, defaulting to an empty tuple so every existing entry is unaffected.
- Validate `forbidden_text` entries are non-empty and unique, and refuse any phrase appearing in both `required_text` and `forbidden_text` on the same entry.
- Evaluate `forbidden_text` at registry build in `verify_legal_reference`, alongside the existing `required_text` check, against the same resolved corpus text.
- Raise a distinct failure message for each clause ("corpus text missing required text" vs. "corpus text contains forbidden text") so the two opposite defects are never conflated.

## Outcome

`LegalReference` now carries an optional negative clause: a corpus excerpt grounding current law can name a repealed phrase that must not survive in the cited document, and a deliberately historical excerpt can name later text that must not have crept in. No existing catalogue entry declares the new field, so registry build behaviour is unchanged until an entry opts in. Verified with the catalogue-verification and catalogue-verification-verifiers test suites (green before authoring new tests) and the project's ruff/format/type-check gates against the two touched files.

## Notes

No entry's `forbidden_text` is authored by this Step; authoring the two hand-checked clauses is a separate Step. The 606/623-entry committed catalogue continues to load and validate unchanged (confirmed via the existing full-catalogue coherence test).
