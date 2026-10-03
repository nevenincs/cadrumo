---
tags:
  - '#audit'
  - '#desktop-frontend'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:49a8cd061ff290b28a44d0091b046da8314619175a3f449b9b0def32092e34a0'
related:
  - "[[2026-10-03-desktop-frontend-plan]]"
  - "[[2026-10-03-desktop-frontend-adr]]"
---
# `desktop-frontend` audit: frontend prototype and native host boundary

## Scope

Review of S01 in 2026-10-03-desktop-frontend-plan, covering new native/desktop files and their governance records on 2026-10-03. The user clarified Textual as the main workspace with documentation alongside; Python console/logs are optional below. Review uses actual production-build browser execution and the compiled Tauri host, without package or runtime doubles.

## Findings

### frontend-behavior | low | Frontend scope passes with explicit integration limits

The React shell presents the main Textual viewport, welcome page, five canonical explanatory chapters, independently controlled documentation and console/log panes, keyboard navigation and resizing. Three Playwright tests passed against static production assets, including offline navigation and desktop/narrow layouts. The collapsed-navigation label defect found on the first browser pass was repaired and the affected test passed. Product identity and SVG are read from their canonical owners; no taxpayer records, native readiness results or Python responses are fabricated. Source inspection found no native invoke commands, filesystem/shell plugins, browser persistence, automatic downloads or runtime management.

### native-window | low | Native execution remains pending in an interactive desktop

Tauri compiled a Windows cadrumo.exe with static frontend assets. The native smoke attempted real WebView creation and failed with HRESULT 0x80070578, invalid window handle. The executing process is in Session 0 and Environment.UserInteractive is false. This is an execution evidence gap, not proof that interactive desktop rendering works. No scheduled task, service, desktop bridge or runtime-management workaround was used. The repeatable native check records failure diagnostics under build/desktop-prototype/desktop/verification/native-smoke.json. Repeat desktop-host-test in an interactive Windows session before accepting native window behavior.

### dependency-boundary | low | Packaged PTY and all platform acceptance remain open

xterm.js lifecycle and resize are exercised; its input is disabled. portable-pty and the bundled interpreter have not been integrated or proved. Native application Readiness and ChildConfiguration still own policy; the handover identifies missing PTY-facing access and future owner-generated DTOs without inventing a second protocol. CONTRACT.md retains separate Windows x64, Linux x64, Linux ARM64 and macOS ARM64 acceptance rows. macOS native startup refuses pending a supported WebKit storage solution and OS write tracing. Tauri dataStoreIdentifier does not establish the required filesystem root.

### build-and-docs | low | Prototype output and documentation are deliberately bounded

Frontend assets, native source snapshot, Tauri-generated schemas, icons, Cargo outputs and evidence live under the selected CMake binary directory. Only ignored frontend/node_modules contains development dependencies beside source. Host build uses locked Cargo dependencies. Full root-CMake enrollment, package-manifest staging, canonical localization and full Sphinx output remain integration work. The reader includes five existing explanatory pages, converts inline MyST roles/anchors and rejects fenced Sphinx directives. Missing full-manual references display a visible notice. The build reports a large initial JavaScript chunk, primarily the terminal and reader dependencies; it remains a prototype performance observation, not a failing gate.

## Recommendations

S01 frontend verification: PASS. Native window and packaged integration acceptance: PENDING, with no critical or high code findings in this review. Keep those claims distinct at handover.

Verification evidence for the current desktop source: locked npm ci passed; npm run check passed (strict TypeScript, ESLint, script syntax and Prettier); production Vite build passed; three Playwright tests passed; Rust fmt and cargo clippy --locked -- -D warnings passed; Tauri debug build passed. Browser results and screenshots live under build/desktop-prototype/desktop/test-results and test-results.json. Native failure evidence is separate under desktop/verification. Python application checks were not run because no Python source, package owner or shared native policy was changed. Code semantic search was unavailable with quiesce_admission_closed; vault search and targeted source inspection supplied grounding.
