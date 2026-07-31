---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:73cd52bcf4eceabc4490fa0aec03216f8b599881e1244c0a0b6f3dd71df9f28f'
step_id: 'S437'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Correct the language-resolver docstring so it describes explicit facade registration rather than the retired import-side-effect behavior, using the required documentation workflow.

## Scope

- `src/cadrumo/application/user_profile/_language_resolver.py src/cadrumo/application/user_profile/__init__.py`

## Description

- Ground the resolver and facade registration path with vaultspec-rag and live source inspection.
- Replace the retired import-side-effect account with the explicit facade-registration contract.
- Correct the bound-session fallback wording surfaced during technical review.
- Run isolated drafting, technical review, editorial review, focused tests, and formal code review.

## Outcome

The module now describes the explicit call from the user-profile facade to
`register_language_resolver`. It distinguishes that registration mechanism from
the import-light callback resolution path without changing runtime behavior.

## Notes

Focused facade-boundary coverage passed. The separate full documentation gate
still has generated API cross-reference warnings in registry modules; they do
not originate from this step and require their own remediation.
