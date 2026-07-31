---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:2709ad6fce0eeae6b832272a0d4b74b52892bfbd7755884f3f79bc63be5b128b'
step_id: 'S15'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

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
