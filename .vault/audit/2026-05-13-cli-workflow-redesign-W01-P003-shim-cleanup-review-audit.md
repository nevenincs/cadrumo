---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-w01-p003-exec]]'
---

# `cli-workflow-redesign` `W01.P003 shim cleanup` Code Review


W01-P003-SHIM-001 | MEDIUM | S0013 still overclaims deletion while retired CLI shim modules remain in the source tree.

The W01.P003 exec record says the rejected `app declaration`, `app invoice`, `app topic`, and old `entrypoints.cli.auth` compatibility registry surfaces were deleted, but `src/aeat/entrypoints/cli/_declaration.py`, `src/aeat/entrypoints/cli/_invoice.py`, `src/aeat/entrypoints/cli/_topic.py`, and `src/aeat/entrypoints/cli/auth/_registry.py` still exist. The root registration in `src/aeat/entrypoints/cli/__init__.py` no longer mounts those app shims, so operator reachability appears removed, but S0013 is a deletion claim and the old source files still define Typer apps or setup-auth registry behavior. The auth registry is also still named in the central error registries. Either delete or relocate the remaining retired modules and registry references, or revise the plan and exec text so S0013 does not claim deletion that has not happened.

W01-P003-SHIM-002 | LOW | Certificate-backend strict parsing is implemented, but configuration guidance still advertises rejected enum names.

`src/aeat/core/config.py` now accepts the settings-shape values `playwright_context` and `httpx_fallback`, and `src/aeat/tests/test_config.py` rejects the legacy enum-name input `PLAYWRIGHT_CONTEXT`. The field description in `src/aeat/core/config.py` still says `PLAYWRIGHT_CONTEXT by default`, and `env/.env.example` still documents `AEAT_CERTIFICATE_BACKEND=PLAYWRIGHT_CONTEXT` / `HTTPX_FALLBACK`. That stale guidance will make a copied example environment fail validation after the shim deletion. Update the example and field help to the accepted lowercase values and consider adding coverage that the shipped example value is accepted.

W01-P003-SHIM-003 | RESOLVED | The remaining retired CLI shim modules and stale auth-registry references were deleted.

`src/aeat/entrypoints/cli/_declaration.py`, `src/aeat/entrypoints/cli/_invoice.py`, `src/aeat/entrypoints/cli/_topic.py`, `src/aeat/entrypoints/cli/auth/__init__.py`, and `src/aeat/entrypoints/cli/auth/_registry.py` are absent. The central error registries no longer name `aeat.entrypoints.cli.auth._registry` errors. CLI tests now assert the retired `app invoice`, `app declaration`, `app archive`, and `app topic` surfaces are rejected instead of preserving their behavior.

W01-P003-SHIM-004 | RESOLVED | Certificate-backend guidance now matches strict lowercase settings values.

`src/aeat/core/config.py` describes `playwright_context` and `httpx_fallback`, `env/.env.example` sets `AEAT_CERTIFICATE_BACKEND=playwright_context`, and `src/aeat/tests/test_config.py` covers both accepted lowercase input and rejected uppercase enum-name input.

W01-P003-SHIM-005 | RESOLVED | Active suggestions no longer point at retired command names.

The obsolete live test for `setup auth` was deleted. Active error suggestions and user-visible next actions were rewritten away from retired `setup auth`, `app declaration`, `app invoice`, `app archive`, and `app topic` names. Residual mentions of those exact command strings in source are negative tests that prove they are absent from the accepted help surface.
