---
tags:
  - '#audit'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-08-25'
body_hash: 'sha256:5a587317fe7188c66022ed6bb826f0dd11132550bf9ceaa3a1bef6d60ceb6136'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
  - '[[2026-06-04-docs-sphinx-ux-adr]]'
  - '[[2026-06-04-docs-sphinx-ux-research]]'
---

# `docs-sphinx-ux` Code Review

## DOCS-SPHINX-UX-001 | INFO | W01 foundation review passed

The W01 foundation implementation was reviewed read-only against the research, ADR, plan, Step Records, dependency declarations, Sphinx configuration, and static theme assets.
No CRITICAL or HIGH issues were found.
No lower-severity issue was identified that should block requesting `W01.P06.S18` brand approval.

The dependency additions are confined to the development dependency group and the sitemap extension remains gated behind `AEAT_DOCS_BASE_URL`.
The branding posture is consistent with the ADR because the title avoids official-agency wording, the mark is an abstract ledger/check motif rather than a public-agency seal, and the first-page copy continues to state that `aeat` never submits filings and is not affiliated with the AEAT.
The plan and Step Records honestly preserve the human gate: `W01.P06.S18` remains open, and the `S17` record explicitly says not to close it before reviewer approval.

Residual risks remain outside W01 approval: the full generated documentation build is still blocked by an existing API autodoc and Pydantic issue, the single-page packet is not a full-site `-W` clean build because linked pages are intentionally excluded, and the OpenGraph extension prints its known Matplotlib social-card notice.

## DOCS-SPHINX-UX-002 | INFO | Visual/theme pivot review passed

The latest docs Sphinx UX pivot was reviewed read-only against the research, ADR, plan, and the requested implementation surface: `docs/conf.py`, `docs/index.md`, `docs/_static/aeat-docs.css`, `docs/_static/aeat-mark-light.svg`, `docs/_static/aeat-mark-dark.svg`, `docs/_static/aeat-favicon.svg`, and the vendored `docs/_static/geist-*.woff2` files.
No CRITICAL or HIGH issues were found.
No lower-severity issue was identified that should block the visual/theme pivot.

The implementation remains on the accepted stack: Sphinx loads Furo as `html_theme`, keeps `sphinx_design` in the extension set, and renders the index route cards through Sphinx Design while preserving Furo's own sidebar, icons, theme toggle, source buttons, copybutton integration, and CSS variable model.
The custom stylesheet is layered after Furo and Sphinx Design in the rendered HTML and mostly uses Furo and Sphinx Design variables rather than replacing theme structure, so the CSS layers are not fighting each other in the reviewed surface.

The label and color system is now deliberate rather than random: link, visited-link, underline, admonition, card, tab, focus, and dark-mode tokens are declared centrally in `docs/conf.py` and `docs/_static/aeat-docs.css`.
The visible safety admonition remains present near the top of `docs/index.md`, and the route cards render as Sphinx Design cards with the shared `aeat-route-card` class rather than ad hoc HTML.

No remote runtime font, image, stylesheet, or script asset was introduced by the pivot.
The custom fonts are vendored as local WOFF2 files and referenced by relative `url(...)` paths, and the logo, Open Graph image, and favicon all resolve to local `_static` assets.
Rendered HTML still contains normal outbound footer and source repository links, plus existing intersphinx mapping URLs in configuration, but those are links or build-time metadata rather than runtime assets loaded for the theme.

Verification note: a source-filtered index build copied the local static assets and produced rendered HTML showing Furo, Sphinx Design, copybutton, and `aeat-docs.css` in the expected order.
That narrow build still fails under warnings-as-errors because the intentionally excluded linked documents are reported as missing.
An unrestricted build attempt still reaches the existing autodoc/Pydantic failure already recorded as residual risk in `DOCS-SPHINX-UX-001`; neither failure is attributable to the visual/theme pivot reviewed here.

## DOCS-SPHINX-UX-003 | INFO | Visited-link follow-up review passed

The accepted Geist/Furo pivot follow-up was reviewed read-only against the latest visited-link styling surface in `docs/conf.py`, `docs/_static/aeat-docs.css`, and the `S19` execution record.
No CRITICAL or HIGH issues were found.
No lower-severity issue was identified in the requested visited-link slice.

The previous purple visited-link direction is now historical only in the `S19` narrative, which immediately records its replacement with a subdued neutral-gray state.
The active Furo tokens use neutral visited colors: light prose links resolve through `color-link--visited` to `#4b5563` with `#d1d5db` underline, and dark prose links resolve through `color-link--visited` to `#a1a1a1` with `#4a4a4a` underline.

