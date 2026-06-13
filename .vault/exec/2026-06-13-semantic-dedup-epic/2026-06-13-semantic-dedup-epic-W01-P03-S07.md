---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S07'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Redirect every per-domain resolve_*_repository_bucket_id function to the shared helper and remove the copied bodies and ## Scope

- `src/aeat/domain/filing/_runtime_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
