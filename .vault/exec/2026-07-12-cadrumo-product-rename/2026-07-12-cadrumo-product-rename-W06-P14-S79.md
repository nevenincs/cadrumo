---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:5aa7e659b87da53529a8e46ba1a230c8880484180ae235f3b51ffccade2bc315'
step_id: 'S79'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Run installed-wheel, split-companion, Docker, MCP handshake, locale, and documentation gates

## Scope

- `CADRUMO artifact acceptance surface`

## Description

- Build the core wheel in a fresh venv and run the installed-CLI smoke (`dev/packaging/smoke_core.py`).
- Build the slim wheel plus both `cadrumo-data-*` companion wheels and prove the degraded-then-byte-identical split-install contract (`dev/packaging/smoke_split_install.py`).
- Attempt the Docker clean-install probe; record the exact blocker if the local Docker daemon is unreachable rather than skipping silently.
- Confirm the MCP handshake gate via the `src/cadrumo/entrypoints/mcp/tests` suite (already exercised for real in the S78 run).
- Run the locale-catalogue scaffold drift check (`python -m cadrumo.locales scaffold --check`).
- Run the generated-API-reference drift check (`python -m dev.docs.apidocs scaffold --check`).

## Outcome

- **Installed wheel**: `uv run python dev/packaging/smoke_core.py --work-dir <scratch>` passed: built `cadrumo-0.2.1-py3-none-any.whl`, installed into a fresh venv, ran the bundled-resource and profile/config smoke. Manifest recorded at `packaging-smoke-manifest.json`.
- **Split-companion**: `uv run python -m dev.packaging.smoke_split_install --work-dir <scratch>` passed: built the slim `cadrumo` wheel plus `cadrumo_data_manuals-0.2.1-py3-none-any.whl` (76.7 MB) and `cadrumo_data_official-0.2.1-py3-none-any.whl` (62.5 MB); the slim-alone venv correctly reported the degraded path (split absence detected, remedy advisory, full authority deferred); installing both companions into the same venv made the advisory disappear and full source verification ran clean (byte-identical path).
- **Docker**: BLOCKED. `docker version` / `docker info` on this machine report `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine: ... The system cannot find the file specified` — the Docker Desktop daemon is not running on this host. The `docker` client binary is present (29.5.3) but the daemon is unreachable, so `dev/packaging/smoke_docker.py` cannot be exercised from this session. This is an honest environment blocker, not a skipped check; the prior `2026-07-13-cadrumo-product-rename-s39-docker-smoke-audit` documents an earlier successful run and remains the last real-behavior evidence for this gate until a daemon is available in-session.
- **MCP handshake**: covered by the S78 fresh-pass run of `src/cadrumo/entrypoints/mcp/tests` (`test_client_handshake.py`, `test_capability_posture.py` included in the 348-passed batch).
- **Locale scaffold drift**: `python -m cadrumo.locales scaffold --check` (with `CADRUMO_LOCAL_STORAGE_ROOT` pointed at a scratch dir to avoid the stale `var/aeat.db` `FormerProductStateError`) reported `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, `hu.yml: ok` — no drift.
- **Documentation generated-reference drift**: `python -m dev.docs.apidocs scaffold --check` reported "Stub tree is conformant. No drift detected."

## Notes

The Docker daemon blocker is environment-specific to this session (Docker Desktop not started) and not a defect in the rename's Docker artefacts; `dev/packaging/smoke_docker.py` itself was not modified and its prior PASS evidence (S39 audit) stands. No production code was modified for this Step; it is a real-behavior gate-running Step. All gates that could run in this environment passed cleanly against current HEAD.
