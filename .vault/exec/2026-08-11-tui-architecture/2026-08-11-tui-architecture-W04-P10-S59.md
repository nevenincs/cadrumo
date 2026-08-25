---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:16229cf3d5db552c8817c1129e925d1240c63c97e98fccc812e0e2b11ec8f332'
step_id: 'S59'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S59 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Prove the relocation is behavior-preserving before any root app or navigation join is introduced and ## Scope

- `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the relocation is behavior-preserving before any root app or navigation join is introduced

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`

## Description

- Exercise registration, recovery confirmation, login, and manager projection through the real encrypted-profile custody path.
- Exercise flow submission and Modelo work review against real application contracts without mocks or monkeypatches.
- Assert every relocated class belongs to its public defining module and has exactly one production TUI AST definition site.
- Assert TUI package namespaces are inert and contain no static, relative, or dynamic forwarding imports.
- Keep devtool parity out of this step until S57 gives those tools public defining modules.

## Outcome

Relocated profile, secret, flow, and Modelo surfaces preserve their behavior before the root application and navigation join. The parity suite imports only public defining modules, finds one production definition per relocated class, and proves package namespaces do not forward symbols.

The serial integration suite passes three cases. The complete import-hygiene and zero-remnant migration suite passes all 63 cases. Independent review approved the remediated step with no findings.

## Notes

The initial candidate reached underscore-private devtool modules. The quality gate rejected those imports, so the case was deleted rather than allowlisted. S57 owns the required hard move to public devtool defining modules and its later parity evidence.

The profile custody test is intentionally serial because it exercises process-global active-profile context and real secure storage; parallel workers can interfere with that state.
