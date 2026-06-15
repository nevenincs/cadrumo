---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S07'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Redirect every per-domain resolve_*_repository_bucket_id function to the shared helper and remove the copied bodies

## Scope

- `src/aeat/domain/filing/_runtime_repository.py`

## Description

- Redirect `resolve_modelo_repository_bucket_id` (`domain.modelos`),
  `resolve_filing_repository_bucket_id` (`domain.filing`) and
  `resolve_application_filing_bucket_id` (`application.filing`) to delegate to
  the shared `resolve_repository_bucket_id`, each passing its own domain error
  class.
- Remove the three duplicated message/context constant triples and the copied
  resolver bodies; swap the now-unused `resolve_active_bucket_id` import for
  `resolve_repository_bucket_id`. Public resolver names and signatures unchanged.

## Outcome

Three copied resolver bodies collapsed to one canonical implementation.
Behaviour-preserving: 15 resolver tests across the three suites pass;
`pytest --collect-only` clean over `core`/`domain`/`application`
(8441/8444, 3 deselected). Landed atomically as commit `72d536614`.

## Notes

None. Message key and reason contexts were byte-identical across the three
copies, so no behavioural reconciliation was required.
