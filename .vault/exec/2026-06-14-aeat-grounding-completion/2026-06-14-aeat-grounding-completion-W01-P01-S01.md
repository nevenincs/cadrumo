---
tags:
  - '#exec'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S01'
related:
  - "[[2026-06-14-aeat-grounding-completion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-grounding-completion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-14-aeat-grounding-completion-plan placeholders are machine-filled by
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
     The Author módulos exclusion magnitudes as registry parameters: 250.000 EUR general rendimientos, 125.000 EUR operaciones con obligación de factura, 250.000 EUR agrícolas/ganaderas/forestales, 250.000 EUR volumen de compras — grounded ley-35-2006:art-31 + dt-32 + Orden de módulos and ## Scope

- `src/aeat/_data/registry/aeat/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author módulos exclusion magnitudes as registry parameters: 250.000 EUR general rendimientos, 125.000 EUR operaciones con obligación de factura, 250.000 EUR agrícolas/ganaderas/forestales, 250.000 EUR volumen de compras — grounded ley-35-2006:art-31 + dt-32 + Orden de módulos

## Scope

- `src/aeat/_data/registry/aeat/`

## Description

- Author the corpus excerpt `corpus/normatives/html/ley-35-2006-dt-32.html` with the
  verbatim LIRPF DT 32ª text (the 150.000/75.000 → 250.000/125.000 EUR override and the
  150.000 → 250.000 EUR volumen-de-compras override), from the BOE consolidated text via a
  secondary source, with an explicit agent-authored provenance header.
- Author `legal/irpf-estimacion-objetiva.toml`: the `[legal."ley-35-2006:dt-32"]`
  legal-authority reference (corpus_ref + document_id + permalink + required_text), and three
  grounded `[parameters."lirpf-dt-32:eo-exclusion-*"]` magnitudes — 250.000 EUR (rendimientos
  conjunto), 125.000 EUR (operaciones con factura), 250.000 EUR (volumen de compras) — each
  `legal_refs = ["ley-35-2006:dt-32"]`.

## Outcome

The módulos exclusion magnitudes now exist as grounded registry values (audit finding V3
closed at the data layer). Verified: `load_legal_parameters_only` loads all three params
(250000/125000/250000 EUR); the STRICT corpus cross-check (`verify_legal_reference`,
corpus_strict=True) passes — every `required_text` is found in the authored corpus; 154
registry/corpus tests pass (catalogue verification, corpus provenance, corpus round-trip
gate). The agrícolas/ganaderas/forestales 250.000 EUR limit is deferred (it is art. 31.1.3ª.b
base, not a DT 32ª override, so it needs art. 31 grounded first).

## Notes

OPERATOR REVIEW REQUIRED — the legal catalogue is a human-reviewed, filing-grade surface
(`ReviewStatus = Literal["reviewed"]`). The DT 32ª legal entry and corpus are AGENT-AUTHORED;
`reviewed_by` honestly records "claude-opus (agent-authored; operator to confirm BOE
year-list)" rather than falsely claiming human review. The operator MUST confirm the corpus
text against the official BOE consolidation — in particular the exact ejercicios year-list,
which shifts with each annual prórroga — and re-stamp `reviewed_by` before this grounding is
relied on as filing-grade. The grounding gate validates self-consistency (required_text ⊆
corpus), not BOE-faithfulness; that is the human reviewer's responsibility by design.

W01.P02 (the advisory exclusion gate that consumes these magnitudes) is NOT yet built: it
depends on a declared estimación-objetiva volume input the profile/ledger surface may not yet
collect (the regime is currently selected by boolean flags). Building the gate requires first
establishing where the operator declares the volume to compare against the magnitude —
tracked as the next step.
