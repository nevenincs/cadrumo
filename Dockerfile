# Reproducible headless-Playwright-capable development image for Cadrumo.
#
# Used by `.devcontainer/devcontainer.json` (VS Code "Reopen in Container")
# and directly via `docker build`. Mirrors the base image already used by
# the `just packaging-smoke-docker-core` / `dev/packaging/smoke_docker.py`
# clean-Linux install proof, so this image and the packaging smoke gate
# stay on one Linux base convention.
#
# NOTE: this Dockerfile is authored from the project's documented uv +
# Playwright setup steps (see docs/workstation-setup.md) and has not been
# `docker build`-verified in this environment. Treat a real build as a CI
# follow-up (tracked from issue #101).

FROM python:3.13-slim

# -- OS-level prerequisites ---------------------------------------------
# curl/ca-certificates: the official uv installer script.
# git: uv workspace + vaultspec-rag git-aware tooling.
# build-essential: source builds for any dependency without a manylinux wheel.
# libnss3, libnspr4, libatk*, libcups2, libdrm2, libgbm1, libpango-1.0-0,
# libxkbcommon0, libasound2: the headless-Chromium shared-library baseline
# `playwright install --with-deps` would otherwise fetch itself; declaring
# them explicitly keeps the image reproducible under a minimal `slim` base
# without relying on Playwright's own apt-heuristics matching this base.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    build-essential \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# -- uv ---------------------------------------------------------------------
# Pinned installer version for a reproducible toolchain across rebuilds.
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh

# -- Non-root workspace user -------------------------------------------------
# Named to match the devcontainer's default `remoteUser`; owns the workspace
# mount and the persisted `~/.local/share/cadrumo/` state volume declared in
# devcontainer.json (the Cadrumo XDG data root).
ARG USERNAME=cadrumo
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USERNAME}

WORKDIR /workspace
COPY --chown=${USERNAME}:${USERNAME} . .

USER ${USERNAME}
ENV PATH="/home/${USERNAME}/.local/bin:/workspace/.venv/bin:${PATH}" \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/home/${USERNAME}/.cache/ms-playwright

# Pre-warm the dependency set (runtime + workbook extra + dev group), matching
# the `[unix] install` justfile recipe exactly. `[workbook-windows]` resolves
# to nothing on Linux (its sole dependency is `sys_platform == 'win32'`
# marker-gated) but is requested for parity with that recipe.
RUN --mount=type=cache,target=/home/${USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
    uv venv --python 3.13 .venv \
    && uv pip install --python .venv/bin/python --editable ".[workbook-windows]" --group dev

# Pre-bake headless Chromium plus its Linux system libraries so
# `playwright install --with-deps` is unnecessary at container start
# (issue #101 acceptance criterion).
RUN --mount=type=cache,target=/home/${USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
    python -m playwright install chromium

CMD ["bash"]
