---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:709924ae03008c840bd1c66d990dc3985600c91f779cf124ba1e5b32c0387e66'
step_id: 'S14'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Regenerate the operator how-to and reference pages for ledger evidence from the frozen live surface

## Scope

- `docs/how-to/ledger-evidence.md`

## Description

- Correct the `ledger-evidence` how-to: the pull-folder step no longer offers `aeat app ledger link` as an evidence-binding alternative (link is invoice-only); fetched evidence binds via `aeat app ledger attach --attachment-id`.
- Confirm the generated CLI reference pages (`docs/cli/app/ledger.rst`, `cli-tree.json`) are gitignored build artefacts that regenerate against the live surface — no committed reference edit is needed, and their residual `--evidence-id` mentions belong to the retained `ledger evidence extract` command, not `link`.

## Outcome

- The ledger-evidence how-to is accurate against the frozen live surface: attach is the sole evidence door; link binds a reconciliation-catalogue invoice only. Documented-command conformance green on this surface (350 passed; the one failure is exec-authcert-p04's `config rekey` .seq). Commit `96bdc97ed9`.

## Notes

- The other forced how-to change (the import-bank-statements `link --evidence-id` paragraph + its `.seq`) landed with S07. This step's remaining scope was the pull-folder line and confirming the reference pages regenerate.
