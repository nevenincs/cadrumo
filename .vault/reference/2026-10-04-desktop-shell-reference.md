---
tags:
  - '#reference'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:2c48e27f276f538b4896634e314613d35e0b469cfa7d1966eb4dc4165db0d73f'
related: []
---

# `desktop-shell` reference: `Desktop shell evidence`

These findings describe the code and built artifacts that the desktop shell composes: the current Tauri frontend and host, the built user documentation and its search, backend logging, and the key bindings the TUI already owns. Source was read at `feature/tui` HEAD `c7c3d9a4f0`, and the native desktop tree at `1d90d999ba`. The built documentation was measured in the canonical output root resolved by `dev/docs/build_paths.py:30` (`var/storage/development/build/docs/html`, written 2026-10-04 07:08).

## Summary

### Current desktop frontend and host

- The frontend is one fullscreen xterm attached to the Rust pseudo-terminal: `native/desktop/frontend/src/App.tsx`, `native/desktop/frontend/src/components/TerminalView.tsx`. Ctrl+Shift+L toggles a diagnostics overlay (`native/desktop/frontend/src/components/DiagnosticsPanel.tsx`), which polls `diagnostics_snapshot` every 500 ms.
- Terminal output is polled through `terminal_read`, with no push. Input is sent as JSON `number[]` in 16 KiB slices (`TerminalView.tsx`). There is one session at a time, and it always runs the TUI.
- Window CSP: `native/desktop/src-tauri/tauri.conf.json.in` sets `script-src 'self'`, `style-src 'self' 'unsafe-inline'`, `font-src 'self'`, `connect-src ipc: http://ipc.localhost` and `frame-src 'none'`. Capabilities are empty. The window is 1440x1050 by default with a 520x400 minimum.
- `native/package-layout.json` already declares a package `docs` path. `native/CONTRACT.md` maps immutable resources to `P/docs/` on Windows.

### Built user documentation

- The docs are built by Sphinx with the Furo theme (`docs/conf.py:373`). Fonts (Hanken Grotesk, Newsreader, JetBrains Mono) are bundled as woff2 in `docs/_static/`.
- Search is Pagefind, built after Sphinx and kept separate from it (`docs/pagefind.yml`, `dev/docs/pagefind_index.py`, `dev/docs/pagefind_inject.py`). `docs/_static/cadrumo-docs.js:364` loads `pagefind/pagefind.js` with a dynamic `import()`. Pagefind instantiates WebAssembly, so the document origin's CSP needs `'wasm-unsafe-eval'`.
- The docs bind their own keys. Ctrl+K opens the search palette (`docs/_static/cadrumo-docs.js:972`). ArrowLeft and ArrowRight step between pages when no modifier is held (`:1475`). Escape closes popovers and the language switcher (`:1703`, `:1798`). Clipboard writes use `navigator.clipboard` (`:1387`).
- Each language has its own root: English at the top level, and es/ca/hu as subdirectories (`justfile` recipe `docs-lang`). The language switcher (`docs/_templates/cadrumo-language-switcher.html:19`) depends on this layout. Per language, the shippable files total about 108 MB in about 15,700 files by this measurement, and 113 to 115 MB by the technical session's packaging pass. Pagefind takes about 30 MB in the development build and about 17 MB as packaged, in about 15,000 files. `_generated/casillas` is 35 MB and `_generated/legal` is 15 MB. All four languages together come to about 435 MB and 63,000 files.
- The output root also holds build-only content that must not ship: `.doctrees` (2.0 GB in each localized root, inside `html/<lang>/`), `_sources` (39 MB per root) and `.buildinfo`.
- The English root in the measured build has no `pagefind/` directory, while es/ca/hu each have one.
- CSP-relevant content in a built page (`index.html`):
  - an async MathJax script from `cdn.jsdelivr.net` loaded on every page, although no English page contains a `class="math` node
  - one executing inline script on `index.html`, Furo's `document.body.dataset.theme = localStorage.getItem("theme") || "auto";`. Across a whole root, the technical session's packaging pass measured 5 distinct executing inline-script hashes, so the CSP hash list has to come from the docs manifest, never a fixed value
  - a non-executing `<script type="application/json" id="cadrumo-chrome-strings">` emitted by `docs/_templates/base.html`
  - no inline event-handler attributes
  - inline `style=` attributes, covered by `'unsafe-inline'`
- hoverxref is enabled for `:term:` roles (`docs/conf.py:147`). Its client requests `/_/api/v3/embed/` (`_static/js/hoverxref.js:89`), which only Read the Docs serves. 11 English pages carry hoverxref anchors.
- Furo's sidebar search is a GET form submitted to `search.html`, so the docs origin needs `form-action 'self'`.
- Palette: light and dark CSS variables are declared in `html_theme_options` (`docs/conf.py:415` onward). The brand accent token is in `docs/_static/cadrumo-docs.css:110`. Furo follows `body[data-theme]` (`auto`, `light`, `dark`), and the theme toggle persists in localStorage.

### Backend logging

- Every Python process configured through `configure_logging` (`src/cadrumo/core/logging.py:800`) writes one shared `RotatingFileHandler` file, `logs/cadrumo.log`. Its location comes from `StorageCategory.LOG_FILE` (`src/cadrumo/core/storage_taxonomy_locations.py:236`) under `cadrumo_log_dir`.
- The line format is `%(asctime)s [%(levelname)s] %(name)s: %(message)s` (`src/cadrumo/core/logging.py:864`). Records carry no process identity. Tracebacks continue on lines that don't start with a timestamp. Records pass `SecretScrubbingFilter`, but they are plaintext and unencrypted (`:806`).
- When the log directory can't be created, logging falls back to stderr only and logs an ERROR record (`:904`). A missing log file is therefore a distinct state from an empty one.

### Keys owned by the TUI

- Account keys F2 to F7 and F10 are reachable from every destination (`src/cadrumo/entrypoints/tui/app.py:68`). Screens also bind F1 (help), F3, F8, Escape (32 bindings), Ctrl+Enter, `/`, the plain letters, the arrows, PageUp/PageDown, Home and End.
- Textual's defaults add Ctrl+P (command palette, with the workbench provider at `app.py:61`), Ctrl+Q and Ctrl+C.
- On Windows, WebView2 handles browser accelerator keys (F5, Ctrl+R, Ctrl+P, F12, Ctrl+F, Alt+Left) unless they are disabled. Several of these collide with the bindings above.
