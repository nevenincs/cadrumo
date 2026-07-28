---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S174'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S174 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Regenerate terminology coverage from authoritative sources and reject removed command tokens and ## Scope

- `src/cadrumo/_data/terminology/evaluation/coverage-report.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate terminology coverage from authoritative sources and reject removed command tokens

## Scope

- `src/cadrumo/_data/terminology/evaluation/coverage-report.json`

## Description

- Regenerate the committed terminology corpus-coverage report from authoritative sources.
- Confirm the regeneration drops removed CLI command tokens and picks up the current grammar.

## Outcome

This is the one W05.P17 Step with a committed generated artefact. Regenerated
with `python -m dev.docs.terminology.coverage report`, which recomputes coverage
from the committed relevance mapping and the live command tree and writes
`coverage-report.json`. The regeneration produced the expected drift: it drops the
removed CLI tokens `cli:app.maintenance.profile_bundle_reconcile` and
`cli-option:aeat app ledger import:path`, and picks up the current grammar
`cli:app.maintenance.reconcile` and `cli:config.profile.censo.pull`. The live tree
was confirmed stable at 290 leaves (it carries `reconcile`, not the retired
`profile-bundle-reconcile`, and carries `censo pull`), so the diff is the stale
committed report catching up to a stable surface, not a tree change.

The report is a holistic derived artefact, so the same regeneration also absorbs
committed casilla and legal corpus drift from other campaigns (29 new
casilla-records, 5 legal targets) since the last regeneration. Every corpus source
was committed-clean in the working tree, so no peer working-tree state was swept;
the report simply reflects current committed reality. Landed at HEAD
`b3fc6d22fb4b3567d01b97a05e97dfc147234303`.

Command (gate): `uv run --no-sync pytest -p no:cacheprovider -n0 -m "unit or
integration" -o addopts="" dev/docs/terminology/tests/test_coverage.py`. Collected
6, `6 passed in 10.74s`, exit code 0, at HEAD
`b3fc6d22fb4b3567d01b97a05e97dfc147234303`.

## Notes

The regenerated artefact was committed separately as an explicit-pathspec commit
naming only `coverage-report.json`, with the incidental casilla/legal drift
disclosed in the commit message. Same peer core-import block as the sibling docs
Steps delayed the start; not touched, cleared on the peer's landing.
