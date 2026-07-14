---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S05'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Rewrite the censo how-to docs to the operator-manual config profile edit path, drop the retired verbs from filing-calendar, modelo-036, and read-live-aeat-data guides, and regenerate the API stubs so no orphan _censo rst remains and ## Scope

- `docs/how-to/censo-update.md`
- `docs/how-to/filing-calendar.md`
- `docs/how-to/modelo-036.md`
- `docs/how-to/read-live-aeat-data.md`
- `docs/api/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite the censo how-to docs to the operator-manual config profile edit path, drop the retired verbs from filing-calendar, modelo-036, and read-live-aeat-data guides, and regenerate the API stubs so no orphan _censo rst remains

## Scope

- `docs/how-to/censo-update.md`
- `docs/how-to/filing-calendar.md`
- `docs/how-to/modelo-036.md`
- `docs/how-to/read-live-aeat-data.md`
- `docs/api/`

## Description

- Confirm `docs/how-to/censo-update.md` documents the operator-manual
  `config profile edit` path with no retired-verb citation.
- Confirm `docs/how-to/filing-calendar.md` and `docs/how-to/modelo-036.md` carry
  no retired-verb citation.
- Confirm `docs/how-to/read-live-aeat-data.md` no longer exists as a source
  document (superseded by an unrelated docs-restructuring campaign) and carries
  no live reference from any remaining how-to guide.
- Confirm `docs/api/` carries no orphan stub for a deleted censo module.

## Outcome

No production edit was required: an earlier landing under this feature
(`3a48c4fe87`) already rewrote `censo-update.md` to the operator-manual path.

- `docs/how-to/censo-update.md` documents `config profile edit`/`preflight`/
  `validate` as the sole path, states plainly that AEAT exposes no read-only
  census view and the tool never operates the census modification tool, and
  cross-links `modelo-036.md` for recording an AEAT-filed Modelo 036 locally.
- `rg` for `censo pull|censo compare|censo apply|censo show|profile censo` across
  every `docs/*.md` and `docs/how-to/*.md` returns zero hits.
- `docs/how-to/read-live-aeat-data.md` is absent from the current tree and from
  git history under that name; it was never authored on this branch under that
  path (only a stale `docs/_build/` artefact references it). No remaining
  how-to guide links to it, so there is no dangling cross-reference to fix.
- `docs/api/cadrumo.application.user_profile._censo_sync.rst` and
  `._censo_errors.rst` are the surviving modules' stubs, not orphans; no stub
  exists for the deleted `_censo_live`/`_censo` sede modules or the deleted
  `_profile_censo`/`_profile_censo_payloads` CLI modules.
- `python -m dev.docs.apidocs scaffold --check` exits 0: "Stub tree is
  conformant. No drift detected."

## Notes

None. This Step closes as verification-only: the doc rewrite already landed
under this feature's P02 wave, and the one plan-named target file
(`read-live-aeat-data.md`) does not exist in the current tree under any prior
commit on this branch — it is not a censo-retirement gap.
