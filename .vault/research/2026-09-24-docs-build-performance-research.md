---
tags:
  - '#research'
  - '#docs-build-performance'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:46b75392dd2eac2e9a4597af8f46a8ff7a7d69510e890ce88c205e3d57261123'
related: []
---

# `docs-build-performance` research: `where the documentation build spends its time`

The deploy build of the user documentation took 214 minutes in CI for its first
root alone, and a publish builds five roots. This record measures where that time
goes so the redesign acts on causes rather than symptoms. Measurements were taken
on 2026-09-24 against commit `ca3bb26beb`, on a cold local build (Windows, serial
Sphinx) and from CI run 35946665823 (Linux runner).

## Findings

### Navigation rendering is 89% of the write phase and quadratic in page count

A 120-second py-spy sample of the Sphinx write phase attributes 89.2% of samples to
Furo's `html-page-context` handler `_compute_navigation_tree`, which asks the page
context's `toctree()` for the whole tree (`collapse=False`, `maxdepth=-1`,
`includehidden=True`). Inside it, `global_toctree_for_doc` -> `_toctree_copy`
deep-copies every entry's table of contents for every page (55% self time in
docutils `_copy_except__document`). With `collapse=True` Sphinx copies only the
current branch; Furo never requests it.

### The same navigation is also most of every page's bytes

One built API page is 575,979 bytes, of which the sidebar navigation is 412,831
(72%), carrying 2,307 internal links. The English root holds 3,798 HTML pages and
2.4 GB. A publish renders and uploads that navigation into every page of every
root.

### The English full-scope site is built twice per publish

The deploy builds an apex root and four language roots. The English root is built
without `--language`, so it is full scope with the API autodoc tree, the same
content as the apex root with a different base URL; the apex's own index is then
replaced by the language entry page. The localization and release ADRs describe
four roots, one of them English full scope.

### The sequence gate runs repeatedly and is dominated by sandbox setup

The gate executes all 263 documented sequences, each in a fresh encrypted sandbox,
on the apex root and again on the first language root, and the prove phase runs it
a third time. No verdict is reused between builds. A 60-second sample of one gate
worker attributes 43% to sandbox provisioning (test profile capsule 15%, M303
filing-evidence seeding 14%, custody directory anchoring 14%), 12% to rebuilding
the validated registry authority snapshot per sequence, and 12% to executing the
documented commands. Locally the gate took about 8 minutes on four workers.

### Reading is ordinary Sphinx work

The read phase (autodoc generation and docutils parsing) took 8.5 minutes serial
for the full-scope root and parallelises under `-j`.

### Nothing persists between builds

Full builds pass no doctree directory, so Sphinx keeps its environment inside each
output directory, and every CI run starts from a fresh checkout. Every publish is a
cold build of every root, run one after another.

## Sources

- `.venv` Furo `__init__.py:117` (`_compute_navigation_tree`) and Sphinx
  `sphinx/environment/adapters/toctree.py:68` (`global_toctree_for_doc`), `:477`
  (`_toctree_copy`)
- `dev/deploy/docs_static_site.py` (`_build_site`, `_build_language_roots`,
  `language_build_command`)
- `dev/docs/build.py:628` (`build_docs`), `:401` (`docs_build_jobs`)
- `dev/docs/sequence_build_gate.py:150` and `dev/docs/sequences/runner.py`
  (`sequence_sandbox`, `_provisioned_sandbox_profile`)
- CI run 35946665823, step "Publish the documentation site"
