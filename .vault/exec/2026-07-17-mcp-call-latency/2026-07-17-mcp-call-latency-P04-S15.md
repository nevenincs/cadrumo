---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:8cb4eece1c1a1b8a55da43ca7eda7f1577bb08c50675b91e35538356d0483b4d'
step_id: 'S15'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Pre-provision the MCPB environment once and launch the interpreter directly thereafter, removing the per-session uv run resolution from the manifest launch

## Scope

- `packaging/mcpb/build.py`

## Description

- Split the MCPB entry into a self-healing bootstrap (`src/server.py`) and the digest-verifying real server (`src/_serve.py`) in `build.py`: the bootstrap provisions the bundle-local `.venv` once via `uv sync` (recording the cohort digest in a `.venv/.cadrumo-cohort` marker), then `os.execv`s the provisioned interpreter directly on `_serve.py`; every later launch sees the marker and direct-execs, skipping uv's project resolution entirely.
- Change the manifest launch to `uv run --no-project --directory ${__dirname} src/server.py` so the bootstrap runs on a bare interpreter with no per-session project resolution; update the `build.py` validator to require the new args.
- Keep the digest-pinned cohort guarantee: `_serve.py` runs the identical wheel-digest verification as before, now in the provisioned interpreter where the cohort is installed.
- Stop the smoke harness (`smoke_mcpb.py`) pre-syncing: it now drives the bootstrap's own first-launch provisioning, then a second launch, asserting the cohort-marker mtime is unchanged (proving the second launch direct-execed with no re-resolution), before the concurrent launches and oracle.
- Update `test_build.py` (new args, both bundle files, bootstrap-vs-serve content split, a bootstrap provisioning-state unit test) and `test_client_install.py` (new launch-arg indices, `src/_serve.py` presence, first/second-launch proof keys).

## Outcome

Validated locally: `build.py --check` accepts the new manifest; the full-cohort build test asserts the bundle carries both `src/_serve.py` (digest verify) and `src/server.py` (bootstrap with `os.execv` + `uv sync`, no digest code); the bootstrap unit test proves provisioning-state keys on the cohort marker (re-provisions until the marker matches the digest, and a digest change invalidates it). Ruff, format, and ty are clean across `build.py`, `smoke_mcpb.py`, and both tests.

## Notes

Grounding for option 2 over bare `--no-sync`: the team lead confirmed empirically on the real installed Windows extension that Claude Desktop extracts and immediately launches (the first `uv run` provisions); install-time provisioning is NOT a guaranteed separate phase, so bare `--no-sync` would break a real first launch. The self-healing bootstrap works whether or not the client pre-provisions. The full-cycle validation - the real MCPB install through the official validator plus the tax oracle - remains the release-CI gate `test_client_install.py` (needs npx, network, a real cohort, and ~20 min); it is not runnable in this sandbox, so the bootstrap's actual `uv sync`/`os.execv` behavior on the real cohort is CI-validated, not proven here. The bootstrap assumes single-writer first-launch (one server per client session); it does not add cross-process provisioning locks.
