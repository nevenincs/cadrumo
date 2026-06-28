---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S02'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W01.P01.S02 - Live surface classification

Scope: classify inventoried live surfaces by direction, owner, and manual evidence requirement.

## Description

- Classify every inventoried live surface as authenticated pull, local projection, local verification, local navigation/read catalogue, or prohibited remote mutation.
- Record owner lanes for backend, CLI, storage, registry, and QA verification.
- Record manual evidence requirements without treating missing live credentials as completion.

## Outcome

Authenticated pull surfaces:

- `config profile censo pull`: backend owner censo/profile, CLI owner profile censo, storage owner encrypted censo snapshot, QA owner live censo/calendar. Manual evidence requires a profile tax ID matching the authenticated AEAT identity and a readable G313 result or exact external blocker.
- `app live filed list`, `app live filed pull`, `app live filed pull-sources`: backend owner filed-data capture, CLI owner live filed, storage owner official evidence and calculation observation persistence, QA owner live filed/calendar. Manual evidence requires authenticated filed register output and stamped persisted official evidence.
- `app live expedientes pull`: backend owner expedientes, CLI owner live expedientes, storage owner expedientes snapshots, QA owner live expedientes/calendar. Manual evidence requires authenticated rows or typed empty state.
- `app live notifications pull`: backend owner notifications, CLI owner live notifications, storage owner notification snapshots, QA owner live notifications/calendar. Manual evidence requires authenticated notification rows or typed empty state with no acknowledgement path.
- `app live justificante pull`: backend owner justificante capture/reconcile, CLI owner live justificante, storage owner official receipt artefact, QA owner justificante/calendar. Manual evidence requires filed-period receipt match or typed no-filed-declaration refusal.
- `app live iva-wallet pull`, `app live iva-wallet pull-history`, `app live iva-wallet pull-remote-state`: backend owner IVA remote acquisition, CLI owner live IVA wallet, storage owner IVA history/wallet manifests, QA owner IVA wallet. Manual evidence requires read-only wallet/filed-history capture outcomes and no form submission.
- `app live verify nif-iva`, `app live verify tgvi`: backend owner verify adapters, CLI owner live verify, storage owner verification observations, QA owner verification. Manual evidence requires public read verification response or typed live unavailable blocker.

Local projection surfaces:

- `config profile censo apply`, calendar projection, overview projection, IVA history `history`, registry filed-state comparison, and persisted list/view/latest commands. These surfaces can change local encrypted/projected state but must not contact AEAT as remote mutation.

Local verification surfaces:

- `aeat app registry verify-filed-state`, live command conformance tests, remote-operation guard tests, access-gate tests, source scans for forbidden aliases, and overview/calendar consistency tests.

Local navigation or catalogue surfaces:

- `app live portals list/view` and Renta Web Open/borrador read probes. Portal commands are local catalogue reads; Renta Web Open and borrador live probes must remain guarded read/navigation paths with safety checks for write-shaped actions.

Prohibited remote mutation surfaces:

- Any AEAT submit, push, acknowledge, dismiss, sign, pay, synchronize-back, portal form mutation, notification acknowledgement, or live write. The central live write gate must refuse these before transport is built.

## Verification

- `uv run aeat app live --help` and live subgroup help commands passed and showed read-only command language.
- `uv run aeat config profile censo --help` passed and showed censo pull plus local show/compare/apply.
- `uv run aeat app registry --help` passed and showed local filed-state verification.
- Focused safety tests passed with 52 selected tests, covering live read/write gate behavior, remote-operation policy, command-tree alias drift, IVA wallet no-submit wording, and live subgroup write-verb absence.

## Notes

The latest authenticated live evidence is inherited only as status context. This classification row does not claim successful authenticated pull for censo, filed, expedientes, notifications, justificante, IVA wallet, verify, or Renta Web Open beyond the predecessor records that explicitly captured those runs.
