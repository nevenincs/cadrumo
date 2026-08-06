---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:6a64fb9d70c08f8fa93adab05c092deb4dd8e48ae28ffbc14099e52f4a14bd9f'
step_id: 'S145'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

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
