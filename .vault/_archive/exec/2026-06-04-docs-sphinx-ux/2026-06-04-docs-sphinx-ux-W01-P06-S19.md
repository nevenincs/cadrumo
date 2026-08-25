---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:955bc51ff1b122b1f2e8478a9c2e069bd5260a39aa18051d75d848b9c42ab2a1'
step_id: 'S19'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
---

# `docs-sphinx-ux` `W01.P06.S19`

Scope: `W01.P06.S19`.

## Description

Incorporate the human brand feedback that the first approval packet looked bland and README-like.
Replace the first-page table/list shape with Sphinx Design cards, badges, tabs, and a local visual filing-flow component.
Reject Mermaid/WebGL for this wave after browser inspection showed remote JavaScript would be pulled into the local-first docs surface.
Rebuild the approval packet and verify the browser-visible first viewport.
Replace the rejected multi-color palette with a Geist/Furo pivot after human feedback identified random labels, admonitions, links, visited links, icons, and highlights.
Remove card badges and map the remaining visual system to Furo theme variables, neutral Sphinx Design cards, self-hosted Geist typography, blue links, and purple visited-link tokens.
Replace the purple visited-link token with a subdued neutral-gray visited state after human review accepted the pivot direction but rejected the visited URL styling.
Add a Furo-native broadcast and footer pattern after human feedback requested proper website surfaces for critical updates, release notes, events, downloads, and support links.
Use Furo's announcement slot, a local `page.html` template override, and config-driven `html_context` data rather than a React or Node shell.
Add an in-site updates and downloads hub so the banner and footer point to a durable documentation page instead of making GitHub links the whole update experience.
Extend the template link macro to support section fragments, including the current-page case where Furo resolves the current document to `#`.
Remove the stale banner shader script from the earlier rejected experimental direction so the approved preview remains a minimal static Furo surface.
Remove the leftover sidebar shader canvas hook and CSS after the code review identified it as dead experimental naming.
Incorporate the follow-up human readability feedback that CLI code examples looked visually collapsed, with flags such as `--from`, `--to`, and `--date` reading as if they were attached to the previous token.
Convert the filing-calendar command examples to highlighted Bash code fences and tune the generated Pygments whitespace spans so command tokens remain visibly separated.
Allow mobile code blocks and inline literals to wrap long command/path-like tokens with `overflow-wrap:anywhere` while keeping desktop blocks horizontally stable.
Incorporate the human feedback that the generated CLI reference intro reads like a table of contents without obvious links.
Update the CLI reference generator so the index emits an orientation surface with explicit command-family cards, internal section links, and a hidden toctree rather than exposing the full generated command list in the first viewport.
Incorporate the human feedback that the sidebar logo panel looked like a dead shader surface and that the logo/title were not visually centered inside it.
Remove the static pseudo-gradient from the sidebar brand panel, center the logo container with flexbox, and keep the mark as a restrained static brand element.
Incorporate the human feedback that the prose font was not good enough while preserving the accepted `Geist Mono` code font.
Move prose/body text to a calmer system reading stack and keep Geist for headings and brand-oriented typography.
Supersede the static-brand interpretation after human feedback made an animated WebGL shader canvas non-negotiable.
Restore a real local WebGL sidebar brand canvas loaded through Sphinx `html_js_files`, boot it after `DOMContentLoaded`, paint immediately, and keep a stale-frame fallback for browser-throttled previews.
Fix inline literal chip layout for `--foo-bar` style tokens by giving docutils literal chips explicit left padding, inline-block layout in prose, and normal wrapping on their nested `.pre` spans.
Fix the deeper double-dash rendering defect by explicitly disabling OpenType ligature, contextual alternate, discretionary ligature, contextual ligature, and kerning features across all code, literal, preformatted, keyboard, and Pygments command surfaces.
Add a small independent leading text-run spacer on docutils literal spans so leading `--` tokens do not rely solely on glyph bounding boxes for readable left inset.
Refine the non-negotiable WebGL brand shader after human feedback identified the first animated version as striped and distorted rather than a subtle gradient.
Replace the fragment shader's contour-band `sin(...)` treatment with a continuous animated brand-gradient field using the local logo blues `#0070f3` and `#3291ff`.
Let the shader own the panel background opacity so the gradient is visible but low-contrast, instead of disappearing through stacked canvas and fragment alpha.

## Outcome

