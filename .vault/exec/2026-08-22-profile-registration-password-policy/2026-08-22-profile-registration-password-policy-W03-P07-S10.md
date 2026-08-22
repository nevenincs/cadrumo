---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:1e479124c45db45911c994b1c44d5a3c0ff394af4dc62d5763c9414fa2946065'
step_id: 'S10'
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
     The S10 and 2026-08-22-profile-registration-password-policy-plan placeholders are machine-filled by
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
     The Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then align scripted CLI and typed error registration, then manage complete real translations exclusively through dev.locales and ## Scope

- `src/cadrumo/entrypoints/cli/_config` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then align scripted CLI and typed error registration, then manage complete real translations exclusively through dev.locales

## Scope

- `src/cadrumo/entrypoints/cli/_config`

## Description

- Let scripted creation propagate typed application registration refusals without a redundant catch/rethrow branch.
- Add real distinct translations for every prospective reason and the non-oracular authentication refusal through `dev.locales`.
- Remove obsolete minimum-only application and TUI strength leaves through `dev.locales`.
- Prove scripted machine-channel refusal is localized, secret-safe, traceback-free, and mutation-free.

## Outcome

All four supported locales now contain distinct prospective-password guidance with complete safe placeholders and one non-oracular authentication refusal. Scripted creation renders the typed application outcome without raw custody English, INTERNAL guidance, traceback, message-key leakage, or candidate echo, and creates no profile on refusal.

Ruff passes. The scripted creation lane passes eight cases and the combined scripted/manager refusal lane passes ten cases.

## Notes

Locale YAML was changed only through `python -m dev.locales`. `scaffold --check` and `audit` remain globally red because unrelated generated Modelo 036/390 catalogue leaves are missing in the shared tree; the feature-owned stale leaves reported by the audit were removed. No unrelated generated keys were scaffolded or overwritten.
