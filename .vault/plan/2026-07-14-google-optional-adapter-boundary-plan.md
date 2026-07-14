---
tags:
  - '#plan'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
tier: L1
related:
  - '[[2026-07-14-google-optional-adapter-boundary-adr]]'
  - '[[2026-07-14-google-optional-adapter-boundary-research]]'
  - '[[2026-07-14-google-optional-adapter-boundary-reference]]'
  - '[[2026-07-14-google-oauth-audit]]'
  - '[[2026-05-13-google-oauth-plan]]'
  - '[[2026-06-04-ledger-google-live-export-adr]]'
  - '[[2026-06-04-ledger-google-live-export-research]]'
  - '[[2026-06-03-ledger-google-live-export-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `google-optional-adapter-boundary` plan

Reconcile the misleading legacy Google backlog with shipped code and the accepted optional-adapter boundary, without creating a second implementation path.

## Description

The legacy plan contains 183 raw Step rows, of which 76 are checked and 107 are open. The current parser reports only 177 rows and 74 checked because repeated phase-local identifiers and suffixed identifiers are not a trustworthy execution model. An open checkbox therefore does not prove that product work remains.

The accepted boundary and its code Reference establish that OAuth desktop authentication, service-account impersonation, encrypted Drive mirroring, canonical attachment custody, consolidated Sheets export, typed Sheets pull, shared-engine calculation, and canonical ledger updates already exist. Google-specific escrow and restore, watched-inbox ingestion, reverse merge, and persistent Sheet-to-work-unit or calculation-revision mutation are intentionally outside the accepted design. This plan records those distinctions and retires the obsolete plan as an executable authority. It does not change production code or approve provider-neutral follow-on ideas.

The checked ledger-Google live-export plan is a second stale authority. Its five closed rows claim a bucket-ledger upload, a manual Sheet roundtrip, Gmail resolution, and self-skipping live tests that the current code and accepted boundary do not provide. Its same-feature ADR explicitly says it is a warning-closeout record with no runtime mandate. This plan supersedes that curation ADR and archives the historical feature without treating its checked rows as implementation evidence.

Execution requires a clean preflight for each target file, a current-HEAD comparison with the related ADR and Reference, and dry-run output for every Vault mutation. Stop if a target contains non-authored work, a dry run touches unrelated files, incoming references would break, the accepted boundary conflicts with current code, or completion would require product implementation or a new ADR.

## Terminology and disposition contract

- An ADR is the accepted architectural decision that authorizes or prohibits behavior. A checked historical plan row is not an ADR and is not proof that code shipped.
- Current HEAD is the commit reported by `git rev-parse HEAD` immediately before a Step. Because this is a shared worktree, every executor re-reads HEAD and the target diff before acting.
- A raw Step is every literal checkbox row in the legacy file. The parser view is the smaller set recognized by the canonical plan CLI after duplicate and malformed identifiers are collapsed.
- An active authority dependency is an incoming `related:` edge whose source still relies on the target as a current decision. Historical provenance may retain the same bare-stem edge because the Vault graph resolves archived targets.
- `S01` uses only these dispositions: `shipped-equivalent`, `retired-obsolete`, `moved-domain-not-approved`, `new-ADR-only`, and `genuine-current-gap`. Every one of the 183 rows records raw ordinal, displayed identifier, phase, checkbox state, claimed behavior, user mandate or goal, current code and test evidence, accepted ADR basis, disposition, successor owner or `none`, and duplicate-code risk. Finding any `genuine-current-gap` stops this documentation-only plan until that gap has its own approved ADR and plan.

## Execution command contract

Run from the repository root. Readiness requires `git rev-parse --show-toplevel`, `git rev-parse HEAD`, `uv run vaultspec-core --version`, `uv run vaultspec-core vault plan check .vault/plan/2026-07-14-google-optional-adapter-boundary-plan.md --json`, and `uv run vaultspec-core vault plan status .vault/plan/2026-07-14-google-optional-adapter-boundary-plan.md --json`. The plan check must have no findings, status must report L1 and 14 Steps, and every target must pass `git status --short -- TARGET` plus `git diff -- TARGET` ownership review.

After approval, scaffold one execution record per Step with `uv run vaultspec-core vault add exec --all-steps -f google-optional-adapter-boundary -r 2026-07-14-google-optional-adapter-boundary-plan --dry-run --json`, inspect the preview, then rerun without `--dry-run`. Use `apply_patch` only for prose. Use the following canonical mutations, always previewing first when the command exposes `--dry-run`:

- `S01`: `uv run vaultspec-core vault add audit -f google-optional-adapter-boundary --date 2026-07-14 -r 2026-07-14-google-optional-adapter-boundary-adr -r 2026-07-14-google-optional-adapter-boundary-plan --dry-run --json`, then the same command without `--dry-run`.
- `S02`: `uv run vaultspec-core vault link add 2026-05-13-google-oauth-plan 2026-07-14-google-optional-adapter-boundary-adr --dry-run --json`, then the same command without `--dry-run`; prose changes do not alter checkbox rows.
- `S03`: `uv run vaultspec-core vault set-frontmatter 2026-05-13-google-oauth-plan --tags '#plan' --tags '#google-oauth-legacy-plan-retirement' --dry-run --json`, then the same command without `--dry-run`.
- `S04` and `S05`: preview with `uv run vaultspec-core vault feature archive google-oauth-legacy-plan-retirement --dry-run --json`; the actual command omits `--dry-run` and is allowed only when `archived_count` is 1 and the sole move is the legacy plan.
- `S06`: `uv run vaultspec-core vault adr supersede 2026-06-04-ledger-google-live-export-adr --by 2026-07-14-google-optional-adapter-boundary-adr --dry-run --json`, then the same command without `--dry-run`; both ADR diffs are reviewed.
- `S07`, `S08`, and `S09`: run `uv run vaultspec-core vault link add SOURCE 2026-07-14-google-optional-adapter-boundary-adr --dry-run --json` and then without `--dry-run`, using respectively `2026-06-03-ledger-google-live-export-plan`, `2026-06-04-ledger-google-live-export-research`, and `ledger-google-live-export.index` as SOURCE. `S07` also uses `apply_patch` for historical-plan prose only.
- `S10` and `S11`: preview with `uv run vaultspec-core vault feature archive ledger-google-live-export --dry-run --json`; the actual command omits `--dry-run` and is allowed only when the four moves are exactly the ADR, plan, research, and index named by `S11`.
- `S13` and `S14`: run `uv run vaultspec-core vault feature index -f google-oauth --json` and `uv run vaultspec-core vault feature index -f google-optional-adapter-boundary --json`. This command has no dry-run surface, so preflight each target index and inspect its complete post-write diff.

## Steps

- [x] `S01` - Produce the definitive 183-row legacy Google disposition audit, recording raw-versus-CLI count drift and one evidence-backed disposition per row; `.vault/audit/2026-07-14-google-optional-adapter-boundary-audit.md`.
- [x] `S02` - Reconcile the legacy Google master plan authority chain and prose as a historical non-executable record without changing structural rows or claiming retired work was implemented; `.vault/plan/2026-05-13-google-oauth-plan.md`.
- [x] `S03` - Retag only the legacy Google plan as google-oauth-legacy-plan-retirement through the canonical metadata command; `.vault/plan/2026-05-13-google-oauth-plan.md`.
- [x] `S04` - Preview archiving google-oauth-legacy-plan-retirement, require archived_count 1, and record every incoming reference in the boundary audit; `.vault/audit/2026-07-14-google-optional-adapter-boundary-audit.md`.
- [x] `S05` - Archive only google-oauth-legacy-plan-retirement after its one-record preview proves every incoming reference remains valid; `.vault/_archive/plan/2026-05-13-google-oauth-plan.md`.
- [x] `S06` - Supersede the ledger-Google warning-closeout ADR with the accepted optional-adapter boundary through the canonical ADR supersede command; `.vault/adr/2026-06-04-ledger-google-live-export-adr.md + .vault/adr/2026-07-14-google-optional-adapter-boundary-adr.md`.
- [x] `S07` - Reconcile the checked ledger-Google live-export plan as historical evidence and link it to the accepted optional-adapter boundary without claiming a shipped live ledger roundtrip; `.vault/plan/2026-06-03-ledger-google-live-export-plan.md`.
- [x] `S08` - Link the ledger-Google research record to the accepted optional-adapter boundary while preserving its historical authority chain; `.vault/research/2026-06-04-ledger-google-live-export-research.md`.
- [x] `S09` - Link the ledger-Google feature index to the accepted optional-adapter boundary while preserving its historical authority chain; `.vault/index/ledger-google-live-export.index.md`.
- [ ] `S10` - Preview archiving ledger-google-live-export, require exactly its ADR, plan, research, and index, and record every incoming reference in the boundary audit; `.vault/audit/2026-07-14-google-optional-adapter-boundary-audit.md`.
- [ ] `S11` - Archive only ledger-google-live-export after its four-record preview proves the successor chain and every incoming reference remain valid; `.vault/_archive/adr/2026-06-04-ledger-google-live-export-adr.md + .vault/_archive/plan/2026-06-03-ledger-google-live-export-plan.md + .vault/_archive/research/2026-06-04-ledger-google-live-export-research.md + .vault/_archive/index/ledger-google-live-export.index.md`.
- [ ] `S12` - Update the master Google reconciliation audit with final counts, both retirement outcomes, and the no-production-code conclusion; `.vault/audit/2026-07-14-google-oauth-audit.md`.
- [ ] `S13` - Regenerate the Google OAuth feature index after both Google reconciliations land; `.vault/index/google-oauth.index.md`.
- [ ] `S14` - Regenerate the optional-adapter-boundary feature index after both Google reconciliations land; `.vault/index/google-optional-adapter-boundary.index.md`.
## Parallelization