The renewed approval packet now shows a minimal Furo-rooted documentation page with self-hosted Geist Sans and Geist Mono, six neutral route cards, one neutral important admonition, no colored card badges, one visible logo, and no remote runtime assets.
The page remains inside Sphinx and Furo, using local theme assets and Sphinx Design components rather than a separate web application shell.
The pivot intentionally removes the previous teal/amber/semantic-rainbow direction instead of continuing to tune it.
Visited prose links now use neutral gray tokens with a muted underline instead of default purple; cards, sidebar links, muted links, and table-of-contents links retain neutral chrome states.
The preview now includes a global broadcast strip for critical notices and a footer update hub with current-state, download, repository, issue, disclaimer, filing workflow, and reconciliation links.
The broadcast and footer are rendered from Sphinx configuration and templates so the generated docs can be updated without hand-editing generated pages.
The updates hub now gives readers a single page for release notes, critical notices, download guidance, event/deadline caveats, support links, and repository links.
Footer links can target the hub's `Critical updates` and `Events and deadlines` sections without producing invalid double-hash links on the current page.
The preview no longer includes the experimental `aeat-banner-shader.js` runtime asset.
The sidebar brand template no longer emits a shader canvas or shader-specific data attributes.
Command examples in the filing-calendar guide now render with Bash syntax highlighting, visible spacing before flags, and no collapsed `backlog--from` / `2026-01-01--to` visual state.
Inline CLI literals such as `--purchase-invoice-evidence-id` and dotted registry keys now use normal white-space with `overflow-wrap:anywhere`, so long tokens can wrap on mobile without forcing horizontal page overflow.
The generated CLI index now starts with two obvious links to `aeat app` and `aeat config`, followed by direct links to global flags, exit codes, JSON output behavior, output schemas, and retired command redirects.
The generated toctree remains available to Furo navigation but is hidden from the page body, so the introduction no longer collapses into a long apparent table of contents.
The sidebar brand panel no longer has a shader-like pseudo-element and the logo SVG is centered inside the panel on both axes.
The prose stack now resolves to `Segoe UI`, system UI, `Helvetica Neue`, Arial, and sans-serif fallback, while code remains on `Geist Mono`, `Cascadia Code`, `SFMono-Regular`, Consolas, and monospace fallback.
The sidebar brand panel now renders a real local WebGL canvas behind the centered light/dark SVG mark; the canvas exposes readiness and frame-count diagnostics for browser verification.
Inline literals preserve both leading hyphens in rendered text for tokens such as `--language` and preserve the space in combined literals such as `--format json`.
Inline literal chips now have measurable left and right padding and wrap long flag/path-like tokens on mobile without forcing horizontal page overflow.
Code and literal surfaces now opt out of inherited prose `"liga" 1` shaping, preventing double hyphen CLI flags from rendering or measuring like a single dash-shaped glyph.
The sidebar brand shader now reads as a soft blue brand gradient behind the logo rather than a striped contour texture.

## Notes