Furo chrome and Sphinx Design card states do not randomly repaint on visit in the reviewed CSS.
Card links are restored to inherited text color, and sidebar, drawer, table-of-contents, and muted visited links are explicitly held to `color-foreground-secondary` rather than inheriting prose visited-link treatment.

No remote runtime font, stylesheet, image, or script asset was introduced by the visited-link refinement.
The only font `url(...)` references in `docs/_static/aeat-docs.css` point to local vendored WOFF2 files, and the reviewed Sphinx configuration continues to use local favicon, logo, stylesheet, and Open Graph image assets.

## DOCS-SPHINX-UX-004 | INFO | Broadcast and footer review passed

The broadcast/footer addition was reviewed read-only against `docs/conf.py`, `docs/_templates/page.html`, `docs/_static/aeat-docs.css`, and the `S19` execution record.
No CRITICAL or HIGH issues were found.
No lower-severity issue was identified in the requested broadcast/footer slice.
Status: PASS.

The template override remains Furo-native: local Furo `page.html` defines the `announcement` and `footer` blocks, and the implementation extends `!page.html` while overriding those blocks instead of replacing Furo layout structure or introducing a separate runtime shell.
The announcement renders through Furo's existing announcement container because `html_theme_options["announcement"]` is set and the custom block is populated from Sphinx `html_context`.
The footer prepends the project notice hub inside Furo's footer block and then calls `super()`, preserving Furo's related-page and bottom-of-page footer content.

The update, download, repository, issue, and support-style links are config-driven through `html_context`, with project URLs loaded from `pyproject.toml` metadata.
The active copy does not imply AEAT affiliation: the broadcast tells users to verify official AEAT deadlines, and the footer note says `aeat` is not tax advice, is not affiliated with AEAT, and does not replace official AEAT tools or professional review.

No remote runtime asset was introduced by this slice.
A source-filtered Sphinx render loaded Furo, Sphinx Design, copybutton, custom CSS, logos, favicon, scripts, and Geist font files from local `_static` paths; outbound GitHub, Sphinx, and Furo URLs appeared only as normal anchor links.
The render still produced the expected source-filter warnings for intentionally excluded linked pages, matching the existing packet-scoped warning caveat rather than a broadcast/footer regression.

Mobile overflow was checked in Chromium against a temporary HTTP-served render at 390px and 320px widths.
At both widths, `document.documentElement.scrollWidth` equaled `clientWidth`, the announcement width matched the viewport, the footer stayed inside the viewport, and no non-local runtime requests were observed.

## DOCS-SPHINX-UX-005 | INFO | S19 follow-up review passed

The `W01.P06.S19` follow-up slice was reviewed read-only against `docs/conf.py`, `docs/_templates/page.html`, `docs/updates.md`, `docs/index.md`, `docs/_static/aeat-docs.css`, and rendered output from a temp Sphinx build.
No CRITICAL or HIGH issues were found.
Status: PASS.

The Furo template override remains narrow: it extends Furo `page.html`, fills only the announcement and footer blocks, and preserves Furo's inherited footer through `super()`.
The `aeat_link` macro renders non-current document fragments as `updates.html#critical-updates` / `updates.html#events-and-deadlines` and current-page fragments as `#critical-updates` / `#events-and-deadlines`, with no double-hash URLs in the reviewed render.

The broadcast, footer, index, and updates copy avoid AEAT affiliation and official-event authority claims.
The update hub says `aeat` is pre-alpha, not tax advice, not affiliated with AEAT, and not an authoritative tax calendar; download language is conditional on packaged artifacts being available rather than promising a packaging surface.

A source-filtered temp Sphinx build of `index` and `updates` succeeded with the expected source-filter warnings for excluded linked pages plus the known `httpx` intersphinx 404.
The reviewed static output did not copy or reference `docs/_static/aeat-banner-shader.js`; only Furo, Sphinx, copybutton, Sphinx Design, local CSS, local SVG marks, and local Geist font assets were present.

Residual risk: `docs/_templates/sidebar/brand.html` still contains an inert `aeat-brand-shader` canvas/CSS hook even though no shader JavaScript asset is referenced.
That is not a runtime asset regression for this slice, but it is dead experimental naming that should be removed in a later visual cleanup if the minimal Geist/Furo direction remains accepted.

Post-review addendum: the inert sidebar shader canvas, shader data attribute, and matching CSS were removed after this review.
A follow-up render and browser assertion confirmed zero shader nodes, zero shader scripts, no double-hash links, no horizontal overflow, and no external runtime assets at desktop and 390px widths.

## DOCS-SPHINX-UX-006 | PASS | Code typography follow-up review passed

