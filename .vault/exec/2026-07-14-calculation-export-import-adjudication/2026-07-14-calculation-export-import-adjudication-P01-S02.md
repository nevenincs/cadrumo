---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:e2558fdb7b983df79bca8194d0a6254dcef2dbbcd952af0cf09be541911b2b8f'
step_id: 'S02'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---
# Publish the shared disposition taxonomy, evidence-field contract, and four-condition gate for the individual candidate Steps

## Scope

- `.vault/reference/`
- `.vault/audit/`

## Description

Check for an existing same-feature audit with:

```text
fd 'calculation-export-import-adjudication.*audit' '.vault/audit'
```

Confirm the canonical scaffold options with:

```text
uv run vaultspec-core vault add audit --help
```

Preview and then create the audit through the canonical CLI with both authorizing links:

```text
uv run vaultspec-core vault add audit --feature calculation-export-import-adjudication --title "Export and import candidate adjudication" --related '.vault/plan/2026-07-14-calculation-export-import-adjudication-plan.md' --related '.vault/adr/2026-07-14-calculation-export-import-adjudication-adr.md' --dry-run
uv run vaultspec-core vault add audit --feature calculation-export-import-adjudication --title "Export and import candidate adjudication" --related '.vault/plan/2026-07-14-calculation-export-import-adjudication-plan.md' --related '.vault/adr/2026-07-14-calculation-export-import-adjudication-adr.md'
```

Publish the shared disposition taxonomy, candidate evidence-field contract, and four-condition gate in the Reference. Seed the audit with the same scope and contract, without adding candidate adjudications.

Verify the feature documents and bounded diff with:

```text
uv run vaultspec-core vault check frontmatter --feature calculation-export-import-adjudication
uv run vaultspec-core vault check links --feature calculation-export-import-adjudication
uv run vaultspec-core vault check body-links --feature calculation-export-import-adjudication
uv run vaultspec-core vault check placeholders --feature calculation-export-import-adjudication
uv run vaultspec-core vault check schema --feature calculation-export-import-adjudication
uv run vaultspec-core vault check dangling --feature calculation-export-import-adjudication
rg -n '^related:|calculation-export-import-adjudication-(plan|adr)' '.vault/audit/2026-07-14-calculation-export-import-adjudication-audit.md'
rg -n '^### Disposition taxonomy$|^### Candidate evidence-field contract$|mandate_met|exact_authority_met|canonical_gap_met|eligible_met' '.vault/reference/2026-07-14-calculation-export-import-adjudication-reference.md' '.vault/audit/2026-07-14-calculation-export-import-adjudication-audit.md'
git diff --check -- '.vault/reference/2026-07-14-calculation-export-import-adjudication-reference.md' '.vault/audit/2026-07-14-calculation-export-import-adjudication-audit.md' '.vault/exec/2026-07-14-calculation-export-import-adjudication/2026-07-14-calculation-export-import-adjudication-P01-S02.md'
```

## Outcome

- The Reference now defines one seven-value disposition taxonomy with a deterministic selection order.
- The candidate contract keeps mandate, exact authority window, canonical implementation state, real evidence or specimen state, retirement, evidence block, gate booleans and result, disposition, and next action separate.
- The gate records `mandate_met`, `exact_authority_met`, `canonical_gap_met`, and `eligible_met` as booleans. Its result passes only when all four are true.
- The audit exists with correct plan and ADR relationships. It contains only the shared scope and contract; individual candidate outcomes remain for their authorized Steps.
- No production source, tests, or registry data changed, and this Step authorizes no candidate implementation.

## Notes

- The dry run reported the exact audit path before the mutating command created it.
- The audit scaffold was created once without `--force`; no existing audit was overwritten.
- The feature-filtered frontmatter, link, body-link, placeholder, schema, and dangling-link checks exited successfully. They emitted inherited repository stem-collision warnings and a graph-cache atomic-write fallback warning; the bounded status check showed no graph-cache change.
- The audit has both required related links and no scaffold comments. The contract marker lookup found both Reference sections and all four gate fields in the Reference and audit. `git diff --check` reported no whitespace errors.
- The P01.S02 plan checkbox remains open for parent review. Nothing was staged or committed.
