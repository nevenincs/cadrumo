---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F08'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F08`

Hardened the wallet empty-result interpretation after the guarded AEAT wallet read query.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`

## Description

The parser no longer treats a no-table wallet page as an empty wallet when the page still exposes the executable `ejecutar` submit control. An authorized empty result now requires the configured wallet form shape without the execute submit. The live read-query driver also inspects the post-click page and raises `external_shape_changed` if AEAT leaves the executable wallet shell in place without a recognizable wallet table.

This keeps the safety posture fail-closed: an incomplete read cannot become `total_pending=0` compensation evidence. No live AEAT contact was made for this hardening pass.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 13 passed.
- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_pull_output_lines_name_guarded_read_query_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/core/test_external_constants.py::test_live_sede_executable_route_literals_stay_centralized src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 16 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.
