---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:5a8a80e59a4c1dae655fd03023639997ca161b150c31221d6d759e5b13153113'
step_id: 'S30'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Extend the vendored stylesheet with the terminal-framed visual language, the collapsed setup disclosure, and prefers-reduced-motion handling

## Scope

- `docs/_static/cadrumo-docs.css`

## Description

- Append a self-contained section 11 to the vendored stylesheet giving the sequence container a terminal-window frame (rounded card, title bar with the three window dots via a pseudo-element) and a shell-prompt marker before each command line.
- Style every token kind distinctly and theme-aware: executable and leaf verbs in the brand rust, groups in the primary foreground, options in the established green, option values and arguments in the secondary foreground, and interpolated placeholders in the warning amber italic.
- Style the collapsed setup disclosure, the result-frame verify caption, and the imperative expect checklist with success ticks; style the JS-created playback controls (buttons, active play state, live position indicator) and the hover-help popover.
- Read a Furo custom property in every colour rule so light and dark themes both resolve; add a `prefers-reduced-motion` block that removes transitions while leaving playback functional; mark verb tokens carrying a command path discoverable with a dotted underline and a focus-visible outline.

## Outcome

The server-rendered transcript now reads as a terminal card with correct-by-construction token highlighting, a collapsed preparation disclosure, and a verification checklist, and the stepped player's controls and the hover popover are styled. No frame is hidden by CSS alone, so a no-JS reader still sees the complete transcript; the active-frame highlight applies only under the JS-set `cadrumo-sequence--enhanced` class. Brace balance verified (255/255); the section index in the header comment was extended to 11.

## Notes

Corrected one variable before landing: an early draft used `--font-stack--sans-serif`, which Furo does not define; swept to Furo's `--font-stack` sans body font. All colours resolve through Furo/Cadrumo custom properties, so both themes are covered without a second ruleset.
