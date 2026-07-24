---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S31'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Author the user-facing setup-flow documentation through the documentation workflow with command conformance green and ## Scope

- `docs/how-to/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the user-facing setup-flow documentation through the documentation workflow with command conformance green

## Scope

- `docs/how-to/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Gather the live CLI surface and the operator-journey facts through a read-only research pass; author the final wording directly per the documentation discipline.
- Rework `docs/how-to/profile-setup.md`: describe the paged wizard (language-first ordering, conditional pages, on-page format hints and refusals), add save-and-resume with the setup-incomplete status and the descendants-re-asked-on-resume caveat, add the modify section with both honesty disclosures, and add the descendants section covering the paged door and the flag verbs.
- Add the Certificado de Situación Censal import section to `docs/how-to/censo-update.md` with preview-then-apply, the non-official evidence framing, the divergence warning, and a plain-language note that certificate reading is not yet active.
- Render every documented command through cli-sequence frames — four new static sequence contracts — after the mandatory-display gate refused plain fences; sweep the generated api stubs to conformance in the same commit.

## Outcome

Landed as `2f28fdeefc`. Gates: documented-command conformance 352 passed (the new sequence contracts add their own checks); `apidocs scaffold --check` conformant; the nitpicky Sphinx build gate passed. One factual correction over the research input: the researcher inferred from help text that the bare descendiente invocation shows a menu, but the shipped callback opens the paged door — the docs state the shipped behaviour, verified against the command registration.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The four new sequence frames are static; the descendiente flag verbs could run as executed sequences with a sandbox-profile fixture — recorded as a docs follow-up, not required by the display doctrine.
- Apoderado placement stayed in the authentication guide; the certificado dormancy is stated in operator language inside a note admonition rather than hidden or over-explained.

