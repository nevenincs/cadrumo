---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S30'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden setup-llm-classification.md and ## Scope

- `docs/how-to/setup-llm-classification.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden setup-llm-classification.md

## Scope

- `docs/how-to/setup-llm-classification.md`

## Description

- Verify-close: read `setup-llm-classification.md` against the hardening standard and its systemic audit patterns (S-PASS, S-PREREQ, S-DRIFT) and confirm resolution at HEAD.
- Confirm S-DRIFT (doc-cites-nonexistent-commands): every command resolves - `aeat app ledger providers`, `aeat config check`, `aeat app ledger classify --llm <provider>`; the supported provider names (`claude`, `antigravity` via Google's `agy` CLI, `codex`) match the live surface, and the retired standalone `gemini` CLI is correctly named as superseded.
- Confirm S-PASS (passphrase prerequisite documented) and S-PREREQ (active profile + at least one unclassified transaction stated before the smoke test).
- Confirm the privacy boundary (never contacts AEAT; provider CLI may send prompt data; treat as taxpayer data) is documented.

## Outcome

- Page verified compliant at HEAD; the systemic S-DRIFT / S-PASS / S-PREREQ patterns are addressed for this page. Delta: none required.

## Notes

- Imperative steps, provider-discovery vs account-login distinction, logged-out refusal relayed verbatim, Spanish-runtime note. CLI conformance gate green.
