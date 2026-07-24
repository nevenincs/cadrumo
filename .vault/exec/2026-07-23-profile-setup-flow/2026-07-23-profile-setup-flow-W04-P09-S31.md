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

# Author the user-facing setup-flow documentation through the documentation workflow with command conformance green

## Scope

- `docs/how-to/`

## Description

- Gather the live CLI surface and the operator-journey facts through a read-only research pass; author the final wording directly per the documentation discipline.
- Rework `docs/how-to/profile-setup.md`: describe the paged wizard (language-first ordering, conditional pages, on-page format hints and refusals), add save-and-resume with the setup-incomplete status and the descendants-re-asked-on-resume caveat, add the modify section with both honesty disclosures, and add the descendants section covering the paged door and the flag verbs.
- Add the Certificado de Situación Censal import section to `docs/how-to/censo-update.md` with preview-then-apply, the non-official evidence framing, the divergence warning, and a plain-language note that certificate reading is not yet active.
- Render every documented command through cli-sequence frames — four new static sequence contracts — after the mandatory-display gate refused plain fences; sweep the generated api stubs to conformance in the same commit.

## Outcome

Landed as `2f28fdeefc`. Gates: documented-command conformance 352 passed (the new sequence contracts add their own checks); `apidocs scaffold --check` conformant; the nitpicky Sphinx build gate passed. One factual correction over the research input: the researcher inferred from help text that the bare descendiente invocation shows a menu, but the shipped callback opens the paged door — the docs state the shipped behaviour, verified against the command registration.

## Notes

- The four new sequence frames are static; the descendiente flag verbs could run as executed sequences with a sandbox-profile fixture — recorded as a docs follow-up, not required by the display doctrine.
- Apoderado placement stayed in the authentication guide; the certificado dormancy is stated in operator language inside a note admonition rather than hidden or over-explained.
