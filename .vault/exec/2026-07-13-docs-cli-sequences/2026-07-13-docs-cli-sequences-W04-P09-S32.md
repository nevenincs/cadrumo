---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:aec84b3ce66d303e70cd1f7dfe7bcbae87cb1d965bda2297f94265dc79c2c82f'
step_id: 'S32'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Verify no-JS content-identical degradation, keyboard and reduced-motion accessibility, and the nitpicky offline -n -W gate green on a rendered sequence page

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Add a zero-external-request audit that scans both vendored assets for `http://`, `https://`, and any quote/paren-anchored protocol-relative or absolute URL, excluding bare `//` line comments.
- Add a wiring-and-implementation gate asserting `docs/conf.py` ships both assets and the JS/CSS sources carry the player and hover-help surfaces (`initSequences`, `setupSequence`, `initHoverHelp`, the payload and cli-tree keys; the sequence, token, controls, popover classes and `prefers-reduced-motion`).
- Add a real in-process nitpicky (`nitpicky=True`, `warningiserror=True`) HTML Sphinx build of a fixture sequence page, reusing the P07 directive and golden pattern, with `html_static_path` shipping the real widget assets and an isolated storage / English fixture for the in-build Click-tree walk.
- Assert the build is clean and the no-JS static HTML is the complete transcript (every frame, the setup output, the verify caption, the imperative expect check, exactly three frames), the enhanceable markup is present (a `data-command-path` hover key and the inline payload matching the frame kinds), and both assets ship into `_out/_static` and are referenced by the page.

## Outcome

Three real gates pass: the external-request audit (no CDN, font, or absolute URL in the widget), the wiring/implementation check, and the rendered-page build. The nitpicky offline `-n -W` build of a sequence page is green, the page degrades to a content-identical transcript without JavaScript, and the widget assets ship. Run: the two static audits pass in 15.7s and the real build in 4.66s, all green.

## Notes

Accessibility checklist verified by inspection of the landed widget: playback controls are native `button` elements (tab-focusable) with `aria-label`s and disabled-edge states; the position indicator is `aria-live="polite"`; arrow-key stepping is scoped to the sequence root so it never hijacks the global Ctrl/Cmd-K palette; hover-help tokens are made focusable (`tabindex="0"`), wire `aria-describedby` to a `role="tooltip"` popover, dismiss on Escape, and expose a tap toggle for touch; `prefers-reduced-motion` removes transitions while leaving playback functional. No conf.py change was needed — both assets were already wired in `html_js_files`/`html_css_files`, so the P08 agent's conf.py edits and this work never touched the same surface.
