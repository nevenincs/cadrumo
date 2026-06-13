---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S01'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W01.P01.S01 - Live surface inventory

Scope: inventory every production live CLI command and backend live facade before authenticated exercise.

## Description

- Inventory the `app live` command tree through real CLI help output.
- Inventory the `config profile censo` live censo command group through real CLI help output.
- Inventory the registry verification command that consumes captured AEAT filed-state evidence.
- Inventory application live facades, outbound AEAT adapters, access gates, and existing live test lanes.
- Read same-day live censo/calendar exec records before recording sweep evidence.

## Outcome

The production live CLI surface currently exposes these operator-facing command groups:

- `aeat app live filed`: `list`, `pull`, `pull-sources`.
- `aeat app live expedientes`: `pull`, `list`, `view`, `latest`.
- `aeat app live notifications`: `pull`, `list`, `view`, `latest`.
- `aeat app live justificante`: `pull`, `list`, `view`.
- `aeat app live iva-wallet`: `pull`, `history`, `pull-history`, `pull-remote-state`.
- `aeat app live verify`: `list`, `view`, `latest`, `nif-iva`, `tgvi`.
- `aeat app live portals`: `list`, `view`.
- `aeat app live borrador 100`: nested Modelo 100 borrador snapshot commands.
- `aeat config profile censo`: `pull`, `show`, `compare`, `apply`.
- `aeat app registry verify-filed-state`: local verification against captured AEAT filed-state evidence.

The backend live facade inventory is:

- Authentication and session substrate: `active_verified_session`, `AeatAccessGate.require_live_read`, `AeatAccessGate.require_live_write`, Clave Movil and certificate providers, encrypted session storage.
- Censo: `CensoSnapshotService`, censo sync service, G313 live adapter.
- Filed declarations: listing, single pull, bulk pull, source pull, filed observation persistence.
- Expedientes: `capture_expedientes`, `capture_expedientes_bulk`, `ExpedientesService`.
- Notifications: `capture_notifications`, `NotificationsService`.
- Justificante: live receipt capture, persisted receipt list/view, reconciliation and evidence stamping.
- IVA wallet and filed-history acquisition: IVA compensation wallet capture, IVA history capture, typed remote acquisition report persistence.
- Borrador/Renta Web and portal surfaces: Modelo 100 borrador snapshot persistence, Renta Web Open read/navigation safety tests, local portal catalogue.
- Verify surfaces: NIF-IVA and TGVI verification observation persistence.
- Remote-operation policy: remote state guard and registry cross-reference policy surfaces.

Existing live and non-live coverage includes central auth gate tests, remote-operation guard tests, live command-tree drift guards, application live facade tests, outbound Sede parser/driver tests, and opt-in `aeat_live` tests for auth, filed declarations, censo, IVA wallet, Renta Web Open, verify, and justificante.

## Verification

- `uv run aeat app live --help` passed and showed only read/list/view/verify/navigation command groups.
- `uv run aeat config profile censo --help` passed and showed `pull`, `show`, `compare`, and `apply`.
- `uv run aeat app registry --help` passed and showed `verify-filed-state`.
- `uv run aeat app live filed --help` passed.
- `uv run aeat app live expedientes --help` passed.
- `uv run aeat app live notifications --help` passed.
- `uv run aeat app live justificante --help` passed.
- `uv run aeat app live iva-wallet --help` passed.
- `uv run aeat app live verify --help` passed.
- `uv run aeat app live portals --help` passed.
- `uv run aeat app live borrador --help` passed.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_gate.py src/aeat/domain/calculations/registry/tests/test_remote_state_guard.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_pull_help_locale_keys_do_not_use_capture_all_names src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestReadOnlyStructuralInvariants::test_no_submit_send_or_present_verb_exists -q` passed with 52 selected tests.

## Notes

No authenticated AEAT pull was attempted for this inventory row. Same-day live censo/calendar records show censo G313 remains blocked by no readable censo or identity mismatch, while filed, expedientes, notifications, and justificante refusal paths have recent authenticated evidence.
