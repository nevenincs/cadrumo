---
tags:
  - '#audit'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
  - "[[2026-07-17-auth-cert-recovery-custody-adr]]"
  - "[[2026-07-17-auth-cert-recovery-custody-audit]]"
---

# `auth-cert-recovery-custody` audit: `close honesty review`

## Scope

Fresh-context honesty review of the `auth-cert-recovery-custody` plan, which reports 44 of 44 steps complete across eight phases. The reviewer carried no prior context in this campaign. The existing `2026-07-17-auth-cert-recovery-custody-audit` is a mid-campaign safety review scoped only to the certificate-secret CLI door (`P05`/`P07`), not a close review; this record is the mandated close-honesty gate the campaign has not previously run.

Every one of the 44 steps was checked against the tree at HEAD (`76cc1a082b`). The 21 backend steps (`P01`-`P03`) carry no execution record under this feature's own stem by design — the plan states they were landed under, and their exec records live under, the originating `cli-authority-verb-conformance` campaign stem; all 21 of those records were confirmed present there (`W02.P06.S37/S43-S46`, `W02.P07.S47-S52`, `W02.P21.S71-S80`) and their `[x]` state matches the parent (superseded) plan. The 23 CLI-door, contract-migration, and DI-seam steps (`P04`-`P08`, `S22`-`S44`) each carry an execution record under this feature's own stem, as the plan-closure discipline requires.

Gates were re-run rather than trusted: `test_override_seam_singularity.py` (10 passed), `test_root_grammar_invariants.py` (17 passed, `-m integration`), the full `application/auth/tests` suite (176 passed), the full recovery/custody-matrix suite (60 passed), `test_certificate.py` (16 passed, `-n0`), the locale `audit` command (`ok` on all four catalogues), and targeted greps confirmed the `SECURE_STORAGE_BACKEND_LABEL` deletion, the single certificate-secret writer, the absence of a certificate-keyring class, the absence of an `--secret` argv option on `certificate secret set`, and the absence of any `submit`/`presentar` method on the certificate authenticator. Every cited commit SHA (`009ed60006`, `7305fd3ae2`, `c4a8166ab4`, `c3c7532282`) was confirmed to exist and to match its exec record's description.

## Findings

### p04-door-never-independently-reviewed | high | The passphrase/recovery CLI door — the campaign's highest-sensitivity surface — never received its own safety or code review

`P05`/`P07` (the certificate-secret CLI door) received a dedicated, independent, fresh-context safety review (`2026-07-17-auth-cert-recovery-custody-audit.md`, verdict PASS, one Low finding since closed by `P08.S44`). `P04` (the passphrase and recovery CLI door — `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`) received no equivalent review, despite being the more sensitive surface of the two: it displays a 24-word BIP-39 recovery mnemonic once, writes it directly to the controlling terminal device (bypassing stdout), and requires a full no-echo retype before committing an enrollment or rotation. Grepping every audit and commit message for a code-review pass over `_custody_secret.py` or `_secure_input.py` in the relevant window returns nothing.

The originating master plan (`2026-07-15-cli-authority-verb-conformance-plan.md`) explicitly named this gap as `W06.P18.S179` ("Run auth and certificate suites") and `W06.P20.S209` ("Invoke vaultspec-code-review over the complete feature diff for safety, intent, boundary direction, and test quality") — both still unchecked in that superseded plan, and neither was re-created as a step in this successor plan when the rescope carved it out. The successor's own `Verification` section restates the intent in prose ("Passphrases, mnemonics, and secret-input values are absent from help and examples") but that is a narrower claim than a safety review: it does not audit the terminal-write bypass, the retype-verification logic, or the crash/cancel-leaves-prior-envelope-intact guarantee for adversarial or malformed input the way the certificate-door review did for its surface. This review's own re-verification (re-reading `write_to_controlling_terminal` and the recovery-envelope preservation logic in `_recovery.py`) found the code sound, but that is exactly the kind of confirmation a dedicated review, not a general-purpose close audit, should have produced and recorded before the campaign closed.

### s41-record-backdated-past-the-actual-gap | medium | The one execution-record gap in this plan was filled the same day this review was requested, and its frontmatter date obscures that

