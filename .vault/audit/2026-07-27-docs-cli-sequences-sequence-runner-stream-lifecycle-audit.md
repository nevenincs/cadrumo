---
tags:
  - '#audit'
  - '#docs-cli-sequences'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:3fc75cfac51453c79028784bbeca03f1b53cf0a4d5fa5a964445504d3ca331f3'
related:
  - '[[2026-07-13-docs-cli-sequences-adr]]'
---

# `docs-cli-sequences` audit: `sequence runner stream lifecycle`

## Scope

An intermittent red observed in the cli-sequence golden gate during the
2026-07-27 docs-build speed campaign, recorded here so it survives as a tracked
defect with its evidence. The speed campaign deliberately did NOT fix it: it is
a separate defect with a separate owner, and folding a runner-lifecycle fix
into a performance change would have made the campaign's before/after
unattributable. Audited surface: the sequence engine's in-process frame
execution (`dev/docs/sequences/_runner.py`, `cadrumo.tests.cli_runner`) and the
application's logging configuration as exercised by an unscoped
`python -m dev.docs.sequences check`.

## Findings

### sequence-runner-stream-lifecycle | high | a stdlib logging-error dump leaks into a frame's captured stderr, intermittently reddening the golden gate

Observed 2026-07-27, worktree at commit `251c06166e`, machine under ~100 per
cent load: an unscoped serial golden check (one child interpreter, every
enrolled sequence) exited red with 2 divergences whose diff content is not a
semantic output change but a Python `--- Logging error ---` fallback dump in a
frame's captured stderr. The dump quotes the debug call at
`src/cadrumo/adapters/persistence/profile/transactions.py:339`
(`_log.debug("loaded transaction catalogue bucket_id=%s entries=%d", ...)`)
followed by the stdlib's `Message:` and `Arguments:` lines. That output shape
is produced by `logging.Handler.handleError` when the handler's stream WRITE
raises — not by the logged call site. `transactions.py` is clean at that
commit and the call is ordinary lazy logging; the call site is not the defect.

Reading of the mechanism (consistent with all observed evidence, not yet
proven by a targeted repro): the engine invokes the CLI in-process
(`invoke_cached_cli`), and a logging handler configured during one invocation
can stay bound to that invocation's captured stderr stream; once the capture
closes, a later debug write through the stale handler raises inside the
handler, and logging's error handler dumps the record and traceback to the
CURRENT `sys.stderr` — a later frame's capture. The transcript then diverges
from the committed golden on stderr content that no CLI behaviour produced.

The flake was masked until now: the gate had been reddening on real semantic
divergences (the deductible-VAT-evidence blocking rule, fixed separately on
2026-07-26/27), and the full check was expensive enough that nobody re-ran it
to see a second, non-semantic cause behind the first. A gate that reds at
random teaches operators to re-run rather than read; this is worse than a slow
gate and worth fixing on its own priority.

### sharding-lowers-repro-rate | medium | the new page-sharded check makes this flake harder to reproduce, not fixed

The golden check is now page-sharded across bounded child interpreters
(commit `6074a646a1`): fewer sequences execute per process, so a stale-handler
write has fewer later frames to leak into, and the reproduction rate per run
drops. A green from the sharded fast path therefore does NOT establish the
flake is gone. Reproduction attempts must use the serial path
(`check_sequences_in_subprocess(jobs=1)` or the bare
`python -m dev.docs.sequences check`) or a long single-process run, and any
future claim that this defect is fixed needs a serial-path soak, not a
sharded green.

## Recommendations

- Root-cause and fix the handler/stream lifecycle: inspect where the
  application installs stream handlers during CLI invocation and what
  `cadrumo.tests.cli_runner.invoke_cached_cli` does with the capture streams
  across invocations; the fix is either per-invocation handler teardown or
  handlers that resolve `sys.stderr` at write time rather than capturing the
  stream object.
- Add a regression proof at the runner tier: after a fix, a test that runs
  many frames through one process with capture streams closing between
  invocations and asserts no logging-error text ever reaches a later frame's
  stderr.
- Verify the fix on the SERIAL check path (see the sharding finding above);
  a sharded green is not evidence here.
