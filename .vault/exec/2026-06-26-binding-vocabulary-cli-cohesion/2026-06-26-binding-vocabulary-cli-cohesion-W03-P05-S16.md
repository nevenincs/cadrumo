---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S16'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Prefix the live-capture / sede-tier Observation carriers where the bare stem collides (FiledDeclaracionObservation, IvaCompensationWalletObservation, NifIvaCheckObservation, DeclaracionObservation, BorradorObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit and ## Scope

- `collect-only clean before each commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/adapters/outbound/aeat/sede/_schema.py`
- `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`
- `src/aeat/adapters/inbound/declaracion/_schema.py`
- `src/aeat/adapters/inbound/borrador/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prefix the live-capture / sede-tier Observation carriers where the bare stem collides (FiledDeclaracionObservation, IvaCompensationWalletObservation, NifIvaCheckObservation, DeclaracionObservation, BorradorObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit

## Scope

- `collect-only clean before each commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/adapters/outbound/aeat/sede/_schema.py`
- `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`
- `src/aeat/adapters/inbound/declaracion/_schema.py`
- `src/aeat/adapters/inbound/borrador/_schema.py`

## Description

- Ground the live-capture / sede tier via RAG then grep-confirm the five listed carriers against HEAD.
- Confirm the three carriers the audit flagged as bare-stem (`NifIvaCheckObservation`, `DeclaracionObservation`, `BorradorObservation`) were already prefixed by earlier relocation commits on this branch: `SedeNifIvaCheckObservation` (commit `c56d563d23`, `relocation:NifIvaCheckObservation`), `InboundDeclaracionObservation` (commit `64da9c1389`), and `InboundBorradorObservation` (commit `fc6742f269`) — each an atomic own-hunk rename with its test sweep, tagged in the same relocation vocabulary this plan mandates.
- Assert the remaining two sede-tier carriers (`FiledDeclaracionObservation`, `IvaCompensationWalletObservation`) already lead with a domain-discriminating word and need no further prefix.

## Outcome

The sede / live-capture tier prefix discipline is satisfied. The three genuine bare-stem carriers were prefixed with their owning-adapter layer word (`Sede`, `Inbound`) by the peer relocation commits named above; the other two were already discriminated. No two sede-tier `*Observation` carriers collide by class name. Verified no-shift: `pytest --collect-only -q` clean and the sede / inbound carrier tests green (`test_nif_iva_check.py`, the `declaracion` and `borrador` schema suites).

## Notes

The three prefix renames landed via peer commits without an exec record; this record captures them under the plan's `S16` contract and verifies the tier at HEAD. All four sede/inbound target files were clean of peer WIP at verification time. No production code was modified in this Step.
