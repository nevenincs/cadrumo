---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:9e0a834356be388eaf86943b4fc8ecb479adc8426ea03bd2d1cf188d90ef943d'
step_id: 'S14'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace minimo-descendientes-eligibility with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-08-04-minimo-descendientes-eligibility-plan placeholders are machine-filled by
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
     The Scope the Art. 58.2 missing-anchor advisory to descendants that actually carry a tranche and ## Scope

- `src/cadrumo/domain/contribuyente/family.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Scope the Art. 58.2 missing-anchor advisory to descendants that actually carry a tranche

## Scope

- `src/cadrumo/domain/contribuyente/family.py`

## Description

- Replace the cohabitation-and-age-under-three test in
  `DescendantInfo.art_58_2_window_anchor_missing` with the full Art. 58.1 non-income
  conditions, so a descendant carrying no tranche is not reported.
- Extend the silent-where-nothing-is-lost case table with an over-25 adopted descendant.

## Outcome

The missing-anchor advisory now fires only where a missing entry date actually costs the
taxpayer something: an older cohabiting adopted or fostered child who meets the Art. 58.1
non-income conditions. A descendant already under three takes the increase through the
ordinary limb regardless, one the statute excludes from the limb has no anchor to be
missing, one not cohabiting takes no minimo at all, and one over 25 with no discapacidad
carries no tranche for the increase to attach to.

The income ceilings are deliberately not applied, and the docstring says so. They need
registry figures this layer does not resolve, and an absent rentas figure is
non-excluding anyway, so the residual over-report is a descendant whose declared rentas
breach the ceiling - a case that already carries its own advisory.

## Notes

This was found by self-review after the axis had already landed, not by a gate. The
advisory would have reported a 30-year-old adopted descendant, which is noise in the one
channel the whole Art. 58.2 disclosure depends on - and an advisory that fires where
nothing is lost trains the operator to ignore it, which is the failure mode this
campaign's own closing audit documented for a sibling collector.

Recorded as a correction rather than folded into the preceding Step: the first landing
was not a clean pass, and a record that says so is worth more than one that reads clean.
