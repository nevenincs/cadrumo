---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S07'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Update the aeat-cli-pull-and-file-standard rule source (it cites censo pull as a worked example), propagate with vaultspec-core sync, and prune stale terminology relevance rows and complexity-baseline entries for deleted modules and ## Scope

- `.vaultspec/rules/rules/project/aeat-cli-pull-and-file-standard.md`
- `src/aeat/_data/terminology/relevance/relevance.json`
- `dev/audit/complexity_baseline.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the aeat-cli-pull-and-file-standard rule source (it cites censo pull as a worked example), propagate with vaultspec-core sync, and prune stale terminology relevance rows and complexity-baseline entries for deleted modules

## Scope

- `.vaultspec/rules/rules/project/aeat-cli-pull-and-file-standard.md`
- `src/aeat/_data/terminology/relevance/relevance.json`
- `dev/audit/complexity_baseline.json`

## Description

- Confirm the `aeat-cli-pull-and-file-standard` rule source
  (`.vaultspec/rules/aeat-cli-pull-and-file-standard.md`) cites the retired
  `config profile censo pull` verb only as a historical worked example, not as
  a live surface, and that the generated `.claude/rules/` copy is in sync.
- Confirm `src/cadrumo/_data/terminology/relevance/relevance.json` and
  `dev/audit/complexity_baseline.json` carry no stale rows for the deleted
  `_profile_censo`, `_censo_live`, or sede `_censo` modules.

## Outcome

No production edit was required: an earlier landing under this feature
(`3a48c4fe87` / `b2ea04d6a8`) already re-authored the rule source's worked
example onto the retirement.

- `.vaultspec/rules/aeat-cli-pull-and-file-standard.md` "Good" list already
  reads: "(The former `aeat config profile censo pull` was retired with the
  live censo scrape per `2026-07-11-censo-operator-manual-enrolment-adr`;
  censal facts are operator-manual.)" — this cites the retirement, not a live
  verb, satisfying `operator-harness-cites-live-cli-surface`.
- The generated `CLAUDE.md` copy of this rule carries byte-identical prose to
  the `.vaultspec/rules/` source (confirmed by direct comparison); no
  `vaultspec-core sync` drift to propagate.
- `rg` for `_profile_censo|_censo_live|sede/_censo\b` across
  `src/cadrumo/_data/terminology/relevance/relevance.json` and
  `dev/audit/complexity_baseline.json` returns zero hits; both files carry no
  stale rows for the deleted modules.

## Notes

None. This Step closes as verification-only: the rule-source re-authoring and
baseline pruning already landed under this feature's P02 wave.
