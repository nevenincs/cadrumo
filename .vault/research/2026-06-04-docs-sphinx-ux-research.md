---
tags:
  - '#research'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-08-15'
body_hash: 'sha256:1f5e2c7c2ffa2ac21fbfd1a8c2486da15030d0fcc1682caf0f1032fa1e0633a3'
related:
  - '[[2026-06-01-docs-cli-buildtime-research]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
---

# `docs-sphinx-ux` research: `modern Sphinx UX, theme, metadata, and generated-reference scaffolding`

This research evaluates the missing generated-Sphinx UX pass: theme choice,
branding, typography, metadata, useful Sphinx extensions, generated API and CLI
reference scaffolding, and reader mental load. It used local codebase discovery,
vaultspec-rag semantic search, Spark explorer subagents, and current external
documentation research.

## Findings

### The current stack is sound but visually unowned

The project already has a serious Sphinx stack: Furo, MyST Markdown, autodoc,
Napoleon, viewcode, intersphinx, sphinx-autodoc-typehints, nitpicky reference
handling, vendored inventories, API stub scaffolding, and build-time CLI
reference generation. This is not a blank documentation system and should not be
replaced casually.

The missing layer is ownership of the rendered experience. `docs/conf.py`
declares Furo and `html_title`, and declares `_static` plus `_templates`, but no
logo, favicon, CSS variables, custom CSS, announcement banner, sidebar tuning,
social metadata, canonical URL, sitemap, or 404 page. The `_static` and
`_templates` folders are placeholder-only. The result is a correct but generic
site.

The metadata is also under-specified. Sphinx project metadata is hard-coded and
can drift from package metadata; copyright contains a literal `%Y` token; no
Open Graph, canonical URL, sitemap, or search-oriented description metadata is
configured.

### Furo remains the conservative default

Furo is still a strong fit because it is intentionally minimal, responsive,
customizable, search-friendly, and optimized for docsets where presenting the
whole hierarchy in the sidebar is not overwhelming. Those traits match AEAT's
need for a quiet, trust-focused tax tool and a documentation set where content
authority matters more than decoration.

The risk is not Furo itself; the risk is using uncustomized Furo while the docs
carry high-stakes tax and legal-safety semantics. Furo should be retained unless
the implementation proves the API and CLI reference tree is too large for its
sidebar model. If that happens, PyData Sphinx Theme is the most defensible
alternative because it supports larger documentation portals and stronger
top-navigation/search/versioning affordances. Shibuya is worth a visual spike
only, not immediate adoption; it is modern-looking but less obviously aligned
with this repo's strict generated-reference and conformance machinery.

Sphinx Book Theme is not the first choice for AEAT. Its book/course ergonomics
fit tutorial-heavy learning material, but AEAT's dominant surfaces are task
guides, generated CLI reference, and contributor API reference.

### The high-value extension set is small

The best near-term extension additions are:

- `sphinx_copybutton` for command snippets and CLI examples. AEAT docs contain
  many console commands, and copy affordance directly reduces operator friction.
- `sphinx_design` for index/task-route grids, compact cards, badges, and
  responsive callout layouts. Use it sparingly for navigation and status
  summaries, not marketing-style cards.
- `sphinxext.opengraph` for page metadata and share previews. This is useful
  once a public docs URL exists; configure site URL and default description.
- `sphinx_sitemap` once `html_baseurl` is known. It should be paired with
  canonical URL policy rather than added as an isolated extension.
- `sphinx-notfound-page` when docs are published as static HTML. A branded 404
  is important for a generated site with renamed pages and retired command
  surfaces.

Use `sphinx_togglebutton` only for genuinely secondary diagnostics or long
optional trace output. Do not hide safety, legal, filing responsibility, or
preflight failure information behind toggles.

Avoid broad adoption of tab systems unless there is a stable repeated need for
platform-specific install commands or format alternatives. Tabs add state and
mental overhead; AEAT should prefer one canonical path per page.

### Generated references need IA wrappers, not hand edits

The generated API reference is correct but cognitively expensive: thin
`automodule` stubs mirror dotted module paths and push readers into a large tree
of contributor-facing internals. The remediation is not hand-editing stubs. Add
curated generated-reference landing pages and package-group overviews that
explain the stable axes: `application`, `domain`, `adapters`, `entrypoints`,
`core`, `diagnostics`, and `locales`.

The generated CLI reference is exhaustive and currently contains developer-heavy
schema registry material. Existing research already recommends moving toward
build-time extraction with `sphinx-click` and dropping committed CLI snapshots.
For UX, the important principle is to separate operator reference from developer
registry details. Operator pages should expose task routes and command examples;
schema-registry material belongs in contributor/API reference if retained.

