---
tags:
  - '#adr'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-08-15'
body_hash: 'sha256:2a08f42d1817af4e3d0fb0336617c8db66c4c82f4814930b2da71d11868b2fe7'
related:
  - '[[2026-06-04-docs-sphinx-ux-research]]'
  - '[[2026-06-01-docs-cli-buildtime-research]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
---

# `docs-sphinx-ux` adr: `modern generated Sphinx UX and brand system` | (**status:** `accepted`)

## Problem Statement

The documentation build is technically strong but visually and
interaction-wise unowned. The current Sphinx site uses Furo, MyST, autodoc,
Napoleon, intersphinx, build-time CLI generation, and generated API stubs, but
the rendered site has no project-specific theme options, logo, favicon, custom
CSS, Open Graph metadata, canonical URL, sitemap policy, branded 404 page, or
generated-reference landing structure.

This creates a mismatch between the product's risk profile and its
documentation experience. AEAT workflows involve Spanish tax preparation,
operator responsibility, safety/legal boundaries, and generated contributor
reference. A generic theme and exhaustive generated trees increase reader
mental load and weaken trust, even when the underlying content is accurate.

## Considerations

The existing architecture ADRs already decide the important boundaries:
documentation truth derives from codebase state; generated API stubs are not
hand-edited; CLI help is not re-authored in narrative docs; educational
documentation follows Diataxis and remains English-only initially; every durable
documentation mandate must either be gated or explicitly marked
not-yet-enforced.

The research found that Furo remains a good default for this project because it
is minimal, responsive, customizable, and appropriate for a focused
documentation set. The major gap is not the theme choice; it is that the theme
has not been customized or paired with a navigation and metadata strategy.

PyData Sphinx Theme is the strongest fallback if the real generated API and CLI
trees prove too large for Furo's sidebar model. Shibuya is a visual-spike
candidate only. Sphinx Book Theme is not the first choice because AEAT is not
primarily a book or course site; its dominant surfaces are task guidance,
generated CLI reference, and contributor API reference.

The useful extension set is small. `sphinx_copybutton` lowers command-example
friction. `sphinx_design` supports task-route grids and compact overview cards
when used sparingly. `sphinxext.opengraph`, `sphinx_sitemap`, and
`sphinx-notfound-page` improve published-site metadata and navigation recovery
when a canonical docs URL exists. `sphinx_togglebutton` is useful only for
optional diagnostics and must not hide safety, responsibility, or legal
boundaries.

## Constraints

The implementation must not hand-edit generated API stubs or freeze generated
CLI details into narrative pages. It must preserve the existing docs-check
discipline and keep the Sphinx build deterministic in concurrent worktrees.

Branding must avoid implying affiliation with the Spanish Tax Agency. The
visual identity may evoke local-first tax preparation, auditability, and Spanish
fiscal context, but it must not copy official marks, seals, crests, or agency
visual language.

The first implementation pass must be small enough to land under shared-worktree
concurrency. Theme and metadata changes must be isolated from generated-stub
churn. If theme alternatives are evaluated, they must be evaluated against the
real built documentation tree, not theme marketing examples.

## Implementation

Keep Sphinx and Furo for the first pass. Add a project-owned theme layer through
`html_theme_options`, Furo CSS variables, light and dark logo assets, favicon,
and one custom CSS file only where theme variables are insufficient. Set package
metadata from the project configuration where practical so Sphinx version and
release fields do not drift from the package declaration.

Add the near-term extension set: `sphinx_copybutton`, `sphinx_design`, and
`sphinxext.opengraph`. Add `sphinx_sitemap` and `sphinx-notfound-page` once the
published docs URL is known or a local placeholder can be safely configured
without misleading crawlers.

Create a trust-first visual system: a simple `aeat` wordmark or abstract
ledger/form mark, high-contrast neutral typography, a restrained civic accent,
and a separate warning color for safety and legal notices. Use system or
vendored fonts only; do not add external runtime font dependencies unless a
separate asset policy is accepted.

Improve generated-reference UX by adding curated wrappers, not by editing
generated outputs. The API reference should gain package-group landing pages
that explain stable boundaries before linking into generated stubs. The CLI
reference should gain an operator-facing entry route and keep developer-heavy
schema-registry material separate from common task paths.

Revise the documentation index into a scannable task router backed by the
existing Diataxis structure. Keep hidden toctrees for Sphinx navigation, but
give readers visible first-page paths for starting, preparing a profile,
importing a ledger, choosing a modelo, calculating and verifying, exporting,
reconciling, troubleshooting, and entering contributor/API reference.

Run the implementation through explicit human gates. Machine checks can verify
imports, links, generated-output drift, and build success, but they cannot judge
whether the logo feels trustworthy, whether the palette reduces anxiety, whether
the route structure lowers mental load, or whether the rendered pages read well
on desktop and mobile. The workflow therefore pauses for human approval after
the brand direction, after the navigation and generated-reference wrappers, and
after the final rendered-site inspection. Requested feedback is incorporated
before the next wave begins.

Run a theme viability check after the Furo pass. If the built API and CLI tree
still imposes excessive sidebar/search mental load, perform a bounded spike
comparing Furo, PyData Sphinx Theme, and Shibuya against the real built docs.
Only switch themes if the spike demonstrates a concrete navigation or
maintainability advantage.

