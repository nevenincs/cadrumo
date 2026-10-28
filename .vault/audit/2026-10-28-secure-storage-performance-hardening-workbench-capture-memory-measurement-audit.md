---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:bf285867b70ce2706e1f66ad5cc0cc5a626a390b56e1c91db5c51511e91aea92'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
  - "[[2026-10-22-ledger-tui-doors-authenticated-stored-reads-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
---

# `secure-storage-performance-hardening` audit: `Workbench capture memory: measurement and no-go`

## Scope

Whether wiring the session-scoped `WorkbenchCaptureMemory` (`src/cadrumo/application/workbench_capture_memory.py`) into the Declarations list and workbench reads would remove the dominant cost of `modelo.declarations.list`. Wiring it would require a bounded plaintext-cache exception in the three related ADRs, so the decision rule was: go only if the work the memo skips dominates the capture phase and the gain is material at real-profile scale. Evidence: the per-phase `workbench_capture_phase` and `workbench_calendar_phase` records of an isolated Debug run on a synthetic profile (55 rows), the user's real-profile log, and an in-process cold-then-warm measurement of `build_overview_calendar` (one call each, no loops). No taxpayer data is quoted.

## Findings

### calendar-cost-is-process-warm-up | high | The calendar work the memo would skip is a first-call-per-process cost, not per-capture work

Synthetic profile, first list read in a fresh profile worker: `declaration_list_inputs` 1.91 to 2.75 s, of which `calendar_schedule` 1.44 to 1.77 s (about 75 to 80 percent); every store read, the portfolio, the summaries and the closing recheck were each under 0.15 s. The second read in the same worker took 0.43 s end to end, with `calendar_schedule` 0.011 s, `calendar_with_filing_evidence` 0.008 s and `agenda` 0.012 s. Within one cold capture, `calendar_with_filing_evidence` (the same `build_overview_calendar` call made a second time) already ran in 0.008 s. In process, a cold `build_overview_calendar` took 2.70 s and the immediately following identical call 0.067 s. The cold profile is dominated by first decoding of authority components into the generation-pinned `authority_cache` (1.37 s, of which full modelo revisions decoded to read one applicability rule 0.77 s, in `src/cadrumo/domain/calculations/registry/applicability.py:1233`), locale shard scans for modelo titles (0.49 s), the holiday calendar load (0.33 s) and deferred Pydantic model builds (0.21 s), all already retained for the process lifetime.

### memo-gain-is-immaterial | high | A per-session memo would save about 0.03 to 0.07 s per warm read and nothing on a cold one

A memo hit skips only the three calendar phases above, about 0.03 s of a 0.36 s warm capture on the synthetic profile and at most the 0.067 s warm calendar build in process. The bounded exception the ADRs would have to state clears the memo on worker loss, suspension, lock and sign-out, which are exactly the events that produce a cold worker; a cold read therefore always misses, and the 1.5 to 2.7 s it pays is untouched.

### real-profile-latency-is-not-calendar | medium | The real-profile 22 s reads are not attributable to repeated calendar work

The real-profile log predates the phase records. Its warm deadline schedules took about 0.02 to 0.06 s per filing year. The slow reads coincide with profile-worker exchange failures and restarts, agent-service startup and file-lock waits of up to 0.86 s (for example around a `runtime_connection_closed` refusal of a `modelo.declarations.list` submission), none of which a capture memo can remove.

### codes-query-localized-every-title | low | registry_modelo_codes resolved every modelo title to return codes

`registry_modelo_codes` built the full list report, whose `title` reads scan each modelo's locale shard on first use, only to keep the codes; obligation coverage calls it on every calendar build. Fixed at the owner (`src/cadrumo/application/modelo/registry_discovery.py:81`) by reading the directories' modelo identities in the same code order: the cold in-process calendar build fell from 2.70 s to 2.21 s, warm from 0.067 s to 0.061 s, with a parity test against the list report.

## Recommendations

- Leave `WorkbenchCaptureMemory` unwired and the three ADRs unamended; the measurement does not meet the decision rule (calendar-cost-is-process-warm-up, memo-gain-is-immaterial).
- The remaining cold cost is authority decoding. Narrowing applicability resolution to an applicability-only authority component would change the published authority format, and pre-warming at worker start is a background warm-up the secure-storage performance ADR rejects; either needs its own decision before implementation.
- Re-measure a real-profile read with the phase records once the concurrent worker-loss changes land, to separate worker respawn and lock waits from capture time (real-profile-latency-is-not-calendar).
