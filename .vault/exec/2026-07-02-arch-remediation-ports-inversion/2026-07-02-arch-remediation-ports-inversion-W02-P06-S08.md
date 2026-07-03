---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Verify the attachments domain pinned inventory at execution time and relocate its repository behind a port if a production domain-to-adapters edge exists, otherwise confirm the domain is already ports-compliant and remove any stale test-edge entries and ## Scope

- `src/aeat/domain/attachments` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the attachments domain pinned inventory at execution time and relocate its repository behind a port if a production domain-to-adapters edge exists, otherwise confirm the domain is already ports-compliant and remove any stale test-edge entries

## Scope

- `src/aeat/domain/attachments`

## Description

- Inventory the `src/aeat/domain/attachments` production tree at execution time: `_enums`, `_errors`, `_ids`, `_models`, `_protocols`, `_service` — no `_repository` module and no production import of any adapters package.
- Confirm the concrete repository already lives in the adapter at `adapters/persistence/storage/attachment.py`, consumed through the domain `AttachmentStore` protocol in `_protocols`.
- Grep the domain production modules for adapters imports outside `TYPE_CHECKING`/tests: none found.
- Audit the `.importlinter` `domain.attachments.*` entries: all six are live test-edge ignores whose backing test files (`test_service`, `test_repository`, `test_attachment_store_no_uri_list`) exist on disk — none stale.

## Outcome

- The attachments domain is already ports-compliant: it owns only the typed models and the repository port, with the secure-object-backed implementation resident in the adapter layer. No production `domain -> adapters` edge exists, so no relocation is required.
- No stale test-edge entries to remove; the `.importlinter` attachments ignores are all backed by present test files.
- Verify-only step: no code change, no commit to production sources.

## Notes

- This verify-only step and the modelos runtime-repository relocation (S17) are two leaves of register item D2; they do not close it. The filing-repositories wave (`domain/filing/_repository.py`, `_complementaria_repository.py`, `_runtime_repository.py`; `.importlinter` pins 686/687/704) remains open, and the graph-wide zero-domain-to-adapters check is the definitive D2 gate.
