---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:defc46ec1abae62610b544daf329a6d19400cf1f9ec72529d8252e1dc0f755ca'
step_id: 'S07'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

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