`P07.S41`'s execution record states in its own Notes section that it "was authored on 2026-07-24, after the work landed" and that it "was the sole execution-record gap in this plan." `git log --follow` on the file confirms it: the record was committed today (`78600dcd`, 2026-07-24), the same day this close-honesty review was requested. Until that commit, the plan's "44 of 44 complete" claim was false under `plan-closure-requires-exec-records` — a checked step (`P07.S41`, checked since the plan's `2026-07-19` `modified:` stamp) carried no execution record for five days.

The record's frontmatter nonetheless carries `date: '2026-07-17'` and `modified: '2026-07-17'`, both a week earlier than the real authoring date its own prose discloses. The scaffolding CLI accepts a `--date` override, and this is very likely how the mismatch arose (backdating the frontmatter to align with the sibling records' dates rather than the real authoring date). The prose is honest about the gap; the frontmatter is not, and a reviewer who trusts dates over prose — the normal way to scan a vault for staleness — would miss that this campaign's completeness claim was inaccurate until today. `modified:` is documented project-wide as "never hand-edited" and CLI-maintained; passing `--date` to backdate a gap-filling record achieves the same effect as a hand-edit would.

### wave6-verification-steps-never-re-created | low | Several parent-plan closure steps for this cluster were retired without an explicit successor, though their functional intent is independently satisfiable

The parent plan's `W06.P18.S178` ("Run passphrase and recovery lifecycle suites... against real encrypted vaults") and `W06.P18.S179` ("Run auth and certificate suites against real storage and provider boundaries") remain unchecked in the superseded plan and were never given an explicit successor step in this plan's own list. Functionally the intent is covered — this review independently re-ran the equivalent suites and they pass — but no step in this plan's own `Steps` list names "run the combined family suite" as its completion condition; the closest analogues (`P04.S27`-`S31`, `P05.S32`-`S34`) each prove one narrower slice. This is a closure-bookkeeping gap, not a functional one, and is listed only because the same pattern (a Wave-6 aggregate verification/review step retired without a named successor) is the root cause of the `high` finding above.

### stale-test-counts-in-two-exec-records | low | Two exec records cite point-in-time test counts that no longer match the tree, though the underlying gates are still green

`P06.S38` cites "MCP suite green (301 tests)"; the current tree collects 278 under the same invocation (`-m ""`). `P06.S35` cites "the full `application/auth/tests` suite (172 passed)"; the current tree runs 176. Both drifted upward in test count between 2026-07-19 and today, consistent with unrelated peer-campaign test additions rather than a regression — this review re-ran both suites directly and confirmed the auth/certificate/recovery-family-relevant subset is green in both cases (the MCP suite's one observed failure, `config.login`/`config.logout`/`config.profile.censo.file` missing risk rows, and the operator-surface-contract-drift failure for the same three families, both trace to the concurrently in-flight `login-session` campaign, not this one). The citations were accurate when written; they are a minor, low-cost source of confusion for a future reader who re-runs the gate expecting an exact match.

## Recommendations

Dispatch an independent safety review of the `P04` passphrase/recovery CLI door, scoped and structured the way the existing `P05`/`P07` certificate-door review was: verify the terminal-write bypass cannot be redirected, the retype-verification rejects a mismatched candidate without touching the prior envelope, non-interactive `create`/`rotate` refuse before any custody read, and `--secrets-stdin` rejects malformed or oversized payloads cleanly. Persist the verdict as its own audit document under this feature's stem before treating the campaign as closed on the safety axis.

When a rescope splits a plan, carry forward or explicitly retire each of the parent's Wave-6 verification and review steps (`W06.P18`/`W06.P19`/`W06.P20` in the parent plan) into a named step in the successor, rather than letting them lapse silently into "covered by the Verification section's prose." A named step with its own execution record is the difference between an intent statement and a completion condition.

Prefer the real authoring date over a `--date` override when scaffolding a gap-filling execution record after the fact; where a backdated date is deliberately used to align with a sibling batch, say so explicitly in the record's own Notes (as `P07.S41`'s prose does) and leave `modified:` at the real date so a date-based scan surfaces the actual gap window.

Given the `high` finding above, `auth-cert-recovery-custody` is not yet structurally complete on the safety-review axis: the CLI-door and contract-migration work is real, tested with real behavior throughout (no mocks, stubs, skips, or xfails found across the nine touched proof files), and independently reproduced by this review, but the safety review coverage this campaign's own certificate-door precedent set is asymmetric across its two custody families. Close the `high` finding — or formally defer it to a named follow-up — before declaring the plan complete.
