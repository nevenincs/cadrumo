---
tags:
  - '#audit'
  - '#desktop-terminal-theme'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:b968d6ec997a23ce4ba55fb27c5b1ba2c3ea6d0503f5b84c5469c30d2c166438'
related:
  - "[[2026-10-07-desktop-terminal-theme-plan]]"
---

# `desktop-terminal-theme` audit: `Integrated terminal appearance`

## Scope

Integrated desktop appearance propagation across xterm, Textual themes, PTY launch identity and presentation-only appearance requests. Root owns shared verification; startup_review independently reviews source. Review covers S01 of 2026-10-07-desktop-terminal-theme-plan and the desktop-shell appearance amendment, including uncommitted changes.

## Findings

### bold-palette | high | Bold ANSI promotion changes text into surface colors

Independent review found xterm's default bright-color promotion would turn bold accent/primary ink into the dedicated TUI's semantic surface slots. Corrected by drawBoldTextInBrightColors=false only for the TUI, with real bold Textual panel-title pixel assertions in both appearances. Visual inspection also found primary buttons inherited foreground ink on a colored fill; the native-ANSI CSS now uses the background slot as contrasting text. Final theme browser tests (four) and Python themes (34) pass after corrections.

### corrected-review | low | No remaining code findings after contrast correction

Independent re-review confirms the correction, role and OSC tests, and isolation of the dedicated TUI palette. Native tests and scoped Python checks were pending at that review. The final Python emission test, lint, formatting and ty now pass. Native checks are being rerun after concurrent log API edits settle; their earlier failures are outside this patch.

### final-verification | low | PASS after integrated browser and native verification

Independent reviewer reports no remaining code findings. All 15 native terminal tests, backend Clippy, production native build, 32 original Python theme tests and three new behavior/emission tests pass. Four final browser theme tests pass on the integrated frontend at build/desktop-theme-integrated-fixed/results, including live recoloring of real Textual output, bold role contrast, hidden Python palette updates, explicit dark override, exact OSC isolation, and DOM-renderer/system-theme changes. The earlier 18 font/scale/border checks pass and the corrected option affects only the separately verified TUI pane. Frontend types/lint/format and scoped Python ruff/format/ty pass. Integration found a concurrent log-refactor stale state reference that blanked the window; corrected to the available-source states predicate, plus three missing sign-in scenario fields. Those repairs remain with the separate log workstream. The native build does not update the installed Python package or Session 1 GUI.

## Recommendations

PASS. Package both the updated desktop binary and Python TUI module together for rollout. Session 1 installed GUI visual acceptance remains unverified from this session.
