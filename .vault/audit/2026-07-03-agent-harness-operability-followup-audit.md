---
tags:
  - '#audit'
  - '#agent-harness-operability-followup'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:3c2d2d1c6d70f2efd84592b04e854388d552a7418716ebe6095cfb986a4e7f3f'
related:
  - '[[2026-07-02-agent-harness-operability-followup-research]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `agent-harness-operability-followup` audit: `live-model measurement: regularizar-atrasos step 1`

## Scope

The persisted live-model measurement the refoundation close deferred (item 1 /
C2, the operator's headline goal). A live Claude-Opus persona operated the real
`aeat` CLI (the authed black-box tool) in an isolated storage sandbox as the AI
tax-advisor for a behind-but-fresh autónomo — never filed, zero work units —
answering "what have I missed?". This is the exact `regularizar-atrasos` persona
whose step-1 entry (`aeat app overview backlog`) the close review found
dead-on-arrival, so the measurement doubles as the live acceptance test for the
graceful-degradation fix landed this session (commit `59317b5b47`). The persona
oriented itself from `aeat app contract` and `--help` (no seeded assumptions),
created a real profile through the non-interactive flags, and drove the overview
surface. Real model, real CLI, real state (sandboxed) — the capability signal a
scripted driver cannot produce.

## Findings

### backlog-operable-for-fresh-persona | pass | `overview backlog` answers "what have I missed" for a zero-work-unit taxpayer

CORE VERDICT: PASS. `aeat app overview backlog` (no flags) rendered the overdue
set and exited 0 for a taxpayer with zero work units — it did not refuse. The
persona read `late_count 10` and a list whose every row carried
`source=registry_deadline` (Modelo 130 and 303 for 2025 2T/3T/4T and 2026 1T,
plus the 390 annual IVA summary and the 100 renta annual), and answered the
taxpayer directly. This confirms the backlog derives from the deadline schedule
plus obligation applicability, not from persisted work state, and that the
step-1 entry is now operable for its own persona. `agenda`, `status`, and
`explain 303`/`explain 130` (both `applicable true` with legal_refs and the
full profile-fact decision basis) also passed, so `backlog + agenda + explain +
status` form a complete regularizar-atrasos path.

The `work_units_degraded` WARNING did NOT fire — correctly. A fresh profile's
empty work-unit catalogue loads as empty (a normal state, `overview status`
says "No modelo work units have been started yet."), which is not a load
FAILURE, so the degradation notice's failure path is simply not exercised by
this persona. The notice is reserved for a genuine work-unit-subsystem fault,
which is the intended design.

### calendar-hard-refuses-fresh-persona | medium | `overview calendar` still refuses modelo-event evidence for a never-filed taxpayer, and `--allow-incomplete` does not relax it

The live persona surfaced a NEW defect a scripted test with seeded state would
miss: `aeat app overview calendar` hard-refuses (exit 2) for the same fresh
persona with `Invalid value: Local modelo event evidence is unavailable for this
calendar row.`, reproduced three ways (wide window, future-only window, no
flag). `--allow-incomplete` does not help, because that flag covers missing
PROFILE data, not missing modelo-EVENT evidence — so a persona reading the flag
name reasonably expects it to unblock and it does not. This is the SAME
operability class the backlog fix (`59317b5b47`) addressed: the calendar's
event-evidence loaders (`_local_live_calendar_events` /
`_local_modelo_record_calendar_events` / the filing-evidence loader in
`src/aeat/entrypoints/cli/_overview.py`) hard-refuse when their optional
persisted evidence is absent, rather than degrading to a schedule-only calendar
with a WARNING notice the way `backlog` now does. A taxpayer who follows the
natural "show me the calendar of what I owe" instinct after backlog hits a wall;
calendar is the odd one out and reads as broken to this persona.

### calendar-window-flags-inconsistent | low | `backlog` defaults the window; `calendar` requires `--from`/`--to`

Within one command family, `backlog` defaults `--from`/`--to` to a 365-day
window while `calendar` marks both `[required]`. A persona transferring muscle
memory from `backlog` to `calendar` hits `Missing option '--from'.`. The two
neighbouring verbs teach different contracts for the same window concept.

### explain-rationale-spanish-under-en | low | `explain` emits the registry rationale in Spanish even under `AEAT_OUTPUT_LANGUAGE=en`

Under `AEAT_OUTPUT_LANGUAGE=en`, `explain 303`/`130` still emit the
`rationale`/`scheduling_rationale` prose in Spanish (registry legal grounding is
authored in Spanish). Likely intentional, but the mix of English labels and
Spanish prose is worth a note. No mojibake or garbling was observed anywhere in
the session — English output was otherwise clean, confirming the UTF-8 handling
holds through the CLI surface.

## Recommendations

- Extend the `backlog` graceful-degradation fix to `overview calendar`: the
  event-evidence loaders should degrade to a schedule-only calendar with a
  WARNING notice when their optional persisted evidence is unavailable, exactly
  as `_local_modelo_work_units` now does, rather than hard-refusing the whole
  surface for a never-filed taxpayer. (Actioned this session — see the
  resolution note below.)
- Consider defaulting `calendar`'s `--from`/`--to` to the same 365-day window as
  `backlog` for family consistency (follow-up).
- Leave the Spanish registry rationale as-is unless an operator directive says
  otherwise; note the label/prose language split in the docs.

## Resolution

The PASS verdict confirms item 1 / C2 for the `regularizar-atrasos` step-1
entry: the headline live-model measurement ran against the real authed CLI with
a real Opus persona, the two hard safety invariants were not breached (the
persona never attempted a live submit and never fabricated a figure — every
overdue item was quoted from CLI output), and this report is the persisted
artifact the gate required. The `calendar-hard-refuses-fresh-persona` MEDIUM was
actioned in the same session (commit `4adf391107`) by extending the
graceful-degradation pattern to the three calendar event-evidence loaders, with
real-behavior regressions that each degrades to a WARNING notice rather than
refusing.
