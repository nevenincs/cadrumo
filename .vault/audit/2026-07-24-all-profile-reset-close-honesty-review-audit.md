---
tags:
  - '#audit'
  - '#all-profile-reset'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:9dc608c3034a82cd5a4b2e34129e1af8e27786eee1dd307048a2ccf81052fa78'
related:
  - '[[2026-07-17-all-profile-reset-plan]]'
  - '[[2026-07-17-all-profile-reset-adr]]'
  - '[[2026-07-17-all-profile-reset-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
---

# `all-profile-reset` audit: `all-profile-reset campaign close honesty review`

## Scope

Fresh-context honesty review of the `all-profile-reset` plan, which reports 31 of 31 steps complete. This reviewer carried no prior context in the campaign, per the review's own gate: the requirement is a reviewer who did not drive execution.

A prior audit under this same feature tag already carries a section titled "Campaign-close honesty review (2026-07-19, fresh-context)" appended to the original P01-P03 safety-closure document, declaring the plan structurally complete at 31/31 five days before this review. That section is treated here as one more claim under review, not as a substitute for this gate: it was authored inside the same document as the safety-closure record it reviews rather than as an independent artefact, and five days of peer landings in this shared worktree separate it from today.

Every plan step's exec record was read in full. The application-layer and CLI-layer test suites the plan's Verification section names were re-run live against HEAD rather than trusted from exec-record prose: `test_config_reset.py`, `test_config_reset_repository.py`, `test_config_reset_recovery.py` (real crash-resume, fresh child processes), `test_config_reset_concurrency.py` (real contending processes), `test_config_reset_lifecycle.py`, `test_config_profile_sandbox.py`, `test_destructive_verbs_require_yes.py`, `test_root_grammar_invariants.py`, `test_service_retention_floor.py`, `test_service_delete.py`, `test_config_custody_profile_lifecycle.py` (the one step's carried-forward evidence file), and the MCP `test_identity_gate.py`. 146 of 147 tests re-run passed; the one failure is Finding 1. The reset orchestration (`config_reset.py`), the bucket-maintenance deletion/retention path (`_service.py`), and the CLI door (`_reset_cli.py`) were read in full and cross-checked line-by-line against the exec records' specific claims (phase ordering, sorted-lock scope, retention-decision persistence-before-mutation, deletion-marker-before-erase, pointer-clear-before-delete, active-bucket-delete refusal backstop). Every commit hash cited across the 30 exec records was confirmed to exist in history. No mock, monkeypatch, skip, or xfail was found in any test file this campaign's steps name.

No environment-blocked gate was found for this campaign: none of its own test files touch OS keychain/credential-store paths (the certificate-secret erasure in P03.S11 goes through secure storage, not the OS keychain), so the Windows credential-store breakage noted for this host did not obscure any of this campaign's own verification surface.

## Findings

### p04-s23-carried-evidence-file-now-red | high | The carried-forward evidence file for P04.S23 has a test failing at HEAD, from a same-day peer commit retiring the mechanism it tests

`P04.S23` ("Prove switching and strong logout through real persisted custody state") is the one step the plan explicitly carries forward from the originating `cli-authority-verb-conformance` campaign stem rather than re-executing (exec record `cli-authority-verb-conformance-W04-P11-S103`, cross-referenced by the rescope audit's `carried-exec-evidence` finding). Its evidence file is `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`. Re-run today, `test_profile_selection_precedence_uses_explicit_env_then_pointer` fails, reproducibly, both under the project's normal parallel run and in isolation (`-n 0`): an explicit `CADRUMO_ACTIVE_PROFILE` environment override no longer takes precedence over the on-disk pointer default. `git log` on `src/cadrumo/core/config.py` shows why: commit `65ad0ea12a` ("feat(profile): land the login-session campaign corpus and root session resume") landed today and deliberately retired `CADRUMO_ACTIVE_PROFILE` as an environment-selection mechanism — the module's own docstring now states selection has exactly two writers (the pointer file and the in-process `--profile` override channel), naming the env var as a development-era override that is gone. The test asserts exactly the old, now-superseded precedence.

This is peer churn from an actively-landing sibling campaign (login-session), not an authorship defect of `all-profile-reset`: `config_reset.py`, the reset journal models, the reset repository, and `_reset_cli.py` were grepped for `CADRUMO_ACTIVE_PROFILE` and none reference it, so the reset orchestration itself does not depend on the retired mechanism. The other five tests in the same file — including the core claim this step names, that `config profile logout` performs the sole strong local-session logout before switch — still pass. The finding is narrower than the step's core claim, but it is real: the plan's stated instruction not to re-execute this step because its evidence "carries execution evidence under the originating campaign feature stem" no longer holds unconditionally as of today's peer landing, and nobody has re-confirmed the file since. Left unaddressed, a later reader trusting the exec record's "do not re-execute" note would not discover the drift.

### plan-description-overstates-carried-forward-count | low | The plan's own Description claims four carried-forward steps; only one genuinely lacks a local exec record

The plan's Description section states: "Four steps below are already landed and carry execution evidence under the originating campaign feature stem, which the rescope record documents. Do not re-execute them." Cross-checking the 31-step plan against the exec folder shows only `P04.S23` genuinely has no local exec record (its evidence lives solely under the originating `cli-authority-verb-conformance` stem, per Finding 1 above and the rescope audit). Three P03 steps (`S15`, `S16`, `S17`) were briefly in the same "checked with no local exec record" state — their own exec records say so explicitly ("Already checked in the plan without an execution record when I inherited P03") — but were retroactively grounded with fresh local exec records rather than left carried-forward, closing the gap the Description still describes. The Description text was written on 2026-07-17 and was never updated once the gap it names narrowed from four steps to one. This is a documentation-staleness nit, not a completeness violation — the real local exec-record coverage (30 of 31) exceeds what the Description claims — but a reader taking the Description at face value would search for three carried-forward steps that no longer exist as such.

### plan-frontmatter-omits-own-decision-records | low | The plan does not relate to its own ADR or its own P01-P03 safety audit

The plan's `related:` frontmatter lists six documents, all belonging to the originating `cli-authority-verb-conformance` campaign; it never lists `2026-07-17-all-profile-reset-adr` or `2026-07-17-all-profile-reset-audit`, even though both of those documents' own `related:` fields point at the plan. The graph edge exists in one direction only. This is the same pattern flagged as a low finding in the sibling `duplication-evidence-repair` close-honesty review five days prior, recurring here independently.

### embedded-close-review-is-not-an-independent-artefact | low | The 2026-07-19 close-honesty pass lives as a section inside the P01-P03 safety audit rather than its own document

`aeat-campaign-close-honesty-review` names three sanctioned mechanisms for the gate; an independent audit document is the pattern every other successor plan in this rescope family used (see the `duplication-evidence-repair` and `cli-authority-quality-backlog` close-review audits, each its own dated file). This campaign's 2026-07-19 pass was instead appended as a subsection of the pre-existing `2026-07-17-all-profile-reset-audit` — the P01-P03 safety-closure record — conflating a scope-limited technical audit with a whole-plan closure gate in one document. This is a process-hygiene nit, not a substantive gap; it did not stop this review from being commissioned, but a future reader scanning the vault index for a close-honesty-review-tagged document for this feature would not find one until this record.

## Recommendations

Re-run `test_config_custody_profile_lifecycle.py` after the login-session campaign's active-profile-selection cutover finishes landing, and either update `test_profile_selection_precedence_uses_explicit_env_then_pointer` to match the new two-writer selection model or delete it if the login-session campaign's own closure already retires it elsewhere; either way, someone must own closing this specific test, because neither campaign's plan currently names it as their responsibility. Until it is green again, treat `P04.S23`'s "do not re-execute, already landed" instruction as conditional rather than absolute.

Update the plan's Description section to state the true carried-forward count (one step, `P04.S23`) rather than the stale count of four, so a future reader reconciling the Description against the exec folder is not sent looking for evidence that no longer needs to exist.

Add `all-profile-reset-adr` and `all-profile-reset-audit` to the plan's `related:` frontmatter so the decision-record graph is bidirectional, matching the correction already recommended for the sibling `duplication-evidence-repair` plan.

No further action is required on the safety-critical orchestration itself: the crash-resume, concurrency, retention-floor, fingerprint-guarded deletion, and grammar-invariant claims were independently re-run against real processes and real encrypted storage today and hold exactly as the exec records describe, with the sorted-lock, retention-before-mutation, deletion-marker-before-erase, and pointer-clear-before-delete ordering confirmed by direct code reading rather than by trusting prose.