The focused single-page build still warns about excluded linked pages and the existing online `httpx` inventory issue.
Those warnings are packet-scoped and do not represent the full generated documentation build.
The full generated documentation build remains blocked by an existing API autodoc and Pydantic failure.
The human approval step remains open until the revised visual direction is explicitly accepted.
The browser preview for the pivot was rebuilt at `?rev=geist-pivot2` and screenshot-captured for human review.
The visited-link refinement was rebuilt at `?rev=geist-pivot3` and browser-inspected for active Furo token values.
The broadcast and footer revision was rebuilt at `?rev=broadcast3` and inspected on desktop and a 390px mobile viewport; the first mobile pass caught a Furo fixed-height announcement conflict, which was resolved by resetting announcement height and whitespace.
The updates hub revision was rebuilt at `?rev=updates2` and browser-inspected at desktop and 390px widths; the first browser pass caught a double-hash current-page fragment bug, which was resolved in the template macro.
The final browser pass at `?rev=updates3` confirmed four update cards, three footer groups, no double-hash links, no horizontal overflow at desktop or 390px widths, no external runtime requests, and no custom shader script.
The post-review cleanup pass at `?rev=updates4` confirmed zero shader nodes, zero shader scripts, no double-hash links, no horizontal overflow, and no external runtime assets at desktop and 390px widths.
The code typography pass was rebuilt with `AEAT_DOCS_ONLY` at `?rev=code10` because concurrent application-code changes currently block the unrestricted Sphinx build through unrelated error-registry and Pydantic/autodoc failures.
Playwright checks at 390px and 1280px confirmed the exact human repro commands preserve spaces in rendered text, produce no horizontal page overflow, and use `pre-wrap` plus `overflow-wrap:anywhere` on mobile.
Screenshots at `.tmp/docs-sphinx-ux-browser/filing-calendar-mobile-code10.png`, `.tmp/docs-sphinx-ux-browser/filing-calendar-desktop-code10.png`, and `.tmp/docs-sphinx-ux-browser/cli-app-mobile-code10.png` were visually inspected for command spacing and inline literal wrapping.
The CLI index orientation pass was rebuilt at `?rev=cli-index2` with `AEAT_DOCS_ONLY`, because the full generator path remains blocked by unrelated shared-worktree application errors.
Browser assertions for the CLI index confirmed two Sphinx Design cards, app/config links, five intro section links, no early visible `aeat app ledger add` command dump, and no horizontal overflow at 390px or 1280px.
Screenshots at `.tmp/docs-sphinx-ux-browser/cli-index-mobile-cli-index2.png` and `.tmp/docs-sphinx-ux-browser/cli-index-desktop-cli-index2.png` were visually inspected for link affordance, first-viewport hierarchy, and mobile layout.
The brand and prose-font pass was rebuilt at `?rev=brand-font1` with `AEAT_DOCS_ONLY`.
Browser assertions confirmed `.sidebar-brand::before` has no generated content, the brand panel uses flex centering, the logo is centered in the desktop brand rectangle, prose resolves to the new system reading stack, code still resolves to Geist Mono, and there is no horizontal overflow at 390px or 1280px.
Screenshots at `.tmp/docs-sphinx-ux-browser/cli-index-desktop-brand-font1.png`, `.tmp/docs-sphinx-ux-browser/cli-index-mobile-brand-font1.png`, and `.tmp/docs-sphinx-ux-browser/cli-index-desktop-brand-font1-dark.png` were visually inspected for brand alignment, dead-shader removal, and prose readability.
The WebGL and inline-literal follow-up was rebuilt at `?rev=shader-literal5` with `AEAT_DOCS_ONLY`, because the full generated documentation build remains blocked by unrelated shared-worktree application errors.
Browser assertions at `?rev=shader-literal5` confirmed a real shader canvas, `data-aeat-shader-ready="true"`, frame advancement from `2` to `3`, no shader error, no generated `.sidebar-brand::before` content, centered logo geometry on both axes, no horizontal overflow, inline literal text retaining `--`, left padding of approximately `6.72px`, right padding of approximately `5.76px`, `white-space: normal`, and `overflow-wrap: anywhere`.
Screenshots at `.tmp/docs-sphinx-ux-browser/cli-index-mobile-shader-literal3.png` and `.tmp/docs-sphinx-ux-browser/cli-index-desktop-shader-literal3.png` were visually inspected for the restored brand shader surface and inline literal chip spacing.
The double-dash rendering follow-up was rebuilt at `?rev=dash-render1` with `AEAT_DOCS_ONLY`.
Browser computed-style checks on the CLI page confirmed leading-dash literals resolve `"liga" 0`, `"calt" 0`, `"clig" 0`, `"dlig" 0`, `"kern" 0`, `font-kerning: none`, `font-variant-ligatures: no-common-ligatures no-discretionary-ligatures no-contextual`, visible left padding, and no horizontal overflow.
Browser computed-style checks on the updates page confirmed highlighted command blocks containing `--version` use the same disabled shaping features with `pre-wrap`, `overflow-wrap: anywhere`, and no horizontal overflow.
The shader-gradient refinement was rebuilt at `?rev=shader-gradient3` with `AEAT_DOCS_ONLY`.
Browser checks confirmed the shader canvas was ready, had no WebGL error, advanced frames from `64` to `118`, used `opacity: 1` with shader-owned alpha, and caused no horizontal overflow.
Screenshots at `.tmp/docs-sphinx-ux-browser/cli-index-desktop-shader-gradient1.png`, `.tmp/docs-sphinx-ux-browser/cli-index-desktop-shader-gradient2.png`, and `.tmp/docs-sphinx-ux-browser/cli-index-desktop-shader-gradient3.png` were visually inspected; the first two were too faint, and the third showed a visible subtle blue gradient without the earlier stripes.
