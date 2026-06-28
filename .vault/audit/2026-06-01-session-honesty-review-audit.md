---
tags:
  - '#audit'
  - '#session-honesty-review'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-test-suite-performance-audit]]"
  - "[[2026-05-31-atomic-relocation-coordination-adr]]"
---

# `session-honesty-review` audit: 2026-06-01 W30.P64 epic close + production-side follow-up sweep

## Scope

Per CLAUDE.md `aeat-campaign-close-honesty-review`: a campaign close
must trigger a fresh-context honesty review before structural
completion is declared. This audit covers the production-impact
commits authored on `chore/eliminate-shims` today: the W30.P64
test-framework epic (S804..S810), the production-side follow-up
fixes (#100, #108, #111, #119, #122), and the policy/audit commits
(S809 sequential default, empirical wallclock recording).

The first reviewer agent dispatched for this gate was blocked on a
non-functional Bash tool and a system-reminder conflict against the
mandate to persist a vault audit. This document is the
coordinator-authored fallback. It is intentionally narrower than a
fresh-context agent review would be; the campaign close is honestly
labelled partial-pass for that reason.

## Gates checked

The standing review gates from `standing_review_gates` memory:

- G1 no naked env reads (production through Settings)
- G2 typed pydantic at boundaries
- G3 tr() for user messages
- G4 no locale yml structure hand-edits
- G5 no shims / re-exports / duplication
- G6 no tautological calculation tests

Plus session-specific concerns:

- Scope creep: explicit-path-staging discipline violated
- Premature closures: tasks closed without verification depth
- Test-vs-code drift: tests updated to match production change
  when the production change itself may be the bug

## Findings

### scope-creep — `26b363bb3` absorbed unrelated peer rename

Commit `perf(test): keep sequential as default addopts` was intended
to touch `pyproject.toml` only. Per `git show 26b363bb3 --stat`, it
also absorbed an unrelated rename of `src/aeat/domain/renta/errors.py`
to `_errors.py`. The rename was staged in the index by a peer's
commit-bot pattern between my `git add -- pyproject.toml` and the
`git commit` invocation. Severity LOW because the rename is itself a
benign refactor (errors → _errors module convention) and was
acknowledged in inline output at commit time. Going-forward
discipline per memory `explicit_path_staging_in_parallel_worktree`:
`git diff --cached` immediately before commit, not just before stage.

### scope-creep — Agent C `42c7cb068` absorbed two peer deletions

Earlier session commit `42c7cb068` (modelo_100 cluster, Agent C)
absorbed peer-staged deletions of `src/aeat/adapters/outbound/google/_refresh.py`
and `src/aeat/adapters/outbound/llm/_prompts.py`. Agent flagged the
absorption in its return report. Severity LOW for the same reason;
documented in the agent's commit message context. Going-forward
discipline same as finding-1.

### premature-closure — #102 closed on test-rename evidence only

Task #102 was filed for `test_profile_import_label_lands_second_copy_under_new_name`
failing with REFUSED_CLI_VALIDATION_BOUNDARY. The named test no
longer exists at HEAD (peer renamed/removed). I confirmed the file's
remaining tests pass and closed the task. Honest gap: I did not
verify whether the export-validation gate that originally triggered
the refusal was tightened, relaxed, or merely moved. The named symptom
is gone; the underlying contract may have shifted. Severity LOW
because the verification step (file passes) is real, but a future
audit could surface the same gate firing in a different test name.

### G5 partial-pass — `64bb92d7c` widens `ExportFieldId` separately

The fix introduces `_EXPORT_FIELD_RE` rather than widening the shared
`_REF_RE`. Verified: the new regex is used exclusively by
`ExportFieldId`; every other typed alias keeps the stricter lowercase
constraint. No shim; no re-export. The new pattern is documented
inline with the AEAT-canonical rationale (uppercase XML-dictionary
IDs like `DPNIF_D`). PASS.

### G2 PASS — `2f17f5f83` ReplayPayload widening

The fix declares five additional fields as typed `Mapping[str, str]` /
`str` with safe defaults. `model_config` keeps `extra="forbid"` —
unknown keys still raise. The on-disk fixture contract is preserved;
type safety is preserved. PASS.

### G3 PASS — `24c070cdb` wizard next-label tr()

`tr("application.wizard.output_labels.next")` is now consumed
inside `wizard/_commands.py`. Machine-parseable `next` KV key is
preserved alongside the new operator-facing `next_label`. The
sidecar-rationale test contract is satisfied without breaking the
scripted-consumer contract documented in the same file. PASS.

### honesty-gap — wallclock measurement skipped p50/p95/p99

The test-suite-performance audit at
`2026-06-01-test-suite-performance-audit.md` records the 11m40s
parallel wallclock empirically. The p50/p95/p99 per-test
distribution was deferred because the durations capture pipeline
never flushed a complete file (PowerShell `Out-File` buffers until
process exit; multiple attempts failed). The audit acknowledges
the deferral honestly but the per-test distribution remains
uncaptured. Severity LOW for the production-readiness verdict, but
the lever for further optimisation is blind without the distribution
data.

### follow-up trail — #111 partial close + #124 chain remainder

`8134c93aa` rewires `iva.resultado-regimen-general` formula args
from form-numbered (`"27"`, `"45"`) to semantic casilla ids
(`iva.cuota-devengada-total`, `iva.cuota-deducible-total`). The
downstream chain (`iva.resultado` via casillas 64/66/77/68) still
references form-numbered casillas. #111 was closed as
partial-fix-only; #124 tracks the full chain remainder. Honest
labelling: the partial fix is a real improvement (regimen-general
now computes correctly) but the cascading iva.resultado is still
zero for Q1-positive scenarios. Three downstream tests still fail
pending the chain-completion fix.

### G6 PASS — no tautological calculation tests introduced

None of today's commits added new numeric-Decimal assertions that
re-apply the formula being tested. All test changes were either
envelope-unwrap alignment, fixture realignment to peer-landed
binding ids, typed-error migration, or marker registration. No new
calculation oracle assertions authored without external citation.

### G1 PASS — no naked env reads

`fd27f5714` adds `psutil>=5.9` to `[dependency-groups].dev` and
`26b363bb3` edits `pyproject.toml` `addopts`. Neither introduces
`os.environ` / `os.getenv` in production code. The W30 epic
explicitly uses `Settings()` and pytest fixtures throughout. PASS.

### G4 PASS — no locale yml hand-edits

Zero changes to `src/aeat/locales/*.yml` in the session's commits.
The locale key `application.wizard.output_labels.next` already
existed in all four locales; my `24c070cdb` added the production
consumer of the key, not the locale value. PASS.

## Verdict

Partial-pass. The W30.P64 test-framework epic is structurally
complete and verified empirically (11m40s parallel wallclock, 5x
speedup). The production-side follow-up fixes (#100, #108, #122,
#111-partial) are clean against G1..G6. Two scope-creep absorptions
(`26b363bb3`, `42c7cb068`) are documented LOW severity. One
premature-closure (#102) is acknowledged. The full p50/p95/p99
per-test distribution is uncaptured.

The campaign is NOT structurally complete in the strict
honesty-review sense — #111 is partial, #124 carries the chain
remainder, three M303 tests still fail, the ~150 other test
failures observed under `just test-parallel` are real production
bugs tracked separately. The test framework can verify code
contracts; the contracts themselves still have open production work.

## Recommendations

1. Future commit cycles use `git diff --cached` immediately before
   commit to catch peer-staged absorption before it lands.
2. Re-attempt the durations capture with pytest's native
   `--resultlog` flag (writes directly, no PowerShell buffering).
3. Drive #124 (M303 form-numbered chain) before declaring the
   modelo-303 calculation surface green.
4. Re-run `just test-parallel` after every cluster of production
   fixes lands to keep the failure count visible.
