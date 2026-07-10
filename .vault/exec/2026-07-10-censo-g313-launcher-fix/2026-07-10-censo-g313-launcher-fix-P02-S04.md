---
tags:
  - '#exec'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S04'
related:
  - "[[2026-07-10-censo-g313-launcher-fix-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-g313-launcher-fix with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-10-censo-g313-launcher-fix-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Capture the authenticated ZK censal panel component structure with identity redacted to ground the parser field anchors and ## Scope

- `src/aeat/adapters/outbound/aeat/sede/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Capture the authenticated ZK censal panel component structure with identity redacted to ground the parser field anchors

## Scope

- `src/aeat/adapters/outbound/aeat/sede/tests/`

## Description

Drove the representation gate into the ZK censal surface under the warm live
session (read-only structural probes; value-like text masked, no personal value
or raw HTML persisted):

- Navigated `OVCT-CXEW/DialogoRepresentacion?ref=/wlpl/BU36-ASIS/M036/index.zul`
  and clicked CONFIRMAR (default representation, en nombre propio).
- Landed on the ZK app `BU36-ASIS/M036/index.zul`, title "Censos WEB".
- Enumerated the ZK component inventory and the panel captions.
- Attempted to open "Modificación de datos" to reach the prefilled 036 censal
  fields, and re-captured the panel.

## Outcome

Partial: the ZK-surface architecture is captured, but the actual censal field
anchors are NOT yet reachable by simple automation.

- The representation confirm lands on the multi-step **Censos WEB** ZK (ZKoss)
  tool (`BU36-ASIS/M036/index.zul`, title "Censos WEB"), a `z-panel` / `z-*`
  component tree (z-div, z-label, z-button, z-column, z-panelchildren, ...), not
  a flat data page.
- Its landing is a **menu**, not data: captions are "CENSOS WEB", "Baja",
  "Modificación de datos", and an "Errores y avisos" grid (Tipo / Número línea /
  Código / Descripción). None of the nine `_G313_LABELS` (Referencia catastral,
  Epígrafe IAE, …) are present at this level.
- Clicking "Modificación de datos" did not advance the panel (content length and
  URL unchanged) — the census data lives behind further in-tool ZK interaction
  (the prefilled 036 form), which requires deeper, fragile driving that a couple
  of automated attempts did not reach safely.

Decisive structural conclusion: there is no read-only "Mis datos censales"
projection. Reading census data means operating AEAT's census **modification**
tool (Censos WEB / prefilled 036) through several ZK steps. That is a
materially heavier and riskier integration than the ADR's re-point + parser
re-ground assumed — driving a modification SPA to perform a read.

## Notes

Stopped the automated deep-drive at 8 probes per the browser-automation
rabbit-hole discipline and the safety rule against operating AEAT
mutation/modification surfaces: going deeper means driving the census
modification form, where an accidental submit would mutate AEAT census state.
All probes were strictly read-only (navigation + CONFIRMAR into the read view;
never Enviar/Firmar/Presentar/Validar/Guardar) and no value was persisted.

`P02.S04` is left OPEN: the ZK component structure is captured to the Censos WEB
landing, but the prefilled-036 field anchors the parser needs are not, and a
product-direction question now stands (see the ADR update): whether to drive the
modification tool to read, seek a different censal read endpoint, or reconsider
live censo read (ADR option 4). Diagnostic probes live only in the session
scratchpad; no code changed; no destructive git operations were run.
