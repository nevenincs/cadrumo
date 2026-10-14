# Agent integration

Cadrumo is a tax filing application and implements no agent capability of its own. cadrumo-agent is a separate project. It alone decides which agents, providers, lanes and models it supports, and Cadrumo makes no ruling on any of them. Cadrumo's part is to build the agent into the native package and to launch and supervise it inside the signed-in profile. It also hands the agent the credentials the person stored and serves Cadrumo's tools to it through the packaged `cadrumo-mcp` relay. Whatever provider list appears anywhere in Cadrumo comes from the agent at run time. Process environments follow [the environment contract](environment-contract.md); the desktop side is covered in [the Tauri shell](build-tauri-desktop-shell.md) and [the frontend](build-desktop-frontend.md) references.

## Package side

The agent source is a local project folder named by the CMake cache variable `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`. Configure stops if the variable is unset or the folder holds no `pyproject.toml`, and the process environment is never consulted. `agent_project` builds the wheel with `uv build --no-sources` and records its version, name and SHA-256 in `agent-wheel.json`. `python_product` installs the wheel beside Cadrumo in the package library. Its dependencies come from one hashed lock per target in `native/agent/`, and every name shared with the root lock must carry the same specifier. Explicit `agent-lock-<target>` targets refresh those locks, and `agent-checksum`, `agent-uninstall` and `agent-rebuild` maintain the wheel. The package declares an agent image, `bin/cadrumo-agent`. The environment declaration admits only exact invocations of it: `-m cadrumo_agent.cli.main` with `serve`, `stores-state`, `setup`, `migrate` or `version --json`, plus `-m cadrumo_agent.worker`. ([variable](../../../../native/cmake/Agent.cmake#L4), [targets](../../../../native/cmake/Agent.cmake#L27), [admission](../../../../dev/packaging/native/agent.py), [image](../../../../native/package-layout.json#L44), [invocations](../../../../native/application-environment.toml#L505))

`bundle.agent` runs `native/tests/agent_smoke.py` under the staged package interpreter. It checks four things against the manifest:

- that the agent and Cadrumo import from inside the package;
- the distribution version and its satisfied requirements;
- the SHA-256 of every agent file;
- `version --json`, and that the hosting-contract and credential-frame versions match.

It does not launch the agent image, read a ready line or start a gateway. `bundle.environment-launch` starts the image the way the runtime does. Neither test shows that a hosted conversation works. ([test](../../../../native/cmake/Packaging.cmake#L238), [probe](../../../../native/tests/agent_smoke.py#L1))

## Runtime side

The only launch path is `aeat app agent serve`. Its first standard-input line is `{"bearer": ...}`; later input is drained, and end of input is the stop request. Standard output carries JSON lines only: `agent_ready` (gateway port, agent version, workspace root, lane), `agent_refused` with one closed code, and `agent_stopped` with a reason. A refusal exits 1, and the bearer buffer is wiped in all cases. The launcher never sees a provider key. ([command](../../../../src/cadrumo/entrypoints/cli/_app_agent_serve.py#L47), [protocol](../../../../src/cadrumo/entrypoints/cli/_app_agent_serve.py#L6), [refusal exit](../../../../src/cadrumo/entrypoints/cli/_app_agent_serve.py#L169))

The runtime's `_agent_start` admits only the `agent-host` frontend with a live human lease and refuses an unmarked lane root. It requires the agent image and relay, and allows one agent tree per profile. It prepares the agent stores before reading the bearer: `version --json`, then `stores-state`, then `setup` or `migrate`. `AgentHostController` then writes one credential frame (version 1, at most 64 KiB) to the agent's standard input and accepts only a ready line with hosting contract 1. Stopping closes standard input, waits, then ends the contained tree. ([start](../../../../src/cadrumo/entrypoints/runtime/profile_connection_agents.py#L193), [stores](../../../../src/cadrumo/application/agent_host/store_lifecycle.py#L1), [frame](../../../../src/cadrumo/application/agent_host/credential_frame.py#L23), [controller](../../../../src/cadrumo/application/agent_host/controller.py#L201), [contract](../../../../src/cadrumo/application/agent_host/controller.py#L38))

The agent's environment is built from an allow-list, never by clearing names. The runtime sets only the storage root and `CADRUMO_AGENT_HOSTED_ROOT`, `CADRUMO_AGENT_PORT`, `CADRUMO_AGENT_WORKER_PORT` and `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`. In the package, the agent and relay come from `CADRUMO_PACKAGE_AGENT_EXECUTABLE` and `CADRUMO_PACKAGE_RELAY_EXECUTABLE`. A development lane root must hold `.cadrumo-agent-lane.json`. ([environment](../../../../src/cadrumo/application/agent_host/launch_environment.py#L31), [programs](../../../../src/cadrumo/adapters/local_runtime/agent_programs.py#L31), [lane root](../../../../src/cadrumo/application/agent_host/lane_root.py#L24))

## Providers and credentials

Cadrumo keeps no provider list. It runs the agent's `providers --declared --json` with the allow-listed environment and bounded output, and caches the result per process. It parses the catalog strictly: `schema_version` must be 1, there are at most 64 lanes, and a lane id is `<provider>_<transport>`. Credentials for the providers cadrumo-agent declares are resolved in the profile worker under custody. They cross to the runtime as a protected secret frame and reach only the agent's standard input. In development storage mode alone, an unset provider falls back to `CADRUMO_LLM_<PROVIDER>_API_KEY`, built from the provider id. ([catalog source](../../../../src/cadrumo/adapters/local_runtime/agent_provider_catalog.py#L42), [parse](../../../../src/cadrumo/domain/provider_settings/catalog.py#L215), [key variable](../../../../src/cadrumo/domain/provider_settings/catalog.py#L40), [development only](../../../../src/cadrumo/application/provider_settings/resolution.py#L150))

## Desktop and lanes

The desktop agent host runs `aeat app agent serve` through the digest-verified packaged CLI, as a long-lived child in a kill-on-close Job Object. It holds the gateway bearer in memory and serves the agent column through `agent_*` commands and two channels. ([runner](../../../../native/desktop/src-tauri/src/agent/runner.rs#L3), [ready check](../../../../native/desktop/src-tauri/src/agent/launcher.rs#L100))

All four lanes below are opt-in; no default lane or gate calls them:

- `just verify-agent-live --package DIR` drives the person's side for an external cadrumo-agent package runner, which spends model credit.
- `just eval-agent-floor` runs the scripted MCP client against a verified copy of `build/windows-x64/stage/Release/app` and spends no model credit.
- `just eval-agent-live` runs an operator-supplied agent command, passed with `--agent-arg` and `--model`, and spends model credit. The eval lanes exit 0 passed, 1 agent failure, 2 product finding, 3 unavailable, 4 harness error.
- `just desktop-agent-live --provider ID` drives the packaged desktop window and needs an interactive desktop. It reads the developer key from `CADRUMO_LLM_<ID>_API_KEY` and exits 0, 1 or 3.

([recipes](../../../../justfile#L727), [eval lanes](../../../../justfile#L1317), [desktop lane](../../../../justfile#L1337), [default package](../../../../dev/agent_eval/live/lane.py#L94), [desktop key](../../../../dev/desktop_agent_live/lane.py#L97))

## Working notes

- Never add a provider, lane or model list, or a provider-specific branch, to Cadrumo code, records or docs. The agent's declared catalog is the only source.
- Scoped observations needing current-code checks:
  - The launcher and the desktop ready check accept only the lane value `development`.
  - `core/config_llm_fields.py` still declares per-provider key settings.
  - `dev/runtime_lifecycle/live_sign_in.py` hardcodes a local model identifier.

  ([launcher lane](../../../../src/cadrumo/application/agent_host/launcher_protocol.py#L26), [settings](../../../../src/cadrumo/core/config_llm_fields.py#L34))
- A packaged build needs `-DCADRUMO_PACKAGE_AGENT_SOURCE_DIR=<folder>` or a CMake user preset; no committed preset sets it.
- `bundle.agent` passing is package integrity, not a working hosted run. Runtime behaviour needs the signed-in Windows lanes above.
