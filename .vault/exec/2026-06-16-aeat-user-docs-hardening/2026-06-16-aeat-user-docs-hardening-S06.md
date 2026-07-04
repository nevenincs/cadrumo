---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S06'
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
     The S06 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden classify-with-llm-evidence.md and ## Scope

- `docs/how-to/classify-with-llm-evidence.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden classify-with-llm-evidence.md

## Scope

- `docs/how-to/classify-with-llm-evidence.md`

## Description

- Verify-close: read `classify-with-llm-evidence.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M20 (cloud-evidence consent gate does not fire on a no-evidence transaction): the page now states the precondition explicitly - the consent gate fires only when real text-layer evidence is attached, and a no-evidence transaction sends nothing extra (only the transaction row, exactly as plain LLM classify).
- Confirm the security posture is documented accurately: on-host default (no acknowledgement), gestor-mode bar, per-run non-sticky `--evidence-acknowledged`, invoice bytes in encrypted storage decrypted in-memory only (never temp file/log/cache), and `qwen2.5vl:3b` as the default local vision model.

## Outcome

- Page verified compliant at HEAD; finding M20 resolved (2026-06-19 documentation batch; a test confirms no evidence leaks the cloud boundary without the ack). Delta: none required.

## Notes

- The `qwen2.5vl:7b` mention is a correct optional upgrade over the `3b` default (not the S-DRIFT default-model error, which was in workstation-setup). CLI conformance gate green.
