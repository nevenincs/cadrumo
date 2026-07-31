---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:0e3ac11e354d30e38d8b5ffd4b03b4aaa6f31124b9c8da863fbd57bace1e3f4d'
step_id: 'S29'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures

## Scope

- `docs/`

## Description

- Regenerate apidocs stubs in the retirement commit (two stale stubs removed, wizard and tui toctrees refreshed); `scaffold --check` clean.
- Run the documented-command and JSON-schema conformance gates: green (independently re-verified at pushed HEAD, 501 passed at integration scope).
- Run the full docs build gate (`dev/docs/tests/test_docs_build.py`) with complete on-disk log capture: 8 failed, 15 passed.
- Re-run the full docs build gate after the peer landed and after the gate's own timeout defect was fixed: **22 passed, 0 failed, pytest exit 0** in 3095 s (51 m 35 s), measured at sha `10460785dc`.

## Outcome

Every substrate-owned docs surface is green: the apidocs tree matches the module tree, no orphan stubs, conformance gates pass, and the wizard/flows/tui reference pages build. The docs build gate itself is now green end to end (22 passed, exit 0) — the peer-owned error-registry row landed, and the gate's own inability to reach a verdict was fixed (see Notes). No failing surface remains.

## Notes

- Owner triage: all 8 docs-build failures reduce to ONE signature — `CadrumoError subclass cadrumo.application.auth._apoderado.ApoderadoRepresentedNifInvalidError is missing a declared ErrorCode registry entry`, raised by the `cli-sequence` directive on every build variant (nitpicky, user-scope, es/ca/hu localized, site-identity, sequence-widget). The class exists only in a peer campaign's uncommitted working-tree edits to the auth/apoderado files; the registry row lands with their commit. The gate's own message anticipates exactly this concurrent-process state.
- The peer's error-registry row landed, clearing all 8 failures of that single signature.
- Closing the step also required fixing the gate's own inability to report a verdict, which was masking the result rather than any docs defect. Three causes, all in `dev/docs/tests/test_docs_build.py`: the project-wide 300 s pytest ceiling killed the module long before a full Sphinx build could finish (now `timeout(1800)` at module scope); nine `subprocess.run` calls had no timeout at all, so a wedged child could hang the gate indefinitely (now a 1200 s ceiling on each); and three hardcoded `-j auto` sites oversubscribed a machine already running a 17-agent fleet (now routed through `_gate_build_jobs()`, honouring `CADRUMO_DOCS_JOBS`, default 4).
- Verdict sequence: 665 s green, then 801 s green on the targeted gate, then the full module at 3095 s / 22 passed / exit 0. The earlier 8-failed reading was a true report of a peer's transient state; the inability to finish at all was the gate's own defect.
