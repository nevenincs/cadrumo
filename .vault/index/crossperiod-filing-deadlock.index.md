---
generated: true
tags:
  - '#index'
  - '#crossperiod-filing-deadlock'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:4eeffbcbde87b061ad6b240d7f976ee55800424e5fe8044a42384df6df2aae50'
related:
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-research]]'
  - '[[2026-06-21-crossperiod-filing-deadlock-audit]]'
  - '[[2026-06-21-crossperiod-filing-deadlock-plan]]'
  - '[[2026-06-26-crossperiod-filing-deadlock-audit]]'
---

# `crossperiod-filing-deadlock` feature index

Auto-generated index of all documents tagged with `#crossperiod-filing-deadlock`.

## Documents

### adr

- `2026-06-19-crossperiod-filing-deadlock-adr` - `crossperiod-filing-deadlock` adr: `Cross-period filing deadlock: late local work file and local-chain export` | (**status:** `accepted`)

### audit

- `2026-06-21-crossperiod-filing-deadlock-audit` - `crossperiod-filing-deadlock` audit: `Cross-period filing deadlock remediation - code review`
- `2026-06-26-crossperiod-filing-deadlock-audit` - `crossperiod-filing-deadlock` audit: `stash recovery + C3 drift remediation audit`

### exec

- `2026-06-21-crossperiod-filing-deadlock-P01-S01` - Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year
- `2026-06-21-crossperiod-filing-deadlock-P01-S02` - Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION
- `2026-06-21-crossperiod-filing-deadlock-P01-S03` - Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED
- `2026-06-21-crossperiod-filing-deadlock-P01-S04` - Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY
- `2026-06-21-crossperiod-filing-deadlock-P01-S05` - Update the workflow engine tests to Decision A semantics (targeted overdue admitted, closed-window FILE no longer aborts DEADLINE_PASSED)
- `2026-06-21-crossperiod-filing-deadlock-P02-S06` - Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property
- `2026-06-21-crossperiod-filing-deadlock-P02-S07` - Add _relax_same_year_local_chain admitting a same-year app_filing dependency whose blockers are a subset of the official-evidence-delta set, clearing those blockers and stamping the advisory facet
- `2026-06-21-crossperiod-filing-deadlock-P02-S08` - Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder
- `2026-06-21-crossperiod-filing-deadlock-P02-S09` - Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding
- `2026-06-21-crossperiod-filing-deadlock-P02-S10` - Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant
- `2026-06-21-crossperiod-filing-deadlock-P02-S11` - Ratchet the owned _cross_period_clean_state.py SPLIT-CANDIDATE size budget from 1265 to 1300 for the feature addition

### plan

- `2026-06-21-crossperiod-filing-deadlock-plan` - `crossperiod-filing-deadlock` plan

### research

- `2026-06-19-crossperiod-filing-deadlock-research` - `crossperiod-filing-deadlock` research: `Filing reachability: gate-refusal and silent-grant surface`
