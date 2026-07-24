---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S18'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Surface the reconciliation failures the pre-flight sweep discards so the export path an operator actually takes reports a leftover journal that may still describe cleartext bytes, carrying them on the export result and emitting them as a warning notice, gated on a test proving the export envelope warns when a journal cannot be reconciled and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Surface the reconciliation failures the pre-flight sweep discards so the export path an operator actually takes reports a leftover journal that may still describe cleartext bytes, carrying them on the export result and emitting them as a warning notice, gated on a test proving the export envelope warns when a journal cannot be reconciled

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`

## Description

- Return the isolated failures from the pre-publication sweep instead of discarding
  them after logging.
- Move the failure record to the typed contracts module so the published result can
  carry it without an import cycle.
- Carry the failures on the export result.
- Emit them as a warning notice on both export verbs, naming the count and the journal
  identifiers and suggesting the maintenance verb.
- Add a proof that the export envelope warns when a journal cannot be reconciled.
- Add a control proving a healthy export stays quiet.

## Outcome

The operator on the path they actually take now learns that a leftover journal may
still describe cleartext bytes on disk. Before this, that fact reached only the
maintenance verb, which is precisely the surface an operator has no reason to visit
until something has already gone wrong.

The warning is non-blocking because the export itself succeeded and the failed
operation keeps its journal for a later attempt, but it is loud, carries the journal
identifiers machine-readably, and suggests the verb that retries.

Non-tautology is observed both ways: removing the wiring reddens the warning proof, and
the paired control proves the notice tracks real state rather than always firing.

## Notes

The failure record moved from a frozen dataclass in the service module to a strict
frozen model in the contracts module. The service still re-exports it, so no consumer
import path changed.