Two streams may start in parallel. In the legacy-plan stream, `S01` through `S05` are ordered. In the ledger-Google stream, `S06` runs first, then `S07`, `S08`, and `S09` may run in parallel on separate documents. `S10` waits for `S04` and all three ledger-Google link Steps because it appends to the shared boundary audit; `S11` follows `S10`. `S12` waits for both archive Steps, `S05` and `S11`, so the master audit records the actual final state. After `S12`, `S13` and `S14` may run in parallel. A Terra xhigh executor owns the legacy-plan stream; a Terra high executor owns the ledger-Google stream and final indexes. A different Terra high or xhigh agent reviews each execution surface.

## Verification

- Each Step has exactly one Step execution record, and each checkbox is closed only through the canonical plan CLI after its evidence exists.
- The row audit accounts for all 183 raw rows and explains the 177-row parser view without treating checked obsolete rows as shipped behavior.
- The legacy plan names the successor authority, contains no claim that retired mechanisms were implemented, and is safely isolated and archived. If incoming references cannot remain valid, `S05` stays open and execution stops rather than reporting completion.
- Every retained provenance link to the legacy plan resolves by its unchanged stem through the archive-aware Vault graph, and the scoped dangling-link check passes after archival. Any edge that the `S04` audit classifies as an active authority dependency must be rewired through a separately approved Step before `S05` may close.
- The ledger-Google warning-closeout ADR is superseded, its plan is explicitly historical rather than implementation evidence, its research and index retain the successor link, and exactly four feature documents archive without breaking provenance links. `S11` stays open if its preview exposes an active authority dependency.
- No production source or test file changes relative to the execution baseline.
- `uv run vaultspec-core vault plan check .vault/plan/2026-07-14-google-optional-adapter-boundary-plan.md --json` reports no findings, and plan status reports 14 of 14 Steps complete with no missing execution records.
- Run `uv run vaultspec-core vault check annotations -f google-optional-adapter-boundary --json`, `uv run vaultspec-core vault check placeholders -f google-optional-adapter-boundary --json`, `uv run vaultspec-core vault check body-links -f google-optional-adapter-boundary --json`, `uv run vaultspec-core vault check frontmatter -f google-optional-adapter-boundary --json`, `uv run vaultspec-core vault check links -f google-optional-adapter-boundary --json`, `uv run vaultspec-core vault check dangling -f google-optional-adapter-boundary --json`, and `uv run vaultspec-core vault check schema -f google-optional-adapter-boundary --json`; each reports zero feature-scoped diagnostics. Run `uv run vaultspec-core vault check structure --json` separately as a global check because it has no feature filter, and classify every finding by owner rather than hiding unrelated corpus drift.
- The production-tree baseline records the exact outputs of `git diff --binary --no-ext-diff -- src | git hash-object --stdin`, `git diff --cached --binary --no-ext-diff -- src | git hash-object --stdin`, `git ls-files --others --exclude-standard -- src`, and `git ls-files --others --exclude-standard -- src | git hash-object --stdin-paths`. The final outputs must match those whitespace-sensitive content snapshots byte-for-byte, proving this plan introduced no production source or test change while preserving unrelated concurrent work.
- Technical review confirms the dispositions against current code and tests. Editorial review confirms that the plan and audits are understandable without campaign memory.
