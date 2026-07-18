---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S19'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration and ## Scope

- `dev/deploy/docs_static_site.py`
- `docs/_templates` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration

## Scope

- `dev/deploy/docs_static_site.py`
- `docs/_templates`

## Description

- Add an `--out-dir` output-redirect flag to the `dev.docs.build` driver so a full build writes its HTML, Pagefind index, orphan sweep, and sitemap to a chosen directory instead of the canonical English root; guard it to full builds and skip the canonical `_build` cleanup when redirected.
- Add `_build_language_roots` / `_validate_language_roots` to the deploy publisher: each translation target builds a strict user-scope site into `html/<lang>` via the existing `--language` and `--out-dir` driver flags (no duplicated build logic), pointing the base URL at the language root, and each localized root must carry its rendered index and its own Pagefind index. Wire both into the publish flow and add per-language root endpoint checks.
- Derive the language-root set from the shared `TARGET_LANGUAGES`, never a second list.
- Add a dependency-free header language switcher: a `docs/_templates` partial included in the custom header that links the current page to its counterpart under each language root (relative root-prefix rewrite), plus the `html_context` that feeds it, derived from `OutputLanguage` with each language's endonym.
- Add deploy unit tests (language-root set, build command, per-language env, root validation) and a real Furo-render switcher test proving correct hrefs from both a localized subdir build and the default English root, plus a conf.py switcher-context test.

## Outcome

The deploy publisher now emits `/` (en, full autodoc, unchanged) plus `/es/`, `/ca/`, `/hu/` user-scope roots, each with its own Pagefind index; the switcher links every page across the roots. A real `--out-dir` es build produced the full deploy layout (index, sitemap with canonical `/docs/es/` URLs, 404, es-stemmed Pagefind chunks) and rendered the switcher with correct up/cross links. Deploy unit tests (7) and switcher tests (3) pass; the existing site-identity and scope-config gates still pass. No live publish was run.

## Notes

The custom header lives in Furo's announcement block, which Furo emits only when an announcement is set (production sets one); the switcher render test sets it too. The generated CLI/glossary/casilla pages render in English inside each localized site (they are English build products excluded from the translation surface, per the W01 scope call). No AWS/live-stack command was executed; verification was local build plus unit checks.