The command-rendering follow-up was reviewed against `docs/_static/aeat-docs.css`, `docs/how-to/filing-calendar.md`, and regenerated filing-calendar render evidence.
The first `code9` evidence still left a reviewer-visible risk that mobile wrapping could read as `backlog--from` at the wrap point, so that intermediate state was rejected.
After changing highlighted whitespace spans from fixed inline-block sizing to inline `break-spaces` with `padding-inline-end`, the `code10` evidence preserves visible spacing for the previously reported `backlog --from` and `2026-01-01 --to` cases.

The rendered command text continues to include the expected spaces, mobile code blocks use `pre-wrap` with `overflow-wrap:anywhere`, and browser checks reported no horizontal page overflow at 390px or 1280px.
The CLI-reference mobile check also confirmed inline literals such as `--purchase-invoice-evidence-id` and dotted registry keys use normal white-space with `overflow-wrap:anywhere`.
No remote runtime assets or non-Sphinx application shell were introduced by this slice.

Residual risk: the unrestricted Sphinx build remains blocked by concurrent application-code failures unrelated to this docs UX slice; the final verification used the source-filtered `AEAT_DOCS_ONLY` packet and retained its expected excluded-document warnings.

## DOCS-SPHINX-UX-007 | PASS | CLI index orientation follow-up passes read-only review

Read-only review of the scoped generator, generated RST, rendered HTML, and desktop/mobile screenshots found no defects.
Generator output and `docs/cli/index.rst` remain synchronized for the command-family cards, hidden toctree, section anchors, and registry wording.
Rendered HTML contains working family links and internal section links; Sphinx Design card syntax renders without system messages; the hidden toctree avoids the first-viewport command dump; screenshots show no desktop or mobile overflow; and the index copy stays limited to observed CLI family, command-count, schema-registry, global-flag, exit-code, output-contract, and retired-redirect claims.

## DOCS-SPHINX-UX-008 | PASS | Brand and prose-font follow-up passes read-only review

Read-only review of `docs/conf.py`, `docs/_static/aeat-docs.css`, `docs/_templates/sidebar/brand.html`, rendered CLI index HTML, and the `brand-font1` desktop, mobile, and dark screenshots found no defects.

The previous shader-like sidebar treatment is gone from the scoped implementation: no gradient, shader, keyframe, or animation styling remains in the reviewed brand path, and the rendered page uses only the static light/dark SVG logo assets through the Furo sidebar template override.
The sidebar brand panel is statically styled with Furo color tokens, bordered as a plain panel, and centers the logo container and image through flex layout.
The rendered desktop light and dark screenshots show the logo panel centered in the sidebar without a shader/pseudo-gradient appearance.

The prose and code typography changes match the requested direction.
Furo `font-stack` now resolves to a `Segoe UI`-first system prose stack, headings retain the local Geist heading stack, and `font-stack--monospace` remains `Geist Mono` first with `Cascadia Code`, `SFMono-Regular`, `Consolas`, and `monospace` fallbacks.
The custom CSS continues to apply code, keyboard, sample, literal, and preformatted text through `var(--font-stack--monospace)`, so the code font was not regressed by the prose-font follow-up.

The desktop light, desktop dark, and 390px mobile screenshots show no obvious layout regression.
Fresh browser measurements also confirmed no horizontal overflow, no generated `.sidebar-brand::before` content, centered desktop brand geometry, prose resolving to the new system stack, and code resolving to the unchanged Geist Mono stack.
Implementation remains scoped to Sphinx/Furo static configuration, one custom stylesheet, and the sidebar brand template override; no application shell or remote runtime asset was introduced by this follow-up.

## DOCS-SPHINX-UX-009 | PASS | WebGL shader and inline literal follow-up passes local review

This addendum supersedes the static-brand conclusion in `DOCS-SPHINX-UX-008` after explicit human feedback made the animated WebGL shader canvas non-negotiable.
The follow-up was reviewed locally against `docs/conf.py`, `docs/_static/aeat-banner-shader.js`, `docs/_static/aeat-docs.css`, `docs/_templates/sidebar/brand.html`, and rendered CLI index output at `?rev=shader-literal5`.
An independent `vaultspec-code-reviewer` subagent was requested but could not complete because the agent pool reported a usage-limit error, so this entry records the local review and browser evidence only.