The index page currently uses hidden toctrees after a hand-written route list.
That gives Sphinx a navigable tree but gives readers limited visual orientation.
The first page should expose a compact task router backed by the existing
Diataxis structure: start, prepare profile, import ledger, choose modelo,
calculate and verify, export, reconcile, troubleshoot, then contributor/API.

### Branding should be trust-first and AEAT-adjacent, not agency-imitative

The project is not affiliated with the Spanish Tax Agency. Branding must avoid
looking like an official government service. The visual system should therefore
signal local-first safety, auditability, and Spanish tax context without copying
AEAT identity.

Recommended direction:

- Logo: simple text mark or abstract ledger/form mark for `aeat`, with no
  official crest, flag imitation, or government seal language.
- Palette: restrained neutral base, high-contrast text, a civic green or blue
  accent, and a separate warning color for legal/safety notices. Avoid a
  one-note blue government clone.
- Typography: system UI for interface chrome, a readable sans for body, and the
  existing monospace stack for code. Prefer stable local/system fonts unless
  there is a committed asset policy for vendored web fonts.
- Tone: precise, plain, non-advisory, and route-oriented. Do not bury the "never
  files for you" safety boundary.

The highest-value theme customization is a small `html_theme_options` block for
Furo CSS variables, light/dark logo assets, sidebar name behavior, source/edit
links, footer icons, and announcement banner policy. Add one custom CSS file
only when Furo variables cannot express the required change.

### Metadata and scaffolding should serve humans and agents

2026 documentation has two practical readers: people and tooling. The docs
should be scannable, link-stable, and extractable.

Concrete scaffolding patterns:

- Every narrative page should start with a one-paragraph purpose statement and a
  short "use this when" route, not a broad introduction.
- Guides should use stable command verbs rather than internal module paths.
- API package landing pages should explain boundaries and link to generated
  stubs; stubs stay generated.
- CLI reference should separate "common tasks" from exhaustive command material.
- Page metadata should include canonical URL, description, Open Graph site name,
  and favicon/logo assets once a public URL is known.
- Avoid duplicating command help or flag tables in narrative docs. Link to
  generated references or demonstrate flows.
- Keep warnings and legal-safety boundaries visible, not collapsed.

Google's current developer-docs guidance reinforces the same direction:
project-specific style first, clarity and consistency over rigid rules,
accessibility, keyboard reachability, semantic structure, shorter sentences,
important information first, and no color-only communication.

### Compatibility constraints

The accepted docs ADRs constrain the UX pass:

- Documentation truth must derive from codebase state.
- Generated API stubs must not be hand-edited.
- CLI help must not be re-authored in narrative docs.
- Documentation paths and filenames must be domain-driven, not process-driven.
- Educational docs are English-only initially and Diataxis-bound.
- Every durable mandate should have a corresponding gate or be explicitly
  declared not-yet-enforced.

This means the next implementation should be a layered Sphinx UX/IA improvement,
not a rewrite of generated surfaces by hand.

## Recommendation

Keep Sphinx and keep Furo for the first implementation pass. Add a deliberate
Furo theme configuration, brand assets, minimal CSS variables, copybutton,
sphinx-design, Open Graph metadata, sitemap/canonical URL when hosting is known,
and a custom 404 page when publishing. Then improve the generated-reference
experience by adding curated landing pages and routing surfaces around the
generated API and CLI outputs.

Run a theme spike only if the built API/CLI tree proves too large for Furo's
sidebar model. The spike should compare Furo against PyData Sphinx Theme and
Shibuya using the real generated docs, not screenshots or marketing examples.

## External sources consulted

- Furo documentation: `https://pradyunsg.me/furo/`
- Furo customization and logo documentation: `https://pradyunsg.me/furo/customisation/`
- Sphinx theming documentation: `https://www.sphinx-doc.org/en/master/usage/theming.html`
- PyData Sphinx Theme documentation: `https://pydata-sphinx-theme.readthedocs.io/`
- Sphinx copybutton documentation: `https://sphinx-copybutton.readthedocs.io/`
- Sphinx Design documentation: `https://sphinx-design.readthedocs.io/`
- sphinxext-opengraph documentation: `https://sphinxext-opengraph.readthedocs.io/`
- sphinx-sitemap documentation: `https://sphinx-sitemap.readthedocs.io/`
- sphinx-notfound-page documentation: `https://sphinx-notfound-page.readthedocs.io/`
- Google developer documentation style guide: `https://developers.google.com/style/`
- Google accessible documentation guidance: `https://developers.google.com/style/accessibility`
