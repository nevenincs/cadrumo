---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f7d2ae49cf61c28a1332d6010e3604dd1d8d59950a145bd12902fa0590f0e8ee'
step_id: 'S158'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S158 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The emit deterministic per-capability census membership and reviewed disposition evidence for aggregate coverage buckets and ## Scope

- `dev/source_connectivity/cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# emit deterministic per-capability census membership and reviewed disposition evidence for aggregate coverage buckets

## Scope

- `dev/source_connectivity/cli.py`

## Description

- Retain the validated manifest and deterministic assignments in the successful check result.
- Project one output record per discovered capability in stable identity order.
- Carry the owning candidate, closed disposition, decision reason, and grounding references on every record.
- Include the complete membership ledger in comparison JSON instead of reporting counts alone.

## Outcome

Aggregate census buckets are now inspectable at per-capability granularity. An operator or later audit can
trace every capability to its owning row, reviewed disposition, reason, and re-fetchable grounding while
the canonical manifest remains compact and authoritative.

## Notes

Ruff passed, the projection unit test passed, and a live explicit-candidate projection produced 16 stable
records. Full selector projection remains correctly blocked by the concurrent ingress-surface drift rather
than refreshing its digest from peer work in progress.
