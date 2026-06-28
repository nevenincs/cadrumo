---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W02.P03.S08 / W02.P04.S10 auth representation gate live retry

## Scope

Continued the authenticated read-only live verification sweep with the
operator available. This slice focused on the Clave Movil authentication
path that blocks censo, filed-history, justificante, expedientes,
notifications, and live-backed calendar proof.

## Live Run

Created a fresh isolated runner and storage root:

- root: `var/live-auth-20260613-ready-auth`
- runner: `var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1`
- redacted log: `var/aeat/live-auth-run/live-auth-20260613-ready-auth.log`
- profile label: `live-auth-20260613-ready-auth`
- provider: `clave_movil`

The first supplied operator passphrase was refused by the secure-storage
minimum-length gate because it was shorter than eight characters. A second
operator-provided passphrase meeting the verifier minimum created the isolated
profile successfully.

Successful local/live-preflight facts observed:

- `config profile create` succeeded for the isolated profile.
- `config auth configure --provider clave_movil` succeeded.
- Auth status reported provider configured, active profile ready, profile tax
  id present, Clave identity present, and identity alignment `matches`.
- The live censo/filed command preflights used the canonical `pull` surfaces;
  no `pull-all` or `capture-all` command was invoked.

Initial live failures:

- `config auth login --provider clave_movil --fresh --reset-lock` failed at
  AEAT's representation dispatcher with
  `representation_gate_own_name_unavailable`.
- `config profile censo pull` repeated the same representation-gate failure.
- `config profile censo compare` then correctly refused because no censo
  snapshot had been captured.

Encrypted diagnostics showed that the live representation page did expose the
own-name controls: form `repForm`, radio `#propio` checked, representative
radio `#representante` unchecked, and a visible `#alertsModal.show` with a
capitalized `Continuar` button. This proved the previous failure was a driver
fragility, not a represented-party-only account state.

## Implementation

Hardened `src/aeat/adapters/outbound/aeat/auth/_clave_movil_page_flow.py`:

- Parse the representation page HTML only for structural control state.
- Refuse if representative mode is already selected.
- Treat a checked own-name radio as already selected, avoiding a fragile click
  on `label[for="propio"]` or `#propio`.
- Dismiss only visible `#alertsModal.show` modals.
- Try the observed capitalized `Continuar` alert button selector before the
  lowercase configured token, with a modal-footer button fallback.

Added focused regression coverage in
`src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py` for the
live-observed checked-own-name representation shape.

## Retry Outcome

After the patch, a focused live retry of:

`aeat config auth login --provider clave_movil --fresh --reset-lock`

no longer reproduced the representation-gate failure. It reached the Clave
Movil push wait page and timed out after the configured 120 seconds:

- diagnostic id: `20260613T123254Z`
- failure mode: `auth_completion_timeout`
- current URL host/path: `www12.agenciatributaria.gob.es` /
  `/wlpl/MOVI-P24H/ObtenerClaveMovil`
- verification code present: true
- phone state recorded: `operator_did_not_check`

No successful live AEAT read is claimed. No live Modelo 036/censo snapshot,
filed history, justificante, notification, expediente, or live-backed calendar
proof was captured in this slice.

## Verification

Passed:

- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil_page_flow.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py`
- `uv run pytest -m "" src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py -k "representation_dispatcher" -q --tb=short`
- `uv run pytest -m "" src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py -q --tb=short`

Operator diagnostic reporting:

- `aeat config auth diagnostics report 20260613T123254Z --phone-state operator_did_not_check`

Non-applicable failed check:

- `uv run ruff check ... var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1`
  was attempted accidentally. Ruff is the Python linter and reported syntax
  errors for the PowerShell runner; this is not a Python gate failure.

## Remaining Blocker

The authenticated live sweep remains blocked at operator-mediated Clave Movil
completion. The representation-dispatcher fragility is locally fixed and the
next live attempt should focus on whether the Clave app prompt is actually
received and accepted for diagnostic `auth_completion_timeout` cases.
