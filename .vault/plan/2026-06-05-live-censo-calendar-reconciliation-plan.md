---
tags:
  - '#plan'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-reference]]'
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
  - '[[2026-06-03-modelo-036-census-sync-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `live-censo-calendar-reconciliation` `implementation` plan

## Wave `W01` - censo taxpayer-model bridge

Make censo apply produce defensible taxpayer-model facts that the existing calendar projection already understands.

### Phase `W01.P01` - censo-derived facts

Derive only taxpayer-model facts that are directly supported by censo or profile evidence. Absent activity evidence remains unresolved instead of being converted into invented obligations.

- [x] `W01.P01.S01` - Add censo/profile taxpayer fact derivation; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W01.P01.S02` - Add real-behavior service and calendar tests for censo-derived obligations; `src/aeat/application/user_profile/tests/test_censo_sync.py`.

## Wave `W02` - live verification and closeout

Verify the CLI path from censo refresh/apply to calendar, including authenticated live-read attempts and explicit external-auth blockers.

### Phase `W02.P02` - gates and live checks

Verify the censo-to-calendar path with focused non-live tests first, then record either successful read-only live evidence or an authenticated external blocker. Lack of live proof remains open work rather than local completion.

- [x] `W02.P02.S03` - Run focused lint/tests plus live censo/calendar CLI verification; `.vault/exec/2026-06-05-live-censo-calendar-reconciliation`.
- [x] `W02.P02.S04` - Run code review and persist audit; `.vault/audit/2026-06-05-live-censo-calendar-reconciliation-code-review-audit.md`.

## Wave `W03` - live 036 reconciliation proof

Make the unresolved live acceptance gap explicit: pull Modelo 036/censo information, reconcile it into the taxpayer profile, enumerate legally applicable Modelo obligations, and prove the calendar shows both app-ready and AEAT-submitted/justificante states from live-backed snapshots.

### Phase `W03.P03` - live censo obligation calendar gate

Verify that authenticated live censo evidence is the source of profile enrolment facts, that derived Modelo obligations are enumerated from the reconciled legal situation, and that calendar evidence distinguishes local ready-to-file state from AEAT submitted and justificante-verified state.

- [x] `W03.P03.S05` - Run live Modelo 036 censo refresh and capture exact authenticated result or external blocker; `.vault/exec/2026-06-05-live-censo-calendar-reconciliation`.
- [ ] `W03.P03.S06` - Reconcile live censo snapshot into profile-derived taxpayer model and obligation enrolment facts; `src/aeat/application/user_profile/_censo_sync.py`.
- [ ] `W03.P03.S07` - Verify reconciled taxpayer obligations project to actual calendar entries with real filing dates; `src/aeat/application/overview/__init__.py`.
- [x] `W03.P03.S08` - Verify calendar evidence includes live-backed filings messages and justificante states without conflating local filing readiness; `src/aeat/entrypoints/cli/_overview.py`.

## Wave `W04` - live profile-store unlock and final calendar proof

Resolve the encrypted-store unlock blocker, rerun authenticated Modelo 036/censo pull, apply the snapshot, and prove legal obligations plus live filing/message/justificante evidence in the calendar.

### Phase `W04.P04` - profile-bound live verification

Run the full profile-bound live CLI sequence after the encrypted secret store is unlocked non-interactively.

- [x] `W04.P04.S09` - Unlock profile-bound live storage with a non-interactive secret-store passphrase or keychain session; `env/.env`.
- [ ] `W04.P04.S10` - Rerun live Modelo 036 censo pull, compare, apply, expedientes, notifications, filed history, and justificante pulls; `src/aeat/entrypoints/cli/_config/_profile_censo.py`.
- [ ] `W04.P04.S11` - Prove the active profile calendar contains legal obligation rows reconciled with live submitted and justificante-verified evidence; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W04.P04.S12` - Fail fast when profile-bound live CLI cannot prompt for secret-store passphrase; `src/aeat/adapters/persistence/storage/master_key/_master_key_io.py, src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`.

## Wave `W05` - authenticated live surface proof

Record the authenticated fresh-profile live reads that reached AEAT and verify calendar projection, while keeping Modelo 036 reconciliation open when G313 returns no legible censo.

### Phase `W05.P05` - fresh-profile AEAT read proof

Use the fresh password-backed profile and persisted live Clave session to prove all current live read facades and calendar projection behavior.

- [x] `W05.P05.S13` - Record authenticated live all-model filing, expedientes, notifications, and calendar proof; `src/aeat/entrypoints/cli/_app_live.py, src/aeat/entrypoints/cli/_app_live_payloads.py, src/aeat/entrypoints/cli/_overview.py`.
- [x] `W05.P05.S14` - Standardize live filed and expedientes bulk reads on pull only and verify Period-safe CLI output; `src/aeat/entrypoints/cli/_app_live.py, src/aeat/entrypoints/cli/_app_live_expedientes_cli.py, src/aeat/entrypoints/cli/_app_live_payloads.py`.
- [x] `W05.P05.S15` - Verify typed Period registry, filed-state, IVA wallet, and calendar evidence boundaries after period stringification landed; `src/aeat/application/registry/__init__.py, src/aeat/entrypoints/cli/_app_live.py, src/aeat/entrypoints/cli/tests/test_registry_cli.py, src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.
- [x] `W05.P05.S16` - Enforce calendar justificante state consistency at typed evidence and event boundaries; `src/aeat/application/overview/_calendar.py, src/aeat/application/overview/tests/test_calendar.py`.
- [x] `W05.P05.S17` - Prevent non-ALTA AEAT register rows from upgrading calendar submitted or justificante evidence; `src/aeat/application/overview/_calendar.py, src/aeat/application/overview/tests/test_calendar.py, src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.
- [x] `W05.P05.S18` - Require ALTA AEAT register status before persisting filed observations into official calculation and IVA history; `src/aeat/application/live/_filed_observation_persistence.py, src/aeat/application/live/tests/test_filed_capture_calculation_history.py`.

## Description

This plan closes the explicit live-censo calendar gap: Modelo obligations must derive from the taxpayer's legal situation, and the calendar must prove whether it used live censo-backed facts, profile facts, or refused because the necessary facts were not present.

## Verification

- A censo snapshot with DNI/NIE-backed profile identity and IAE epigraph applies derived taxpayer facts for natural-person economic activity.
- The derived facts make `projection_for_taxpayer` complete enough for the overview calendar to enumerate Modelo obligations.
- A censo snapshot without IAE/taxpayer-axis evidence does not silently infer obligations.
- Live `config profile censo refresh` is attempted and the result or authenticated external blocker is recorded.
- Focused tests and lint pass.