## Rationale

This decision preserves the project's strongest documentation invariant:
generated and code-derived truth remains authoritative. The UX pass improves
navigation, trust, metadata, copy ergonomics, and visual ownership without
turning generated reference into hand-authored prose.

Furo-first is the lowest-risk route because the current build already uses it
and its customization model is sufficient for the known gaps. A theme switch
would add dependency churn and visual churn before proving that Furo is the
problem. The fallback-spike condition keeps that option open without making it
the starting point.

The extension set is intentionally narrow. Each addition maps to an observed
reader or publishing need: command copy, route cards, metadata, sitemap, and
not-found recovery. Extensions that add hidden state or extra interaction are
kept out unless a specific content pattern requires them.

## Consequences

The docs will become more trustworthy and scannable without weakening the
generated-doc discipline. Users get clearer routes through high-stakes tasks,
and contributors get generated-reference wrappers that explain where to enter
the API and CLI surfaces.

The implementation adds new docs dependencies and visual assets, so the docs
gate and dependency drift checks must be updated together. The design system
also creates a maintenance obligation: colors, logos, and metadata become part
of the docs contract rather than incidental theme defaults.

Some decisions remain deliberately deferred. Hosting metadata cannot be final
until a canonical docs URL is known. A theme switch cannot be justified until
the real built documentation tree demonstrates a Furo-specific failure.
Localization of narrative docs remains outside this decision.

The human-gated workflow slows execution by design. It prevents the project from
shipping a mechanically correct but cognitively poor documentation experience,
and it makes human feedback a blocking artifact rather than an optional comment
after implementation is already treated as done.

## Amendment (2026-07-13): deployment sitemap is a build-owned writer, not `sphinx_sitemap`

Scoped, operator-authorized ruling resolving a mechanism conflict that surfaced
after the product rename: this ADR's Implementation section mandated the
`sphinx_sitemap` extension, but the deployment surfaces that landed later
demand properties the extension cannot express. The live deploy validator
(`dev/deploy/docs_static_site.py`) hard-requires a `sitemap.xml` whose URL set
contains exactly the canonical docs root `https://cadrumo.neve.md/docs/` and
only canonical-prefixed URLs, and the committed test
`test_deployment_sitemap_uses_canonical_human_doc_urls` in
`dev/docs/tests/test_docs_build.py` demands a canonical-human-page policy:
generated surfaces (`api/`, `_modules/`, `search.html`) omitted, `index.html`
pages deduplicated to their directory roots, and a deterministic sorted URL
list.

Verified against the installed `sphinx_sitemap` 2.9.0 source: exclusion IS
expressible (`sitemap_excludes` is fnmatch-wildcard-capable), but two demands
are structurally not. First, under the plain `html` builder this site uses,
every page link is emitted as `pagename + ".html"` — the `index.html` →
directory-root mapping exists only for `DirectoryHTMLBuilder` — so the root
renders as `.../docs/index.html`, failing the validator's exact
canonical-root check, and no `sitemap_url_scheme` template can express the
conditional mapping. Second, links drain from an unsorted multiprocessing
queue in page-build order, so ordering is nondeterministic under parallel
builds and merely incidental under serial ones. Additionally, the extension's
conditional activation reads `CADRUMO_DOCS_BASE_URL` in `docs/conf.py` while
the deploy script exported the rename-stale `AEAT_DOCS_BASE_URL`, so deploy
builds generated no sitemap at all.

**Ruling.** The deployment sitemap is generated by a hand-written,
deterministic, stdlib-only post-build writer —
`write_deployment_sitemap(html_root, base_url)` in `dev/docs/build.py` — that
walks the built HTML tree, filters to canonical human pages, canonicalises
`index.html` to directory roots, sorts, and writes the sitemaps.org urlset
with no lastmod stamps. The `sphinx_sitemap` extension wiring in
`docs/conf.py`, its `sitemap_url_scheme` setting, and the `sphinx-sitemap`
dependency are removed in the same change (delete-not-bridge). The
extension-plus-post-filter hybrid was rejected: the post-filter would have to
rewrite the root URL, re-map every index page, and re-sort — regenerating the
entire document — so the extension would contribute only a dependency and a
second drift surface. This amends the mechanism sentence in Implementation
("Add `sphinx_sitemap` … once the published docs URL is known"); the outcome
mandate — a published sitemap for the canonical docs URL — is unchanged, and
`html_baseurl` stays for Open Graph and canonical-URL metadata.

## Codification candidates

- **Rule slug:** `generated-docs-use-curated-wrappers`.
  **Rule:** Generated API and CLI references must be improved through curated
  landing pages, route surfaces, and generator changes, never by hand-editing
  generated output.

- **Rule slug:** `docs-branding-must-avoid-official-impersonation`.
  **Rule:** AEAT documentation branding must signal local-first tax preparation
  and auditability without copying or implying affiliation with official Spanish
  Tax Agency visual identity.

- **Rule slug:** `human-gates-for-docs-ux`.
  **Rule:** Documentation UX, visual design, readability, and cognitive-load
  changes must include explicit human approval gates because machine checks
  cannot validate reader experience.
