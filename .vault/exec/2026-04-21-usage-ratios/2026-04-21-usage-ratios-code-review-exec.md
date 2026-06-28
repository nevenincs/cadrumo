---
tags:
  - "#exec"
  - "#usage-ratios"
date: 2026-04-21
modified: '2026-04-21'
related:
  - "[[2026-04-21-usage-ratios-adr]]"
  - "[[2026-04-21-usage-ratios-plan]]"
  - "[[2026-04-21-usage-ratios-phase1-summary-exec]]"
---

# 2026-04-21-usage-ratios-code-review

## Overview

Mandatory Phase-5 Verify artefact for #259. Six commits on `feature/259-usage-ratios` (`f0f781d` → `231424f`) were reviewed across four rolling audit rounds (19 discrete audits spanning 20 distinct domains), plus a final sweep. PR #306 is ready for merge once Windows CI is confirmed green.

## Verdict

**Approved.** Zero critical or high-severity findings reached the merge tip. Every must-fix surfaced during audits was addressed in the subsequent hardening commit. One follow-up issue was carved out ([#310](https://github.com/wgergely/aeat/issues/310) — concurrent-writer data loss) with ADR acknowledgement and a clear deferral rationale.

## Rounds executed

| Round | Domains | Outcomes |
|---|---|---|
| 1 | security, trilingual/UX, pydantic deep, test quality, concurrency + platform | 1 hardening commit (`9b51c78`). Dropped unreachable `is_finite` branch, added canonical key ordering, strengthened tautological tests. Zero critical. |
| 2 | architecture, failure-mode UX, vault consistency, downstream contract, performance | 1 hardening commit (`437dab7`). Moved `FAMILY_ALIASES` to CLI-private (two audits converged), dropped `phone_fixed_business` (alias overlap), surfaced pydantic / OSError detail, extended unknown-key hint with `difflib`. Zero critical. |
| 3 | Round-2 regression, CLI composition stress, data-file evolution, shadow/duplication, error-message quality | 2 hardening commits (`dce6eed` + `6354eea`). Fixed stale `--help` regression (real Kent-observable bug), added UTF-8 BOM tolerance, replaced pydantic's 38-entry enum dump with focused 12-category list, `_indented_wrap` for 80-col-safe output, trailing-whitespace tolerance. One follow-up filed (#310). |
| 4 | Round-3 regression, test-suite blindspots, i18n actual coverage, git + filesystem | 1 hardening commit (`231424f`). Closed six test blindspots (atomicity, CLI silent-swallow, zero-format exact match, `Value error,` prefix stripping, difflib cutoff, payload indent, UTF-8 bytes). Persistence now writes trailing LF. ADR text drift corrected. |
| 5 | vaultspec completeness, PR finalization, Round-4 regression | No new code commits. Created this code-review record and the phase-1 summary; amended ADR with R3+R4 entries; updated PR body, labels, and milestone. Round-4 regression audit returned `clean`. |

## What went well

- **Four parallel audits per round, mixing reviewer personas** (`vaultspec-code-reviewer` and `general-purpose`). Convergent findings (e.g. both architecture and downstream audits flagging `FAMILY_ALIASES` library-level placement) carried more weight than any single audit.
- **Concrete Kent-observable tests** for every user-visible bug that surfaced. The stale `--help` alias bug (found in Round 3 regression audit) was a real merge-blocker that no single-round review would have caught; the rolling cadence did.
- **Follow-up tracking discipline.** The concurrent-writer data-loss finding was carved out to #310 with a crisp reproducer and a rationale for why it isn't a #259 regression. The ADR's Out-of-scope section points to the tracker.
- **Vault integrity.** Every wiki-link resolves; tag taxonomy is compliant; `status` fields were rolled forward at each phase boundary.

## What to watch in follow-ups

- **#310 (concurrent writers).** Must land before #214 (setup wizard) if the wizard ever sets multiple ratios from parallel prompts. The existing `os.replace` atomicity protects against torn writes but not against whole-key loss under read-modify-write races.
- **Pattern drift (Round-4 regression audit).** `save_usage_ratios` now forces `newline="\n"` and appends a trailing `\n`, but peer services (`invoices/`, `transactions/`, `attachments/`) do not. Either backport in a tidy-up PR or accept the divergence. Neither is a #259 regression; both are follow-up candidates.
- **Dead-branch guard.** `_indented_wrap`'s `if not items:` branch is defensive code with no regression-prevention test (because `FAMILY_ALIASES` and `ELIGIBLE_USAGE_RATIO_CATEGORIES` are never empty at any call site today). Consider adding a direct unit test on the helper or deleting the guard.
- **i18n wiring.** `AEAT_OUTPUT_LANGUAGE` has zero readers in `src/aeat/`; the entire CLI layer is English-only. A dedicated EPIC is the right scope; wiring it in #259 alone would fork the CLI layer.

## Artefact integrity

- [x] Research, ADR, Plan, Phase-1 summary, this code review — all present under `.vault/`.
- [x] ADR `status: implemented`; Plan `status: completed`; tag taxonomy compliant.
- [x] ADR's `## Post-approval amendments` covers Rounds 1 through 4.
- [x] `feature 'usage-ratios'` has its feature index (`.vault/feature-usage-ratios.index.md`) after running `uv run vaultspec-core vault feature index -f usage-ratios`.

## Final recommendation

Merge PR #306 via **"Create a merge commit"** once `windows-latest / Python 3.13` completes green. Keep the six-commit history (do NOT squash) so release-please can categorise the hardening rounds under `test:` / `refactor:` / `fix:` for the changelog.
