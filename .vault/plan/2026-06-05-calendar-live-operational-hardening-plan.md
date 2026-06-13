---
tags:
  - '#plan'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-calendar-live-operational-hardening-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
  - '[[2026-06-04-calendar-live-filing-integration-live-verification-audit]]'
  - '[[2026-06-02-modelo-721-cripto-data-fidelity-adr]]'
---


# `calendar-live-operational-hardening` `implementation` plan

## Wave `W01` - live registry boundaries

Convert authenticated live verification residuals into committed registry guard fixes or explicit unsupported-boundary rows before expanding the operator facades.

Harden the live calendar operating surface after authenticated AEAT verification exposed residual CLI and registry boundaries.

### Phase `W01.P01` - registry guard repair

Commit the verified M190 declarations-host guard and convert unsupported registry/live combinations into explicit failure semantics.

- [x] `W01.P01.S01` - Strengthen M190 filed declarations host guard after live capture rerun; `src/aeat/domain/calculations/registry/test_modelo_190_registry.py`.
- [x] `W01.P01.S02` - Report Modelo 721 filed capture as an explicit unsupported live boundary; `src/aeat/application/live/__init__.py`.

## Wave `W02` - calendar operator facades

Add the missing CLI parity surfaces operators need to refresh calendar-visible filing events and inspect latest message state from persisted live snapshots.

### Phase `W02.P02` - live facade parity

Add missing local and live-read CLI commands needed to operate messages, expedientes, and calendar event refresh flows.

- [x] `W02.P02.S03` - Add notifications latest CLI facade; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W02.P02.S04` - Add expedientes capture-all live facade; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W02.P02.S05` - Add live facade payload schemas and tests; `src/aeat/entrypoints/cli/test_registry_cli.py`.

## Wave `W03` - verification and review

Run focused tests, live read-only checks, execution records, and code review before closing the operational hardening wave.

### Phase `W03.P03` - verification closeout

Run focused automated checks, live read-only command verification, execution records, and formal code review.

- [x] `W03.P03.S06` - Run focused unit and CLI verification; `src/aeat/entrypoints/cli/test_registry_cli.py`.
- [x] `W03.P03.S07` - Run live read-only operational verification; `.vault/audit/2026-06-05-calendar-live-operational-hardening-live-verification-audit.md`.
- [x] `W03.P03.S08` - Persist execution records and code review audit; `.vault/exec/2026-06-05-calendar-live-operational-hardening`.

## Description

This plan follows the completed calendar/live filing integration and live verification audit. It keeps live reads explicit, local calendar projection local-only, and unsupported AEAT/registry boundaries reported as structured results rather than silent omissions or remote timeouts.

## Steps

## Parallelization

Registry-boundary hardening and CLI local-read parity can proceed in parallel after payload names are stable. Live verification must run after implementation and focused tests.

## Verification

- Focused unit tests pass for registry read-surface guards, live bulk capture failure classification, notifications latest, and expedientes bulk capture payloads.
- Focused CLI help and JSON envelope tests pass for all new or modified commands.
- Live read-only verification confirms filed history, justificantes, messages, expedientes, and calendar aggregation operate from the active authenticated session.
- Code review audit records no HIGH or CRITICAL findings.
