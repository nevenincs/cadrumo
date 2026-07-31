---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:7760dd160760b0f9ff327a259e90b0fdda45a13d472f7b48de222e9407d2fc2a'
step_id: 'S261'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# Prove real zero-clone, clone, unavailable executable, non-zero, timeout, stderr, and unparseable outcomes cannot become false green and that report and direct runner render the same typed result

## Scope

- `src/cadrumo/tests/test_dev_audit_report.py`

## Description

- Establish that this step duplicates a step already closed under a rescoped successor plan.
- Enumerate the seven outcomes the step names and locate the real exercised case for each, rejecting any that is a faked return value.
- Measure the non-zero-exit reason to see what the diagnostic actually carries.
- Add the missing discriminating assertion on the diagnostic evidence and prove it by reintroducing the loss.
- Correct the step's own scope citation, which names a module that does not hold its proofs.

## Outcome

Satisfied, with one real gap found and closed at commit 090fdc64cf.

This step's action text is word-for-word identical to the sixth step of the duplication-evidence-repair successor plan, which is closed. Six of the seven outcomes it names were already proven by real exercised cases, and the proofs are unusually good: failure conditions are forced rather than faked. A genuine non-zero exit is obtained by pointing the injected resolver at a real Python interpreter that rejects the scanner arguments. A real millisecond timeout is applied to a real subprocess. The missing-executable path comes from a resolver returning nothing, which is a real contract rather than a patch of global state. The green assertion is earned from a real scan over a genuinely clone-free subtree, guarded by a lower bound on files analysed so a partial scan cannot pass as a full one. The unparseable case is parametrized over four shapes, and it deliberately includes a clone total with no summary table, on the correct reasoning that a total alone does not prove any file was read.

The seventh outcome, stderr, had a real exercised case but a NON-DISCRIMINATING assertion, which is this campaign's defect class exactly. The runner builds the unavailable reason from the failed process's stderr, falling back to stdout and then to a fixed no-diagnostic-output sentinel. The gate asserted only that the reason said the process exited. That assertion cannot tell a captured diagnostic from a vanished one: with the stderr capture dropped the reason still reads that the process exited with a code, the amber verdict stays correct, and the gate stays green while the evidence explaining the verdict is gone.

Measured, not argued. The real reason carries the interpreter's own usage error. With stderr dropped from the diagnostic the run splits one failed and one passed: the pre-existing assertion still passes, which is the proof it was not discriminating, and the new one fails naming the loss. The production line was then restored and confirmed byte-identical to the commit.

The new assertion is structural rather than textual. The tail is a real interpreter's own error text and varies by version and locale, so it asserts a non-empty tail that is not the fallback sentinel, never the literal message.

One correction to the step itself. It scopes its proofs to the health-report test module, which carries only the end-to-end dimension check. The unavailable, non-zero, timeout, unparseable, bad-path, missing-scanner, and single-owner proofs all live in the runner's own two test modules, which the step never names. The work exceeds the step's text; only the citation misleads an auditor reading the plan alone. Recorded here rather than by editing the step row.

On the step's final clause, that the report and the direct runner render the same typed result: this holds structurally rather than by assertion, and structurally is stronger. The report does not render a parallel result to compare, it delegates to the one runner, and the tree-wide single-owner gate pins that there is only one.

## Notes

Semantic CODE search was degraded and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, an available status, and an empty degraded-reasons list. Discovery was by direct reads of the two runner test modules and the runner itself, plus a measurement script run against the real subprocess.

A verification trap worth recording: the live-scan test module is integration-marked, so a bare pytest invocation against it selects nothing and exits green. Every run here carried an explicit marker expression and a confirmed non-zero collected count. The gate that catches the defect class is itself reachable only past a selection defect of the same family.

The discrimination proof required briefly reintroducing the defect in the production runner. The line was restored immediately and confirmed byte-identical to the commit before anything was staged.

CORRECTION to this record's own verification, added after the fact rather than smoothed over.

The verification behind this step ran the duplication module's unit half, 22 passed, plus targeted selections against the non-zero-exit and diagnostic cases. It did NOT run the full live-scan suite. A later independent re-run at commit 003a2f987d did, and found the disposition-coverage gate RED: the live scan observes clone groups in the TUI form-screen module that carry no recorded disposition, failing with 1 failed and 45 passed.

Attributed before being reported. The form-screen module did not change during this session and carries no working-tree WIP, so the condition predates this work and is not caused by it; the clone groups are peer-owned TUI code. The gate itself is behaving correctly, since detecting exactly this drift is its purpose.

The finding does not overturn this step's conclusion, because the false-green defect and the outcome classification are separate properties from the disposition record's freshness, and both were verified directly. It does qualify the CLAIM: the duplication authority is sound, and one of its gates is red on stale reference data. Those are different facts and were reported as such.

The deeper lesson is the one this campaign is about. A gate that is only ever run through a marker-scoped or -k-narrowed selection is a gate whose result you have not actually seen. The live-scan module is integration-marked, so every convenient way of running it during this step silently excluded the one test that was failing. Verifying a gate authority without running its slowest half is the same substitution the audit names: checking the description rather than the artifact.
