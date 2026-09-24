# syntax=docker/dockerfile:1

# The Cadrumo contributor container image.
#
#   --target dev      Reproducible headless-Playwright-capable development
#                     image. Used by `.devcontainer/devcontainer.json`
#                     ("Reopen in Container") and by a direct
#                     `docker build --target dev`; no recipe wraps it.
#
# This image is not used by CI. It is the contributor environment, and
# nothing here describes or provisions the machines CI runs on: how a job
# is executed is not this repository's concern. A `runner` stage that built
# a self-hosted fleet machine, and the scripts it baked into it, were
# removed for that reason.
#
# ── One base, declared once ──────────────────────────────────────────────
# `PYTHON_BASE_IMAGE` is the single declaration point for the Linux base
# every Cadrumo container shares, read back by
# `dev/packaging/_base_image.py:linux_base_image`. Nothing may restate it:
# `dev/packaging/tests/test_container_base_image_singularity.py` WALKS the
# tree and fails on any surface that binds a bare `python:3.13-*` literal
# instead of deriving it from here — a comment asserting singularity is what
# this replaced, and a comment is exactly what did not hold.
#
# The interpreter minor inside this tag is separately joined to
# `dev/ci/python-runtime-matrix.json` by
# `dev/packaging/tests/test_runtime_floor_singularity.py`, so a base image
# shipping a runtime the project no longer supports cannot pass.
#
# The tag is pinned to the DISTRIBUTION (`-trixie`), not just the Python
# minor. `python:3.13-slim` is a moving tag: it silently rolled from Debian
# 12 (bookworm) to Debian 13 (trixie), and trixie's 64-bit `time_t`
# transition renamed every ABI-bearing library below to a `t64` suffix
# (`libasound2` -> `libasound2t64`, `libatk1.0-0` -> `libatk1.0-0t64`,
# `libatk-bridge2.0-0` -> `libatk-bridge2.0-0t64`, `libcups2` ->
# `libcups2t64`). The old names do not exist on trixie at all, so the apt
# layer broke on every cache-cold build while cache-warm machines kept
# passing — the worst shape of failure there is. Pinning the distro is what
# keeps the explicit package list below truthful.
ARG PYTHON_BASE_IMAGE=python:3.13-slim-trixie
ARG UV_VERSION=0.9.7

FROM ${PYTHON_BASE_IMAGE} AS base

# -- OS-level prerequisites ---------------------------------------------
# curl/ca-certificates: the official uv installer script.
# git: uv workspace + vaultspec-rag git-aware tooling.
# just: the project's task runner. The devcontainer `postCreateCommand`
#   (`just install && just env-setup`) and every documented dev lane invoke
#   it, so an image without it builds fine and then fails at container
#   creation. Debian trixie ships it (1.40.0), so no out-of-band download.
# build-essential: source builds for any dependency without a manylinux wheel.
# lib*: the headless-Chromium shared-library baseline `playwright install
#   --with-deps` would otherwise fetch itself; declaring them explicitly
#   keeps the image reproducible under a minimal `slim` base without relying
#   on Playwright's own apt-heuristics matching this base.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    just \
    build-essential \
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libdbus-1-3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# -- uv ---------------------------------------------------------------------
# Pinned installer version for a reproducible toolchain across rebuilds.
ARG UV_VERSION
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh

# -- Non-root workspace user -------------------------------------------------
# Named to match the devcontainer's default `remoteUser`; owns the workspace
# mount and the persisted `~/.local/share/cadrumo/` state volume declared in
# devcontainer.json (the Cadrumo XDG data root).
#
# `/workspace` is created and chowned HERE, before `WORKDIR`. A bare
# `WORKDIR /workspace` creates the directory owned by root, and
# `COPY --chown` only relabels the copied CONTENTS, never the directory
# itself — so the non-root user could not create `.venv` inside it and the
# build died on `failed to create directory '.venv': Permission denied
# (os error 13)`.
ARG USERNAME=cadrumo
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USERNAME} \
    && install -d -o ${USER_UID} -g ${USER_GID} /workspace

# A LOGIN shell re-runs /etc/profile, which sets PATH unconditionally and so
# discards everything the `ENV PATH` below puts in front of it — `python` then
# resolves to the interpreter at /usr/local/bin and `import cadrumo` fails.
# That hit both the VS Code integrated terminal (login shells) and
# `just devcontainer-test` itself, which invokes `bash -lc`. A profile.d
# snippet is the one place that survives the reset, so declare the venv in
# BOTH: `ENV` covers non-login `docker run`/`exec`, profile.d covers login.
RUN printf '%s\n' \
    '# Cadrumo: keep the project virtualenv ahead of the system interpreter.' \
    'PATH="/home/'"${USERNAME}"'/.local/bin:/workspace/.venv/bin:$PATH"' \
    'export PATH' \
    > /etc/profile.d/10-cadrumo-path.sh \
    && chmod 0644 /etc/profile.d/10-cadrumo-path.sh

WORKDIR /workspace
USER ${USERNAME}

ENV PATH="/home/${USERNAME}/.local/bin:/workspace/.venv/bin:${PATH}" \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/home/${USERNAME}/.cache/ms-playwright


# ── Development image ────────────────────────────────────────────────────
FROM base AS dev

ARG USERNAME=cadrumo
ARG USER_UID=1000
ARG USER_GID=1000

COPY --chown=${USERNAME}:${USERNAME} . .

# Pre-warm the dependency set (runtime + workbook extra + dev group), matching
# the `[unix] install` justfile recipe exactly. `[workbook-windows]` resolves
# to nothing on Linux (its sole dependency is `sys_platform == 'win32'`
# marker-gated) but is requested for parity with that recipe.
RUN --mount=type=cache,target=/home/${USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
    uv sync --locked --extra workbook-windows --group dev

# Pre-bake headless Chromium so `playwright install --with-deps` is
# unnecessary at container start (issue #101 acceptance criterion).
#
# Deliberately NO cache mount here. This step's whole purpose is to leave the
# browser in the image LAYER, and a `type=cache` mount is scratch space that
# is discarded when the step ends — the browsers would vanish from the built
# image. (The previous revision mounted the uv cache over this step, which
# cached nothing it ever wrote but at least did not eat the output.)
RUN python -m playwright install chromium

CMD ["bash"]
