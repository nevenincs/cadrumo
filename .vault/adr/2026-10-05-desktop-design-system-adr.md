---
tags:
  - '#adr'
  - '#desktop-design-system'
date: '2026-10-05'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:cc654c0302fe49fa5847361c4571d88eff9b80c84c96ee0029e683b9636adba8'
related:
  - "[[2026-10-05-desktop-design-system-reference]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# `desktop-design-system` adr: `Desktop shell design system and browser development loop` | (**status:** `accepted`)

## Problem Statement

## Considerations

## Considered options

## Constraints

## Implementation

## Rationale

## Consequences

## Context

## Problem Statement

The desktop shell frontend has no component foundation. Each dialog, menu, palette, radio group and tab strip carries its own keyboard and focus code, one stylesheet holds every rule, and the sign-in view is an unstyled form. Its states can be seen only through a test fixture or a packaged run, because the browser host reports every capability unavailable (`2026-10-05-desktop-design-system-reference`).

On 2026-10-05 the user directed that the frontend keep React and Vite, adopt shadcn/ui on the Radix foundation as one centralized design system, gain a Storybook catalogue, and be developed in a browser against deterministic host scenarios, without compiling the desktop package. This record fixes the dependency set, the ownership boundaries of the design system, and the limits of the development-only host. Reversing any of them means rewriting every shell component.

## Considerations

- The shell policy admits only local scripts, styles and fonts. Every candidate runs under it unchanged (`2026-10-05-desktop-design-system-reference`, Content security policy).
- Shell colours are generated from the documentation palette, never copied (`2026-10-04-desktop-shell-adr`, Theme). A nested area can be always dark, so colour roles must resolve on every scheme boundary.
- The shell holds no runtime authority, and sign-in presents only the state the canonical commands report (`2026-10-04-application-sign-in-adr`). A browser stand-in that fabricates host answers must never be mistaken for that evidence, and must never ship.
- The frontend bundle carries no location, origin or environment variable name (`2026-10-04-desktop-shell-adr`, Constraints).
- The packaged acceptance suite drives the window through a fixed set of classes, ids and roles, and treats rail order and settings choice order as contracts (`2026-10-05-desktop-design-system-reference`, Selectors).
- Every package version in the frontend is pinned exactly, and the candidates admit the pinned React 19 and Vite 8 (`2026-10-05-desktop-design-system-reference`, Toolchain compatibility).
- Chrome strings exist only in the canonical locale catalogues, in four languages.

## Considered options

- **shadcn/ui source components on Radix, styled with Tailwind 4, catalogued in Storybook.** Chosen, by the user's direction. Radix supplies tested focus, dismissal and keyboard behaviour; the component source lives in the repository, so tokens and variants stay under one owner; everything is bundled.
- **Keep the hand-rolled components and add only a catalogue.** Rejected: each surface keeps its own focus and keyboard code, which is where the accessibility gaps are.
- **A packaged component library with its own theme engine.** Rejected: a second colour authority beside the generated palette, runtime style injection to audit against the policy, and variants owned outside the repository.
- **shadcn/ui on the Base UI foundation.** Not chosen: the user named Radix, and the official Command component composes with it.
- **Scenario selection inside the production entry, behind a build flag.** Rejected in favour of a separate development entry: an entry the production build never reads cannot leak by a mis-set flag.

## Constraints

**Dependencies.**
- Runtime additions are `radix-ui`, `cmdk`, `lucide-react`, `class-variance-authority`, `clsx` and `tailwind-merge`. Build-time additions are `tailwindcss`, `@tailwindcss/vite` and `tw-animate-css`. Development-only additions are `storybook`, `@storybook/react-vite` and `@storybook/addon-a11y`. Each is pinned to an exact version in `package.json` and the lockfile.
- Primitives are added from the official shadcn registry and then owned as source under `src/components/ui/`. The shadcn CLI is a tool, not a dependency.
- Nothing loads from a network origin, and the shell policy is not widened for this work.

**Tokens.**
- `src/generated/palette.css` stays the only source of colour values. One theme stylesheet maps it to semantic roles and exposes those roles to Tailwind. No component, story or variant declares a colour value of its own; overlay and shadow alphas are declared once in the theme.
- Roles are declared on every scheme boundary, so an always-dark area resolves its own values.
- Length, type, radius, density, elevation, layer and motion tokens have one declaration each. A component reads a token or a Tailwind utility bound to one, never a literal.
- The terminal ANSI palettes remain a declared exception, because xterm takes literal values.

**Ownership layers.** Dependencies point downward only.
- Tokens: the generated palette, the theme stylesheet and the length tokens.
- Primitives, `src/components/ui/`: generic controls with their variants. They import no product component, no shell module, no IPC type and no string catalogue.
- Product components, `src/components/`: sign-in dialog, command palette, settings, pane headers, rail, account controls, log view. They compose primitives and never declare a control dimension or interaction pattern of their own.
- Composition, `src/App.tsx` and `src/shell/`: layout, the action registry and host interaction.
- Host access stays behind `Host`. Only `tauriHost` imports the Tauri API.

**Icons.** One library, `lucide-react`, bundled as inline SVG, read through one registry module that maps the shell's icon names. A glyph the library lacks is drawn once in that registry. This keeps the bundled inline set of `2026-10-04-desktop-shell-adr`.

