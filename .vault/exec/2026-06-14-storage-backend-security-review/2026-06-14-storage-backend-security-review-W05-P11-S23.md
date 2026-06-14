---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S23'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Resolve the fincas domain hexagonal inversion by relocating the ORM-coupled repository or exposing a typed boundary facade and fix the stale docstring path and ## Scope

- `src/aeat/domain/fincas/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Resolve the fincas domain hexagonal inversion by relocating the ORM-coupled repository or exposing a typed boundary facade and fix the stale docstring path

## Scope

- `src/aeat/domain/fincas/_repository.py`

## Description

- Fix the stale `aeat.adapters.persistence.storage._orm` docstring reference (the
  mapper rows live under `storage.sql._orm`; the code path already imports the
  correct path).

## Outcome

STEP OPEN (partial). The clear stale-reference bug is fixed (committed
`1afb8a4d1`; 191 fincas tests green). The hexagonal-inversion relocation is
DEFERRED to a focused pass.

Security dimension CLEARED during the assessment: `FincaRow.address` (the
taxpayer-identifying PII) is `EncryptedString`-at-rest by deliberate design; the
non-identifying Catastro valuation columns are plaintext `Numeric` by documented
choice. So this is a STRUCTURE finding, not a security one.

Relocation plan: `FincaRepository` (637 lines) is a `domain/` repository that takes
a raw SQLAlchemy `Session` and operates on the private `_orm.FincaRow` (not
re-exported), unlike the `SecureBoundRepository`-backed domains. Resolving the
inversion means either relocating the ORM-coupled repository into the persistence
adapter or exposing a typed boundary façade at the `sql`/storage-root surface, then
rebinding `_aggregates.py`, `__init__.py`, and the fincas tests. Large enough to
warrant its own focused slice with the full fincas + storage suite as the gate.

## Notes

Deferred per the quality-over-completion discipline: a 637-line domain relocation
at near-full context risks the kind of incident the secure_objects WIP-sweep caused.