The shader is now a real local Sphinx asset: `docs/conf.py` includes `aeat-banner-shader.js` in `html_js_files`, the sidebar brand template emits a `[data-aeat-brand-shader]` canvas, and the stylesheet layers that canvas behind the centered light/dark SVG mark without a competing `.sidebar-brand::before` pseudo-shader.
The JavaScript waits for `DOMContentLoaded` when needed, initializes WebGL per canvas, paints immediately before scheduling animation, exposes `data-aeat-shader-ready` and frame-count diagnostics, and includes a stale-frame fallback so browser-throttled previews do not remain at frame zero.
Reduced-motion users still avoid the animation because both CSS and JavaScript honor `prefers-reduced-motion: reduce`.

Inline literal styling now preserves the reported `--foo-bar` class of tokens as readable chips rather than visually swallowing the first hyphen.
Browser checks at `?rev=shader-literal5` confirmed inline literal text retained leading `--`, `--format json` retained its space, left padding measured approximately `6.72px`, right padding approximately `5.76px`, `white-space` resolved to `normal`, `overflow-wrap` resolved to `anywhere`, and the page had no horizontal overflow.
The same browser pass confirmed the shader canvas was ready with no error, frame count advanced from `2` to `3`, logo geometry was centered on both axes, and `.sidebar-brand::before` had no generated content.

## DOCS-SPHINX-UX-010 | PASS | Double-dash code rendering follow-up passes local review

The follow-up for the reported `--foo-bar` rendering defect was reviewed locally against `docs/_static/aeat-docs.css` and the rendered CLI and updates pages at `?rev=dash-render1`.
The earlier padding-only treatment did not address the deeper risk that the code surfaces inherited prose font shaping from `.content`, where `"liga" 1` was enabled.
The active CSS now explicitly disables `"liga"`, `"clig"`, `"calt"`, `"dlig"`, and `"kern"` on code, keyboard, sample, preformatted, docutils literal, and nested `.pre` surfaces; it also sets `font-kerning: none` and the non-ligature `font-variant-ligatures` values on those same surfaces.

Browser computed-style checks confirmed leading double-dash literals such as `--language`, `--format json`, and generated option names resolve to `"liga" 0`, `"calt" 0`, `"clig" 0`, `"dlig" 0`, `"kern" 0`, and `font-kerning: none`.
The literal spans also receive an independent small leading spacer, so the left inset is not solely dependent on glyph bounds.
Highlighted command blocks containing `--version` on the updates page resolve to the same disabled shaping features with `pre-wrap`, `overflow-wrap: anywhere`, and no horizontal overflow.

## DOCS-SPHINX-UX-011 | PASS | Brand-gradient shader follow-up passes local review

The shader refinement was reviewed locally against `docs/_static/aeat-banner-shader.js`, `docs/_static/aeat-docs.css`, the light/dark logo SVG color tokens, and rendered output at `?rev=shader-gradient3`.
The previous fragment shader used a sine contour band calculation, which matched the human report that the surface looked striped and distorted rather than like a subtle gradient.
The active shader now uses continuous low-frequency noise and diagonal interpolation, with local brand blues from the mark (`#0070f3` in light mode and `#3291ff` in dark mode) mixed into a pale or dark panel field.

The canvas no longer relies on stacked low alpha and CSS opacity that made earlier gradient attempts nearly invisible.
The shader owns its panel alpha while the CSS canvas opacity remains `1`, producing a visible but low-contrast brand-gradient background behind the centered logo.
Browser verification at `?rev=shader-gradient3` confirmed the WebGL canvas was ready, had no shader error, advanced frames from `64` to `118`, and caused no horizontal overflow.
The inspected `shader-gradient3` screenshot shows the intended soft blue brand gradient rather than the earlier stripe texture.

## DOCS-SPHINX-UX-012 | RECONCILED | Post-close umbrella retired without claiming global docs health

Fresh curation found that `W03.P05.S27` combined an obsolete finite inventory
with a permanent whole-documentation green condition. The named sequence and
generated-target backlog was delivered later: filing-spine outputs in
`522ee05830`, broad how-to outputs including Modelo 303 in `92c8aaa35f`,
verification contracts in `74a15f5485`, and later API/reference rescaffolds
including `de05300c27`, `61d4ff3930`, and `6e5e679f53`. The original six-frame
and missing-target list is therefore no longer an executable current worklist.

The current documentation failure is unrelated to the June UX delivery:
`415944f178` deliberately removed `SequenceEngineError` from the
`dev.docs.sequences` facade while `sequence_directive.py` retained the old
facade import. That relocation owner must use the canonical direct errors-module
import; compatibility must not be restored. Ongoing Sphinx and documentation
health remains owned by canonical docs/CI gates, which route new failures to
their actual producers rather than reopening this historical UX campaign.

S27 and its failed-observation execution record are retired through the VaultSpec
CLI, never checked. Archiving this feature records delivered historical UX and
does not assert that every future HEAD has a green global documentation build.