**Development scenario host.**
- A third `Host` implementation serves deterministic, synthetic scenarios: signed out, signing in, signed in, wrong password, throttled, runtime unavailable, loading, empty and error.
- It is reachable only from a development entry page that the production build does not take as input. The production bundle contains none of its code, and a check on the built output proves that.
- It is selected explicitly, by opening that entry. The production entry keeps choosing between `tauriHost` and the browser host that fabricates nothing.
- The page labels itself as simulated. A scenario result is design and test evidence only; it is never evidence of authentication, of a native menu, or of any host contract.
- It simulates only what `Host` publishes. A native window action without a host contract is not drawn as if it existed.

**Sign-in presentation.** The sign-in view becomes a dialog in the shell origin, opened whenever the active profile has no live sign-in and the TUI pane would otherwise start. The submission rules of `2026-10-04-application-sign-in-adr` are unchanged: one dedicated submission, no automatic retry, status re-read after any failure, typed refusals shown undiminished, handover to the TUI for locked and recovery cases, hidden where unsupported. By that record's amendment of 2026-10-06 the dialog also names the profile under a label, offers the choice between profiles and is the form that creates one; first run and other profiles hand over to the TUI only where the host offers no profile commands. The password is read from the field once, sent as bytes, cleared from the field and zeroed; it is never stored, logged or placed in component state.

**Settings.** The settings surface keeps the items of `2026-10-04-desktop-shell-adr` and the Account section of the sign-in decision, and gains one item the user approved on 2026-10-05: a display-language choice for this window, following Cadrumo's output language by default. It is a frontend preference that selects among the languages `desktop_environment` reports; it writes no product Settings and reaches no backend.

**Stable hooks.** The classes, ids, roles and orders listed under Selectors in `2026-10-05-desktop-design-system-reference` are kept on the redesigned components. A redesign does not edit a packaged assertion to pass.

**Catalogue.** Storybook renders the application's own components, theme and generated strings. Its static output goes under the build directory and is never packaged. The full application remains the composition preview.

## Implementation

We will rebuild the shell's presentation on shadcn/ui primitives over Radix, styled through Tailwind 4 with one theme stylesheet bound to the generated documentation palette, and develop it in a browser against a development-only scenario host and a Storybook catalogue.

- A bootstrap documented beside the frontend configures the standalone desktop project and runs the existing generators, which is everything `npm run dev` needs.
- A development entry page mounts the same `App` with the scenario host and a scenario switcher.
- The theme stylesheet replaces the role mapping in `styles.css`; `tokens.css` stays the length authority and is exposed to Tailwind.
- The palette is built on the official Command component, settings on Popover with radio groups, sign-in on Dialog, tooltips on Tooltip, the browser menu stand-in on the same menu styling, panel tabs on Tabs.

These are *hypotheses* within the constraints: the exact primitive list, file names, the form of the scenario switcher, the story layout, and whether the split and panel separators stay hand-written or move to a library.

## Rationale

Radix removes the per-component focus and keyboard code that the shell cannot verify surface by surface, and shadcn keeps the component source and its variants in the repository, so the generated palette remains the single colour authority. Tailwind is what those components are written in; centralizing its theme in one stylesheet is what keeps it from becoming a second token system.

A separate development entry makes the scenario host structurally absent from the product instead of conditionally absent, which matters because it fabricates sign-in answers. Keeping the packaged suite's hooks stable lets the redesign proceed without touching acceptance evidence it does not own.

## Consequences

**Benefits.**
- Every major interface state can be reproduced and refined in a browser without compiling the desktop package.
- One place defines tokens and variants; a new surface composes existing controls.
- Focus trapping, restoration, dismissal and keyboard operation come from one tested foundation.

**Accepted costs.**
- Nine bundled packages and three development packages to keep current.
- Stable hooks constrain markup: some classes stay only because acceptance reads them.
- Radix renders overlays in a portal on the document body, so an overlay takes the root scheme, not the scheme of the area that opened it.
- A browser scenario proves presentation and interaction, not the host. Native menus, WebView2 focus behaviour, the real sign-in command and window state still need focused checks in the Tauri window.

**Reconsider if:**
- the shell policy must drop `'unsafe-inline'` styles, which Radix positioning relies on
- the sign-in view moves to a dedicated window, as `2026-10-04-application-sign-in-adr` anticipates
- the documentation palette stops being the colour authority

Acceptance (user, 2026-10-05: the frontend design handover brief, confirmed the same day by the stated goal of a complete design system on React, shadcn, Tailwind 4, Radix and Storybook 10) authorizes the direction and does not mean any part of it is implemented.

### Amendment 2026-10-06: the rail gains a shortcuts group, and its order

Authorized by the user on 2026-10-06, who asked for the side rail to read: search; a separator; the window's toggles; a separator; new shortcut elements; a separator; the bottom panel's toggles.

The first rail group's order becomes search, docs home, TUI, then the shortcuts group, then console, Python and logs; settings stays alone in the last group. Search and docs home keep the first two positions, which are the only positions the packaged acceptance suite reaches by index (`native/desktop/tests/packaged/docs-ui.mjs:22`, `:102`), so no packaged assertion changes. The shortcuts group opens with one element that needs nothing from the host beyond `open_external`: the tax agency's electronic office, whose address is the product's own constant and is held to it by a test. Further shortcuts that need data or actions the host does not offer today (notifications, the profile's Drive folder, sync counts, the filing calendar) are not part of this amendment: each needs its own decision on how the shell may read profile data.

The stable-hooks commitment is otherwise unchanged.
