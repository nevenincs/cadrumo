---
tags:
  - '#reference'
  - '#desktop-design-system'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:fb78c6f6487c5cdfc0533ea6c7d346ebfffda95d17d81942158d39e61e45c162'
related:
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# `desktop-design-system` reference: `shell frontend structure and design-system toolchain`

## Summary

## Context

Grounds the design-system decision for the desktop shell frontend in `native/desktop/frontend/`. Read on 2026-10-05: every file under `src/`, `tests/desktop.spec.ts`, `vite.config.ts`, `playwright.config.ts`, `package.json`, the desktop scripts, `native/desktop/CMakeLists.txt`, the packaged acceptance modules under `native/desktop/tests/packaged/`, and the npm registry for candidate packages.

## Summary

### Current structure

- The shell is one React 19 application with no component library. `src/App.tsx:107` composes every area and owns the action registry (`src/App.tsx:376`), layout state and host calls.
- Styling is one hand-written sheet. `src/styles.css:60` maps shell roles (`--bg`, `--chrome`, `--fg`, `--accent`, `--error` and others) onto the generated palette names on `:root, [data-scheme]`, so a nested always-dark area such as the TUI pane (`src/App.tsx:1116`) resolves its own values. `src/tokens.css:12` holds every length token and declares no colour. `src/generated/palette.css` is written by `dev/docs/desktop_palette.py` from `docs/conf.py` and is ignored by Git (`.gitignore`).
- Interactive behaviour is hand-rolled per component: the palette's combobox and listbox (`src/components/CommandPalette.tsx:193`), the settings popover with its own outside-click and focus return (`src/components/Settings.tsx:85`), a radio group (`src/components/Settings.tsx:12`), the browser stand-in menu (`src/components/ContextMenu.tsx:7`), the roving rail (`src/components/Rail.tsx:15`) with CSS-only tooltips (`src/styles.css:233`), and the panel tab strip (`src/App.tsx:1198`). None traps focus; the palette restores focus through a ref in `App` (`src/App.tsx:1292`).
- Icons are 22 inline paths addressed by string name (`src/components/Icon.tsx:5`).
- The sign-in view is an unstyled form inside the TUI pane (`src/components/SignIn.tsx:40`, rules at `src/styles.css:8`). Its state machine lives apart in `src/shell/signIn.ts:43`: one pending status read, one submission, no retry, the password bytes zeroed after the call (`src/shell/signIn.ts:113`).
- Chrome strings come only from the generated catalogue (`src/shell/strings.ts:8`). `dev/locales/desktop_chrome.py:53` declares the keys and its drift check holds the declaration to the shell source, so a new string needs a catalogue entry in all four locales.

### Host port

- `src/shell/host.ts:35` is the one port to the desktop host. `src/shell/tauriHost.ts:20` implements it over the published commands; `src/shell/host.ts:69` is the browser stand-in, which fabricates nothing: every backend capability rejects with `HostUnavailable`, and only a `?docs=` documentation entry is honoured.
- `src/main.tsx:17` selects the host by `isTauri()`. There is no third implementation, so signed-out, throttled, runtime-unavailable, loading and error presentations are reachable in a browser only through the Playwright fixture that fakes `__TAURI_INTERNALS__` (`tests/desktop.spec.ts:23`).

### Development loop

- `vite.config.ts:8` reads `generated/identity.json` and `generated/desktop-server.json` from the directory named by `CADRUMO_CMAKE_BINARY_DIR` through `native/desktop/scripts/build-paths.mjs:4`, which also needs `build-paths.json`. Without a configured build directory `npm run dev` cannot start.
- Those three files are written at configure time by the standalone desktop project (`native/desktop/CMakeLists.txt:26` to `:30` and the shared build-path module). `build/d2-desktop` was configured that way with `CMAKE_HOME_DIRECTORY` set to `native/desktop`, bind address `127.0.0.1` and ports 15370 and 15371. Configure needs CMake, Node, npm and the development Python; it compiles nothing.
- The two generated shell inputs come from the `desktop-frontend-generated` target (`native/desktop/CMakeLists.txt:80`), which runs `dev.locales.desktop_chrome` and `dev.docs.desktop_palette`. Neither needs Rust, a wheel or a documentation build.
- Browser tests run against `vite preview` of a production build (`playwright.config.ts:23`).

