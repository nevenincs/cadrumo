---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
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
     The S02 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Relocate the submission repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries and ## Scope

- `src/aeat/domain/submission/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the submission repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/submission/_repository.py`

## Description

- Relocate the concrete `SubmissionRepository` (a `SecureBoundRepository` subclass) from the domain submission package to the persistence adapter, behind the pre-existing read-side `SubmissionRepositoryProtocol`.
- Delete the domain repository module, drop the concrete from the domain package facade, and expose the protocol as the domain's read-side surface.
- Sweep every consumer and test to the adapter home; keep the two domain roundtrip tests in place under sanctioned adapter test-edges.

## Outcome

- Landed together with the engine inversion and the deferral deletion in commit `48398f93d` (tagged `relocation:submission-repository`); the three plan steps are one inseparable inversion because moving the concrete forces the engine dependency-injection change and makes the deferral comment false.
- The `domain.submission` package no longer imports the persistence substrate; the domain-to-adapters pinned edge for the repository is deleted.

## Notes

- S02, S03, and S04 co-landed in one atomic commit; separating them would leave a non-collectible tree at a checkpoint.
