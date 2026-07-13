---
tags:
  - '#audit'
  - '#docs-brand'
date: '2026-07-13'
modified: '2026-07-13'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace docs-brand with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

## Recommendations

- Land the dark-code-block override: the fix currently rides uncommitted
  inside `docs/_static/cadrumo-docs.css`, which is the product-rename
  campaign's working-tree file (the `aeat-docs.css` -> `cadrumo-docs.css`
  rename is uncommitted); commit it with, or immediately after, that
  campaign's docs sweep.
- Purge orphaned HTML on every full docs build (or build into a clean output
  directory) so removed pages cannot survive rendering an old theme, and
  recompile the search index only over live pages.
- Consider decoupling the docs build from operator storage resolution so the
  former-product custody guard cannot red a documentation build.
