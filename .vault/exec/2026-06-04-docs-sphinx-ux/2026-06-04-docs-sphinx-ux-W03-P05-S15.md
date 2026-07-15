---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S15'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-sphinx-ux with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-06-04-docs-sphinx-ux-plan placeholders are machine-filled by
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
     The build the rendered HTML documentation and ## Scope

- `docs/_build/html` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# build the rendered HTML documentation

## Scope

- `docs/_build/html`

## Description

Verified the rendered-HTML build path is exercised for real by the same
`dev/docs/tests/test_docs_build.py` battery `S14` closes: `test_docs_build_directory_contains_only_canonical_html`,
`test_docs_build_cleanup_removes_noncanonical_entries`, and
`test_rendered_site_identity_and_static_marks_are_canonical` all build real HTML output
and assert on its contents, and `test_sphinx_nitpicky_build_is_clean` /
`test_user_scope_build_is_nitpicky_clean_and_excludes_api` prove the full and
user-scoped builds succeed cleanly. The deploy pipeline
(`dev/deploy/docs_static_site.py`) provisions and validates the production static site
from that same rendered output (required-artifact checks for `index.html`, `404.html`,
`sitemap.xml`, the Pagefind bundle) against a real AWS session, so the "build the
rendered HTML documentation" step is backed by an actual site build, not a documentation
promise.

## Outcome

Step closed. Evidence: the full docs-build gate battery green at HEAD `807778bd87bc`
(team lead's `test_sphinx_nitpicky_build_is_clean` run, 766.51s, plus this session's
fresh `test_changed_docs_validation_does_not_pollute_repository_docs[dev/docs/cli_reference.py]`
pass, 7.57s) and the deploy pipeline's own artifact/build validation exist and are
exercised on real HTML output.

## Notes

No new commit required for this verification.
