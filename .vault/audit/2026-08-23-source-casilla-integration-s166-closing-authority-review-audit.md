---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a319c0e06dd91fbcb4204e781802b8b15e50ff85f9a1bbea4bb5dad835a467a3'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `source-casilla-integration` audit: `s166 closing authority review`

## Scope

Independent review of the S166 physical-closing observation, authority decision, prior-closing continuity, conflict retention, hard cutover, and tamper-sensitive provenance contracts.

## Findings

### s166-closing-authority-review | high | resolved resolution provenance was incomplete

The resolution now retains the authority-decision identity and fingerprint, selected or competing physical-observation identity and fingerprint, and prior-continuity-link fingerprint. Strict consistency checks refuse forged selected values, conflicts, coordinates, identities, and fingerprints.

### s166-closing-authority-review | medium | resolved prior continuity was self-asserted

The link now validates a canonical fingerprint of the immediately prior authoritative closing across activity, year, value, source fingerprint, and evidence. Valid source or value substitutions with a stale binding fail closed.

### s166-closing-authority-review | medium | resolved authority chronology admitted impossible provenance

The resolver now requires an authority decision to occur on or after the physical observation it names. The invariant applies to both physical-selected and movement-selected decisions retaining a competing observation.

### s166-closing-authority-review | low | resolved cents and evidence-role ambiguity

Closing resolutions and conflict diagnostics refuse sub-cent values, while physical-closing evidence admits each required closed role exactly once. FIFO, PMP, and COSTE_MEDIO remain distinct grounded acquisition-price bases.

### s166-closing-authority-review | pass | final domain contract is complete

Final independent review reported zero critical, high, medium, or low findings. Fifty focused domain tests, Ruff, and the type checker were clean.

## Recommendations

S167 must remove or refuse the legacy CLI `InventoryLedgerPayload.closing_stock` shape and carry the new authority inputs through secure ingress. S168 must compose the reviewed authority resolution into projection without rebuilding its invariants.
