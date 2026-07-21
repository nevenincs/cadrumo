---
tags:
  - '#audit'
  - '#docs-brand'
date: '2026-07-13'
modified: '2026-07-13'
related: []
---

# `docs-brand` audit: `docs brand fidelity render audit`

## Scope

Rendered-output fidelity audit of the Sphinx user documentation against the
Cadrumo marketing frontend design language (the Figma-derived brand in the
sibling marketing repository's `frontend/src/styles.css`): warm paper
neutrals, rust accent, Instrument Serif display headings, Hanken Grotesk
text, JetBrains Mono code. The docs-brand theme layer itself landed in commit
`af600657f9`; this audit verified that the theme actually renders as designed
across the paramount surfaces the operator named — section headers, chapter
navigation, and code display — in both light and dark themes at 1440px,
driving the freshly built HTML with headless Chromium screenshots and
comparing against the served marketing landing page.

## Findings

### stale-mixed-build | high | half the built site still rendered the pre-brand theme

`docs/_build/html` was a mixed incremental artifact: 2208 of 4379 HTML pages
predated the brand commit (the retired `api/aeat.*` autodoc tree and removed
narrative pages such as `getting-started.html` and root `glossary.html`) and
still carried the old blue `#0068d6` Furo palette, the stock sidebar, and no
site header. Because Furo bakes theme variables and templates into each page
at build time, an incremental build leaves removed-page orphans rendering the
old design indefinitely, and the Pagefind search index compiled over the
build output indexed all 2208 stale pages, so Ctrl-K results could land on
pre-brand pages. Resolution: full rebuild (config change forced a complete
re-read), deletion of all orphaned HTML older than the rebuild, and a search
index recompile (4379 -> 2171 live pages). A post-purge sweep found zero
pages carrying the old palette.

### pygments-dark-specificity | medium | dark-mode code blocks rendered cold navy

The generated dark Pygments stylesheet ships
`body[data-theme="dark"] .highlight { background: #0d1117 }` (from
`pygments_dark_style = "github-dark"`), which out-specifies the theme's
`.content .highlight` warm-surface override, so dark-mode code blocks sat on
a cold navy block foreign to the warm ink palette. Resolution: added
matching-specificity overrides in `docs/_static/cadrumo-docs.css` (section 8)
for the explicit dark state and the auto state's dark branch, re-asserting
`var(--color-inline-code-background)`. Verified by re-screenshot: dark code
blocks now sit on the warm `#26231d` surface with rust command heads.

### build-blocked-by-state-guard | low | docs build refuses on former-product state

The docs build imports the application (deferred-model rebuild and CLI
reference generation), which trips the former-product `aeat.db` custody
refusal on any workstation that carries retired product state. Workaround
used here: point `CADRUMO_LOCAL_STORAGE_ROOT` at a scratch directory for the
build process. Consider isolating the docs build from operator storage
resolution so a documentation build never depends on the machine's product
state.

### deliberate-adaptations | low | documented divergences from the marketing scale

Three divergences are deliberate docs-density adaptations, documented in the
theme CSS, and were left standing: content h2 tops out at 2.1rem versus the
marketing section-title 2.5975rem; inline code chips are borderless tints
(the marketing legal page uses a 1px-bordered chip); h3 and below stay on the
Hanken Grotesk text stack rather than Instrument Serif. Dark mode as a whole
is an extrapolation — the marketing site ships light-only — and follows the
same warm hue family inverted onto the ink.

### verified-surfaces | low | remaining surfaces render on-brand

Verified on-brand in both themes: index, how-to index, tutorial, CLI
reference, API reference root, generated glossary; sticky site header,
broadcast strip, breadcrumbs, sidebar chapter captions (mono uppercase
kickers), footer groups; admonitions (warm tint, per-severity accent),
route/status cards, tables; the Ctrl-K command palette end-to-end against the
recompiled index (term/casilla/command tiers, rust-highlighted selection);
Mermaid diagrams render the neutral theme in light and acceptable neutral
grays in dark with no cold-color leak.

### naming-deconflation-verified | low | product/executable/authority referents are clean on live surfaces

Operator directive (2026-07-13) restated the binding naming contract of the
accepted `cadrumo-cli-executable` ADR: `Cadrumo` is the product in all user
documentation prose, `aeat` is reserved for the command-line executable in
invocations, and AEAT in prose refers only to the Agencia Estatal de
Administracion Tributaria. A sweep of the narrative sources (index, how-to,
tutorials, explanation, architecture, runbooks, workstation setup, updates,
disclaimer) and the generated surfaces (CLI reference, glossary) found no
product-conflated use of `aeat`: every bare `aeat` occurrence is a fenced or
inline-code CLI invocation, every prose AEAT names the authority ("official
AEAT tools", "not affiliated with AEAT"), and `cadrumo.adapters.outbound.aeat`
names the authority-boundary adapter package correctly. The two kickoff-brief
documents and the verification marketplace proofs cite the literal plugin id
`aeat@...` as factual transcripts; those surfaces belong to the rename and
packaging campaigns respectively.

### cadrumo-as-executable-prose | medium | nine prose references named the executable `cadrumo`

Operator follow-up surfaced the inverse conflation the first sweep missed:
eight how-to pages carried nine prose references to "the `cadrumo` command" /
"run `cadrumo`" — an over-correction from the rename sweep, since the binding
`cadrumo-cli-executable` ADR fixes the human executable as exactly `aeat`
(`cadrumo` is the product, package, and import root only). Every fenced
example already invoked `aeat` correctly; only the prose noun drifted.
Resolution: all nine references corrected to the `aeat` command, verified by
a residual sweep (zero occurrences of `cadrumo` as command/executable/binary
remain) and the documented-command conformance gate (60 passed). The
`README.md` heading "Run Cadrumo from source" stands: it names the product,
and its examples invoke `aeat`.

## Recommendations

All three recommendations were engineered to closure on 2026-07-13 under
operator direction:

- Dark-code-block override: landed. The product-rename campaign's complete,
  build-verified docs sweep was committed from a verified index (staged set
  audited file-by-file, the auditor's own hunk excluded via an index blob
  swap so attribution stays clean), then the override landed as its own
  commit on the now-tracked `docs/_static/cadrumo-docs.css`.
- Orphan purge: `remove_orphan_pages` now runs on every canonical full build
  before the search index compiles, deleting any built page whose source
  document no longer exists (viewcode pages map back to `src/` modules;
  builder specials and asset directories are exempt). A live-tree run
  removed 26 further orphans from pruned api stubs; the search index was
  recompiled over the orphan-free tree. Covered by real-behavior tests in
  `dev/docs/tests/test_orphan_page_removal.py`.
- Storage decoupling: `ensure_isolated_storage_root` points the build's
  product storage at a build-scoped scratch root (explicit caller pins win)
  for both the Sphinx subprocess and the in-process search-index pass, so
  the former-product custody refusal can no longer red a documentation
  build. Verified end-to-end by running the index compile with the variable
  deliberately unset.