### Selectors the packaged acceptance suite depends on

The packaged suite drives the real window by these hooks, and calls rail order and settings choice order locale-independent UI contracts (`native/desktop/tests/packaged/docs-ui.mjs:15`):

- `.rail-group` first and last, with buttons in order search, docs home, TUI, console, python, logs, then settings (`docs-ui.mjs:16`, `:123`).
- `.palette`, its `combobox`, `.palette-results > section` holding `option` rows, `.palette-title`, `.palette-chord` (`docs-ui.mjs:23` to `:70`).
- `.settings`, whose first `radiogroup` is appearance with radios in order follow, light, dark, read through `aria-checked`, closed by Escape (`docs-ui.mjs:129` to `:149`).
- `#profile-password` and `.sign-in button[type=submit]` (`sign-in.mjs:192`, `:195`).
- `#tab-<kind>`, `[data-terminal="<kind>"]`, `.xterm-screen`, `.xterm-rows` (`session.mjs:193` to `:199`, `browser.mjs:434`).
- `.docs-frame`, `.pane-docs .pane-title`, `.panel-separator`, `.logview-list` (`packaged.test.mjs:549`, `:949`, `:1238`, `:1348`).

The browser suite additionally uses `.pane-docs`, `.pane-tui`, `.pane-head`, `section.panel`, `.split` with `split-row` or `split-column`, `.terminal-note`, `.terminal-host`, `.source-banner`, `.record`, `.sign-in`, and roles `navigation`, `tab`, `dialog`, `radiogroup`, `radio`, `menu`, `menuitem`, `combobox`, `option`, `region` (`tests/desktop.spec.ts`).

### Toolchain compatibility

Pinned today (`package.json`): react and react-dom 19.3.0, vite 8.3.2, @vitejs/plugin-react 6.1.1, typescript 6.0.3, @playwright/test 1.63.0, every version exact. Registry state on 2026-10-05 (`npm view <package> version peerDependencies license`):

| Package | Version | Peer range that matters | Licence |
|---|---|---|---|
| tailwindcss, @tailwindcss/vite | 4.3.3 | vite ^5.2 to ^8 | MIT |
| radix-ui | 1.6.7 | react ^16.8 to ^19 | MIT |
| cmdk | 1.1.1 | react ^18 or ^19 | MIT |
| lucide-react | 1.52.0 | react ^16.5.1 to ^19 | ISC |
| class-variance-authority | 0.7.1 | none | Apache-2.0 |
| clsx, tailwind-merge, tw-animate-css | 2.1.1, 3.7.0, 1.4.0 | none | MIT |
| shadcn (CLI, not a runtime dependency) | 4.21.2 | none | MIT |
| storybook, @storybook/react-vite, @storybook/addon-a11y | 10.6.1 | vite ^5 to ^8, react ^16.8 to ^19 | MIT |

Every candidate admits the pinned React and Vite. All are permissive licences.

### Content security policy

The shell policy in `native/desktop/src-tauri/tauri.conf.json.in` is `script-src 'self'`, `style-src 'self' 'unsafe-inline'`, `font-src 'self'`, `img-src 'self' data:`. Tailwind compiles to a static sheet at build time, Radix positions through inline styles and a few injected style elements, cmdk and lucide ship no remote resource, so the candidates run under the existing policy without widening it. Nothing loads from a network origin.

### Latest packaged run

`build/windows-x86-64/e2e-desktop/desktop/test-results/packaged/20261005-200924/summary.txt` records 7 PASS, 8 FAIL, 1 SKIP. The desktop-shell audit's `session-proof-boundary` finding states that the packaged runner is integration evidence and that presentation work needs an independent desktop UX loop.
