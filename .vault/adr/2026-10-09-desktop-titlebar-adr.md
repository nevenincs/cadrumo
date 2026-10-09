---
tags:
  - '#adr'
  - '#desktop-titlebar'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:4f4be3876e302b12d86eae521b429bf940fe6d2be86177759fc492ece172b8f6'
related:
  - "[[2026-10-09-desktop-titlebar-reference]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# Desktop title bar | (**status:** `accepted`)

## Problem Statement

The approved header must replace native title chrome and the duplicated Settings account controls without bypassing documentation isolation or the existing account authority.

## Considerations

The supported Tauri window APIs and existing source boundaries are recorded in 2026-10-09-desktop-titlebar-reference. The operator authorized this implementation on 2026-10-09 after approving the existing dev display mockup.

## Considered options

Use supported Tauri native window methods behind token-checked app commands, chosen. Granting core window JavaScript capabilities risks documentation-frame access and conflicts with the existing shell isolation contract. Platform-specific window-manager patches and new plugins are unnecessary.

## Constraints

The shared header owns the application logo/title, active account display and one account dropdown. Settings contains frontend preferences only; retire its Account component and switcher. Sign out appears only in the account dropdown. Profile selection is available only while signed out, from the existing coherent listing, and named login remains the action that changes the product's selected profile. Reuse the existing password and profile-creation dialog; it is a credential form, not a second Settings account surface.

Window commands are a closed typed set behind the per-launch token, operate only on the invoking main window, and call supported Tauri Rust methods. No plugin capability, new native dependency, ambient token or documentation bridge action is added. Close must request normal app shutdown and preserve cleanup refusal. Maximized/fullscreen changes are observed without polling. Dragging excludes interactive account and window controls; double-click toggles maximize. OS resizing, placement and snapping remain native responsibilities.

Windows and Linux remove window decorations. The existing macOS application refusal remains; this work does not broaden platform admission. Existing window-state persistence stays Rust-owned.

## Implementation

Promote the approved header to product composition, retire the separate visual-study implementation, publish typed window commands and Host window access, and adapt scenario and packaged checks to the authorized account location change. Keep generated localization in its canonical workflow and use existing shared controls and tokens.

## Rationale

Supported Tauri methods provide native window behavior without custom window-manager patches. One account controller and one header account menu avoid conflicting profile and sign-out surfaces while preserving runtime authentication semantics.

## Consequences

The desktop IPC gains a bounded window-control interface. Browser controls remain unavailable outside a native host. Native acceptance needs platform execution; shared rendering does not prove Linux window-manager behavior. Reconsider if native macOS application admission is implemented or native snapping requirements exceed Tauri's supported behavior.
