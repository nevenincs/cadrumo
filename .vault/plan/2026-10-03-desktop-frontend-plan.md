---
tags:
  - '#plan'
  - '#desktop-frontend'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-10-03-desktop-frontend-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:c70a395a20f1541e44c6abf65106430fb4312dd3b4aa6ddf73da858e6dfb61fc'
---

# `desktop-frontend` plan

## Description

Approved 2026-10-03

Authorization: the user asks to focus on prototyping the actual desktop frontend while dependencies are being built and explicitly asks to define the React stack now. S01 implements that scope. The supplied broader handover remains the future native integration acceptance contract, not a prerequisite for frontend work.

2026-10-03-desktop-frontend-adr governs the presentation stack and owner boundaries. 2026-10-03-runtime-without-service-manager-adr prohibits runtime management. Own new native/desktop files; preserve all concurrent native/application, interpreter, platform, root CMake, documentation and package-generator changes. Source placement is confirmed against the current native inventory and core packaging plan. The user clarified during execution: the Textual TUI is the main workspace, documentation opens alongside, and Python console/logs are optional below. The React shell does not implement parallel tax workflows. A minimal Tauri development host embeds the assets with no native capabilities and requires an explicit preview WebView directory; this does not settle delivered storage policy. No taxpayer data or successful backend results are fabricated.

## Steps

- [x] `S01` - Build and verify the React desktop frontend prototype with canonical documentation, optional console and logs, and an explicit native-integration handover; `native/desktop/`.

## Parallelization

Execute S01 in this session. Other sessions retain native dependencies and shared build ownership. Generated frontend outputs use an isolated desktop subtree of an explicitly selected CMake binary directory; no shared cleanup or native build races.

## Verification

Verify locked install, strict TypeScript, lint/format, production static build and browser interaction covering navigation, documentation content, optional panes, keyboard resizing and terminal mount/unmount. Test with network disabled after local assets load. Inspect layout at desktop and narrow widths. Review the integrated prototype and record exact evidence. These checks establish frontend behavior only.

Leave packaged PTY input/resize/Unicode/paste/mouse/backpressure/exit/cleanup, hostile ambient Python, read-only relocation, real package readiness and OS write tracing open in the integration handover. Required target rows are Windows x64, Linux x64, Linux ARM64 and macOS ARM64; no browser result closes them. macOS storage path containment needs a public supported API investigation and process write traces before release. Root CMake enrollment and manifest staging wait for the foundation handoff.
