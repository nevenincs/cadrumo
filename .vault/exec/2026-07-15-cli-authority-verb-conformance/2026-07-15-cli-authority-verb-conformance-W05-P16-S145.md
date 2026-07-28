---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S145'
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
     The S145 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Classify passphrase, recovery, reset start and resume, portable profile export, and subject-access export under exact risk keys, with both cleartext export purposes carrying the same handoff classification and ## Scope

- `src/cadrumo/application/operator_surface/_risk_table.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Classify passphrase, recovery, reset start and resume, portable profile export, and subject-access export under exact risk keys, with both cleartext export purposes carrying the same handoff classification

## Scope

- `src/cadrumo/application/operator_surface/_risk_table.py`

## Description

- Read the risk table and confirm each named custody, reset, and export purpose carries an exact risk key.
- Compare the two cleartext export purposes against each other.

## Outcome

Every named purpose is classified, and the classifications are discriminating rather than uniform. Passphrase change and recovery rotate are destructive; recovery status, verify, and create are not, with create carrying a recorded rationale about eliciting human confirmation on the MCP surface. The reset lifecycle is split correctly: start and resume are destructive while status is a read, and the site records that the split inherits the pre-split destructive posture.

The specific requirement that both cleartext export purposes share one classification holds: the portable profile export and the subject-access request are both declared handoff, so an operator cannot read one as safer than the other when each produces the same cleartext artefact.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
