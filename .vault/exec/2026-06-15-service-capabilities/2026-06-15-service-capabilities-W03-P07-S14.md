---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S14'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Write the onboarding how-to doc covering bootstrap, capabilities, and the doctor and ## Scope

- `docs/how-to` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write the onboarding how-to doc covering bootstrap, capabilities, and the doctor

## Scope

- `docs/how-to`

## Description

- Author `docs/how-to/onboarding.md`: a clean-machine guide covering `just bootstrap` (install), `just doctor` / `aeat config check` (readiness), `just provision` + `ollama serve`/`ollama pull` + provider-CLI (fill gaps), and `aeat config profile capabilities show/set` (opt in/out of cloud upload — off by default, gestor-barred — on-host vision, and Google export).
- Register the page as the first "How do I start this?" card and the first hidden toctree entry in `docs/how-to/index.md`.
- Verify every documented command against the live CLI and justfile before authoring; cross-links target existing how-to pages.

## Outcome

A newcomer now has a single front-door guide from empty checkout to a working, capability-configured tool. Documented-command conformance (48 tests) passes; the imperative-step, simple-terminology style follows the user-docs-hardening rule. Committed as `6bf45d03e`.

## Notes

The full nitpicky Sphinx build (`-n -W`) is the slow gate; it runs in the S15 verification pass rather than per-doc. Links and toctree wiring were verified by inspection (all targets exist).
