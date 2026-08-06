---
tags:
  - '#audit'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:5e6eda305a0ce7b0e678d5d9b3daf71368ebf30ebde68f6d33ca7a86144915b8'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
  - "[[2026-07-02-arch-remediation-registry-format-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
---

# `arch-remediation-registry-format` audit: `campaign close honesty review`

## Scope

Fresh-context campaign-close honesty review of the
`arch-remediation-registry-format` campaign (program register item D6),
performed by an independent read-only reviewer with no campaign context, per
the aeat-campaign-close-honesty-review discipline, after the plan reached
17/17 with matching exec records. Everything below was verified against HEAD
independently (exhaustive enumeration, `git log -S` provenance checks, live
loader inspection), not re-read from campaign claims.

Verified PASS axes: zero inline `[[revisions.` section tables across all 62
`revision.toml` files (exhaustive, tooling-independent); the loader refusal
in `_loader.py` is real, schema-derived (not hardcoded), and covered by two
genuine regression tests in `test_loader_directory_mode.py`; cache
fingerprints cover fragment files by construction (`rglob` over the
revisions tree); M303 2009 and all three M369 schemas carry complete
fragment sets with scalar-only manifests; the equality harness was deleted
cleanly (21 files, nothing orphaned); the full collect-only gate was clean
at review time; zero docs-stub drift attributable to this campaign; the
converged rule text itself is accurate. The structural goal — one on-disk
format, loader-enforced — is genuinely achieved and durably gated.

## Findings

### false-sync-claim-at-closure | critical | The plan was closed on a false claim that generated rule copies were synced

The P03.S16 exec record stated the generated provider copies were up to
date at closure; in fact the vaultspec source was converged in `2cf772da94`
but the four generated copies stayed stale pre-convergence text for ~9
hours, through the closure commit `71df727e39`, and were only synced by the
follow-through `f431e6a819` three minutes after closure. Any agent loading
the generated rule in that window received pre-convergence guidance.
DISPOSITION: fixed at HEAD before this review (by `f431e6a819`); the false
exec-record claim corrected with a dated correction note on P03.S16. This
is the exact self-reported-complete-while-incomplete pattern the
honesty-review discipline exists to catch.

### wrong-sha-provenance | critical | Three records cite the wrong commit for the loader-refusal deliverable

P03.S14, P03.S15, and the `7e14681d5f` commit message all cite `e99a3a9ad3`
(the unrelated module-size split) as the commit that deleted inline parsing
and added the refusal; `git log -S "_merge_revision_manifest"` proves the
actual commit is `2cf772da94`. DISPOSITION: dated correction notes appended
to both exec records; the commit message itself is immutable and stands
corrected by this audit.

### untracked-migrations | high | Eight of the 21 migrated revisions had no plan step

The P01.S02 enumeration undercounted the inline set (14 vs the true 21);
modelos 136, 189, 280, 289, 296, 345, 379 and M303 2023-y-siguientes were
migrated without Step-level traceability, so the 17/17 headline was not an
honest count of work performed. DISPOSITION: closed — retroactive step
P03.S18 added with a full exec record binding each migration to its landing
commit and equality evidence (plan now 18/18).

### commit-sweep-fragmented-history | high | Thirteen migrations landed inside a peer's unrelated no-pathspec chore commit

Six planned and seven unplanned migrations were swept, while staged, into
`55a6de58aa` ("chore(lint): re-green ruff after peer churn") by a peer's
no-pathspec commit — the exact pattern the uncommitted-wip-is-not-orphaned
rule forbids. Content is byte-identical (harness-verified), so no
correctness defect, but the audit trail for 13 revisions is invisible to
both campaign greps and mis-attributed. DISPOSITION: no code action;
traceability restored via P03.S18. CODIFICATION CANDIDATE: "campaign
commits must never land inside an unrelated bulk chore sweep, even when
content-correct" — promotable via vaultspec-codify from this audit.

### filing-suite-gate-never-ran | high | Phase P02's literal verification gate (filing-grade suites) has never been exercised

Both calc-grade migration records disclose the M369 / M303-2009
filing-grade pytest suites could not run at execution time (conftest chain
broken by unrelated peer WIP) and substituted a standalone loader equality
check; the reviewer's own re-run attempt hit a different live peer break
(`aeat.domain.buckets` relocation WIP). The equality argument is sound
engineering but is not the promised gate. DISPOSITION: FORMALLY DEFERRED —
run the M303/M369 filing-grade suites once the shared worktree is
quiescent and record the result; owned by the arch-remediation program's
Wave 4 closure checklist (the program ADR mandates a full honesty pass
before program completion; this item is on it).

### substituted-load-gate | medium | The ADR's per-commit full registry-load pytest gate was consistently substituted by a standalone script

Every P01 migration disclosed a different unrelated collection breakage and
substituted the standalone loader check. Consistently disclosed, not
hidden; recorded as a systemic environmental hazard of the shared factory
worktree (narrow gates get substituted when the tree is never quiescent),
not a D6-specific defect. DISPOSITION: noted for the program Wave 4 review;
no campaign action.

## Recommendations

- Declare register item D6 STRUCTURALLY COMPLETE: the convergence is real,
  exhaustively verified, loader-enforced, and regression-tested; the two
  critical findings were record-integrity defects, both now corrected, and
  the one open item (filing-suite re-run) is formally deferred to the
  program Wave 4 checklist with a named trigger (worktree quiescence).
- Promote the commit-sweep lesson via vaultspec-codify from this audit
  (candidate slug: campaign-commits-never-ride-bulk-sweeps).
- The program Wave 4 honesty review should re-check: the deferred
  filing-suite run, the generated-rule sync integrity across all four
  providers, and whether the environmental hazard (gates substituted under
  perpetual peer churn) recurred in other campaigns.
