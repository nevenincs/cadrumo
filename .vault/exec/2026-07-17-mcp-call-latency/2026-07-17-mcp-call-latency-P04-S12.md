---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Route both the direct per-verb call and the meta-execute call through the warm in-process runtime while keeping the shared off-loop progress wrapper and the per-tier timeout ceilings and ## Scope

- `src/cadrumo/entrypoints/mcp/_server.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route both the direct per-verb call and the meta-execute call through the warm in-process runtime while keeping the shared off-loop progress wrapper and the per-tier timeout ceilings

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`

## Description

- Add `_run_tool`: dispatch a verb through the transport its call tier selects - warm in-process for READ and MUTATE, supervised subprocess for the AEAT-sede open-world (LIVE) family - and route both the direct per-verb path and the meta-execute path through it, so both share one transport decision.
- Add `_run_inprocess_tool`: serve a verb through the warm runtime under a wall-clock ceiling; because an in-process call cannot be process-tree-killed, run it in a dedicated worker thread joined with the per-tier timeout and return the same localized timed-out refusal on breach while the abandoned worker finishes in the background.
- Refactor `_run_subprocess_tool` to parse its completed run through the shared `parse_cli_envelope`, so the subprocess and in-process transports produce byte-identical envelopes from one parser.
- Keep the shared off-loop progress wrapper for both paths, so the event loop stays free while either transport runs.
- Leave the bulk-resource resolver on the supervised subprocess (out of this Step's stated scope).
- Repoint the loop-responsiveness gap probes to an open-world (subprocess) verb: local reads now serve warm in-process sub-second, too fast to overlap the mid-call probe, so the slow-call proof moves to the transport that stays subprocess.

## Outcome

Both the direct and meta-execute paths serve local verbs warm in-process. Measured against an isolated state root: the first in-process call pays the cold registry load once (1.3 s), and warm calls run at a ~53 ms median - decisively under the sub-second bar, against roughly 5 s for the same verb via the subprocess transport. The two loop-responsiveness tests pass (13 s, two 5 s subprocess probes), proving both dispatch paths still run off the event loop. The full `src/cadrumo/entrypoints/mcp` suite is 255 passed with the two `test_risk_table_parity` failures triaged as pre-existing peer churn (a stale `config.reset` risk row, last touched by the package-rename campaign, not this feature).

## Notes

The identity gate blocks the first change of a session until an identity read, so the responsiveness probe issues a `cadrumo_whoami` read before dispatching the open-world verb - a real client sequence, not a stub. The in-process wall-clock ceiling cannot force-terminate a hung local verb the way the subprocess tree can; on breach the abandoned worker holds the stdout capture lock until it finishes, so subsequent in-process calls queue behind it. Local READ/MUTATE verbs are bounded compute, so this is a safety net for a pathological hang, which the crash-restart path covers; it is documented, not silent. The warm-path-specific responsiveness assertion plus the idle-lock custody and crash-restart regressions land in S17.

Review remediation (MEDIUM-1): the "subsequent in-process calls queue behind it" caveat above is superseded. `_run_tool` now fails fast rather than wedging the whole warm transport: a bounded capture-lock wait (`cadrumo_mcp_warm_capture_wait_seconds`) means a call never queues forever, and once a worker has held the capture past the wedge threshold (`cadrumo_mcp_wedge_threshold_seconds`, default the MUTATE ceiling) the transport is declared wedged and READ/MUTATE calls degrade to the proven subprocess transport, carrying a warning Notice naming the wedge; warm serving resumes automatically once the worker completes and releases the capture. Real-behavior proof in `test_warm_wedge_fallback.py`.

Corrected framing (honesty): the fallback preserves the RESULT (the parity oracle proves the envelope is byte-identical across transports), but it is NOT service-invisible. During a wedge a warm call goes from ~53 ms to a ~5 s subprocess, and before the wedge flag trips a contended call can wait up to the bounded acquire (default 5 s) for up to the 180 s wedge threshold; that is real, bounded, temporary service degradation, not "invisible except latency". MEDIUM-2's soft-timed-out MUTATE that finishes in the background is likewise an operator-visible surprise (reported failed, may have landed) that the idempotent-retry Notice mitigates but does not eliminate. Both are accepted trade-offs against the far worse total-transport wedge, stated plainly rather than glossed.

Absorbed in-scope regression (safety): a peer refactor (`38eba09021 refactor(config): hard-cut reset CLI lifecycle`) split the destructive `config.reset` (`destructive=True`) into `config.reset.start/resume/status` but left `application/operator_surface/_risk_table.py` with the stale `config.reset` row and no rows for the new commands. Because a missing row classifies all-false, the destructive `config.reset.start`/`config.reset.resume` verbs were agent-callable on the MCP surface at `auto_approve` - no human confirmation before an irreversible local-state wipe. Fixed under coordinator authority (the config-reset owner is unaddressable; over-declaration is fail-closed): `config.reset.start` and `config.reset.resume` declared `destructive=True` (inheriting the pre-split contract), `config.reset.status` a read declaration, bare `config.repair` a read declaration (its report builder is read-only, verified), and the stale `config.reset` row removed. Proof: both previously-red `test_risk_table_parity` cases green; `confirmation_for_tool` for `config.reset.start`/`config.reset.resume` now returns `confirm` (the elicitation/refusal route) instead of `auto_approve`; the rule-surface conformance gate and the HITL/dispatch/confirmation suites (50 tests) stay green.
