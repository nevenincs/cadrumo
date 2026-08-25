---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:423f283aaeca21467bc161144ac06dfec1678e164defd41ba8a5f4bf58b8f57f'
step_id: 'S108'
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
     The S108 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The adjudicate M296 withholding-row semantics and source ownership from official evidence and ## Scope

- `.vault/research/2026-08-22-m296-row-source-grounding-research.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# adjudicate M296 withholding-row semantics and source ownership from official evidence

## Scope

- `.vault/research/2026-08-22-m296-row-source-grounding-research.md`

## Description

- Located the M296 lifecycle through semantic discovery, then read its
  registry revision, type-2 exporter, typed candidate, source mesh, encrypted
  retention owner, census, and focused tests.
- Checked the official BOE order, AEAT GI22 procedure, 2024 registry design,
  and current 193/296 note against the locally pinned source hashes.
- Recorded the row-identity and Annex-association requirements, and compared
  them with the current candidate grouping and retention-store schema.
- Ran exact redeclaration searches for an encrypted M296 repository,
  persistence/revision/replay owner, and live resolver before recording the
  research result.

## Outcome

Official evidence supports refusing a connection at this step. The present
encrypted M180/193 owner and the current M296 candidate do not preserve the
full non-resident type-2 recipient identity, conditional legal fields,
record grain, declarant record identifier, provenance, or replay/review chain.
Manual box 04 and caller-populated export rows remain distinct from a
canonical recipient-row source. The research identifies the bounded reopening
requirements for a later, separately authorized source-owner/resolver step;
it creates no runtime or census change.

## Notes

- The source-kind spelling is not a dormant name mismatch: `withholding296`
  is present in the taxonomy and candidate. The dormant defect is the lossy
  grouping/synthetic record identifier and absence of a durable secure owner.
- `pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_modelo_296_registry.py`
  passed 3 tests. Focused Ruff checks passed.
- The repeated-record module is integration-marked. Its integration invocation
  exceeded the shared runner's 30-second output-capture limit and exited
  without a terminal summary, so this record does not claim that test as
  passed. The feature Vault hard gates were clean; its remaining warnings are
  pre-existing template, markdown, and two unrelated research-reference
  warnings.
