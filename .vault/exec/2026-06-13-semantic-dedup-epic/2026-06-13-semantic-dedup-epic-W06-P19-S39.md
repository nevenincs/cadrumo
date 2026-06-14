---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S39'
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
     The S39 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The B1 Extract a secure-object catalogue integrity-error wrapper and route the exact-shape repositories through it and ## Scope

- `src/aeat/adapters/persistence/storage/errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# B1 Extract a secure-object catalogue integrity-error wrapper and route the exact-shape repositories through it

## Scope

- `src/aeat/adapters/persistence/storage/errors.py`

## Description

- Confirmed the four modelo catalogue repositories (calculation-revision,
  filing-record, work-unit, verification-report) share the byte-identical
  integrity-except shape: positional `"<label> catalogue integrity error"`
  message + `translated_message` + `{reason: secure_object_integrity,
  cause_type}` context, chained `from exc`.
- Added `raise_catalogue_integrity_error(exc, *, error_cls, label,
  translated_message, logger)` to `domain/modelos/_errors.py` and routed the
  four repos through it, passing each repo's own logger so log source is
  preserved.

## Outcome

Committed as `0ea544c08`, tagged `relocation:raise_catalogue_integrity_error`
(5 files, +58/-36). Ruff clean; 108 modelos repo/roundtrip/integrity tests green.
Behaviour-identical.

## Notes

Excluded from this exact-shape helper: `buckets/_event_repository` (its context
keys are namespace/object_key, a different shape) and `domain/modelos/
_participation_index` (peer-WIP at edit time). The four exact-shape repositories
— the step's scope — are done.
