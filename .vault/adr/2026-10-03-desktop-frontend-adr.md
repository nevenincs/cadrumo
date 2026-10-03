---
tags:
  - '#adr'
  - '#desktop-frontend'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:146041a441b10ecfa2b322b1b5e7ea5c6af346cbda5be9c77ea9a12697696808'
related:
  - '[[2026-10-03-desktop-frontend-research]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
  - '[[2026-10-03-application-packaging-adr]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
---
# `desktop-frontend` adr: React desktop presentation and isolated prototype | (**status:** `accepted`)

## Problem Statement

The desktop needs a durable frontend stack and a reviewable UI while Python packaging and Rust application contracts are still being implemented.

## Considerations

The user explicitly requests Tauri, TypeScript, definition of the React stack, documentation and an optional native console/log view. Research findings F1-F5 in 2026-10-03-desktop-frontend-research establish ownership and the limits of current integration evidence.

## Considered options

- React with Vite and accessible primitives: selected; builds static local assets and leaves native policy in Rust.
- A server-rendered React framework: unnecessary server and routing machinery for this shell.
- A bare terminal window: insufficient for side-by-side user documentation and an independent Python console. The existing Textual TUI remains the main application workspace.

## Constraints

Own native/desktop/ only. Generated assets and caches live under the selected CMake binary directory. Consume canonical product identity and documentation content. Do not fork Settings, targets, package inventory, readiness rules or interpreter selection. No runtime management, downloads or private-data persistence in the prototype. Browser and native integration evidence remain separate.

## Implementation

We will use React, strict TypeScript and Vite, Radix accessible primitives, Lucide icons and CSS design tokens. Use React state for transient view state; defer server-state libraries until runtime query contracts exist. Lock dependency versions. Prototype the workspace, offline documentation reader, resizable optional console/log area, keyboard navigation and honest unavailable states. The user clarified in this session: Textual TUI is the main workspace, with documentation alongside. React owns the surrounding shell and welcome page; Python console and logs occupy an optional bottom pane. Do not build parallel React tax workflows. A minimal Tauri development host embeds the static assets without granting native frontend capabilities; its explicit preview WebView directory is not a delivered storage-policy decision.

xterm.js remains a terminal renderer candidate behind one component; portable-pty remains the native candidate requiring real interaction proof. No fabricated Python shell or successful package state. The follow-on bridge must reuse application-library Readiness and ChildConfiguration and generate frontend DTOs from their owning Rust contracts when stable. A browser prototype does not accept a new native protocol.

The current user instruction authorizes defining and implementing this frontend stack. This record refines desktop presentation only; it does not adopt the broader proposed storage/deployment policy in 2026-10-03-application-packaging-adr. Accepted Textual frontend boundaries continue to apply to Textual code. This React host neither replaces the TUI nor moves its implementation.

## Rationale

Research F1-F3 favors a static React shell that can evolve within the settled Tauri host without taking over unfinished native responsibilities. F4 makes macOS storage containment an explicit native acceptance obligation.

## Consequences

The UI can be reviewed now. The chosen presentation dependencies need version updates and accessibility testing. Packaged Textual/Python, PTY backpressure and cleanup, WebView write containment, shared CMake enrollment and execution on all four required targets remain follow-on integration work. No approval of those unresolved details follows from frontend acceptance.
