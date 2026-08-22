---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:d79a97bb49fd54c5c9f0200fea397be49ad7b491193fc099a76699af859c771f'
step_id: 'S11'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-registration-password-policy with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-08-22-profile-registration-password-policy-plan placeholders are machine-filled by
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
     The Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove real TUI scripted CLI and all-language parity at scalar byte surrogate and exact-Unicode boundaries with no persistence on refusal and ## Scope

- `profile credential inbound tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove real TUI scripted CLI and all-language parity at scalar byte surrogate and exact-Unicode boundaries with no persistence on refusal

## Scope

- `profile credential inbound tests`

## Description

- Add a strict bounded profile-creation secret-stdin channel using the existing hardened reader.
- Prove malformed JSON and extra fields refuse without echo or profile creation.
- Prove all supported locales interpolate complete, distinct real prospective and authentication messages.
- Run the combined real TUI and scripted creation boundary lane.

## Outcome

Scripted profile creation now accepts exactly one strict machine payload containing a passphrase and its confirmation. The lazy command exposes one `--secrets-stdin` option without changing the interactive arm. Locale parity covers all five stable credential messages across English, Spanish, Catalan, and Hungarian.

Ruff passes. Five language-parity cases and 22 combined TUI/scripted integration cases pass.

## Notes

The live CLI had no creation secret-stdin capability at the start of this step; the minimal production addition was explicitly authorized. Locale catalogues were not changed. The previously classified unrelated Modelo 036/390 scaffold/audit drift remains outside this step.
