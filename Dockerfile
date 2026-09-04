# syntax=docker/dockerfile:1

# Every Cadrumo container image, declared in one file.
#
#   --target dev      Reproducible headless-Playwright-capable development
#                     image. Used by `.devcontainer/devcontainer.json`
#                     ("Reopen in Container") and `just devcontainer-build`.
#   --target runner   Self-hosted GitHub Actions runner image for the Linux
#                     fleet. Built by `just runner-image-build`.
#
# ── How the three container surfaces relate ──────────────────────────────
# 1. The RUNNER containers execute every workflow job labelled
#    `[self-hosted, Linux, X64]`. They mount the HOST docker socket.
# 2. Through that socket, the packaging smoke lanes
#    (`dev/packaging/smoke_docker.py`) start NESTED clean-Linux containers on
#    the host daemon to prove a built wheel installs from scratch. Those
#    nested containers use `PYTHON_BASE_IMAGE` below — the same base as the
#    dev image, resolved by `dev/packaging/_base_image.py` so the string is
#    written once.
# 3. The DEV image is not used by CI at all; it is the contributor
#    environment. It shares the Python base with (2), not with (1).
#
# The runner keeps a SEPARATE base by necessity, not by drift: its upstream
# image carries the GitHub Actions runner agent itself (`run.sh`,
# `config.sh`, `Runner.Listener`) built against Ubuntu. There is no version
# of that agent on the Python base, so the two families are declared
# separately here and each exactly once.
#
# ── One base, declared once ──────────────────────────────────────────────
# `PYTHON_BASE_IMAGE` is the single declaration point for the Linux base
# every Cadrumo container shares. `dev/packaging/smoke_docker.py` (the
# clean-Linux wheel-install proof) defaults to the same string, so the dev
# image and the packaging proof cannot drift onto different distributions.
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

# Single declaration point for the self-hosted runner family. Pinned to a
# release tag rather than `:latest`: a runner image that moves under the fleet
# is how capability drift between the two supposedly-identical Linux runners
# appears, and that drift reproduces only half the time because a job lands on
# whichever runner is free.
ARG RUNNER_BASE_IMAGE=ghcr.io/actions/actions-runner:2.335.1
ARG GH_VERSION=2.97.0
ARG JUST_VERSION=1.58.0

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
    uv venv --python 3.13 .venv \
    && uv pip install --python .venv/bin/python --editable ".[workbook-windows]" --group dev

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


# ── Self-hosted GitHub Actions runner image ──────────────────────────────
# Replaces the hand-provisioned stock container documented in
# dev/runners/README.md. Everything that made those runners *these* runners
# lived outside the image — copied into the `cadrumo-runner-state-<n>` named
# volume by hand — so a rebuild silently lost tools and the two supposedly
# identical Linux runners could disagree. Each such gap cost a full smoke run
# to rediscover and reproduced only half the time, because a job lands on
# whichever runner is free.
#
# CRITICAL PLACEMENT RULE: the state volume mounts over `/home/runner`, so
# ANYTHING this stage writes under `/home/runner` is shadowed at runtime and
# effectively does not exist. Every tool below is therefore installed OUTSIDE
# that path (`/usr/local/bin`, `/home/linuxbrew`), which is also why they now
# survive a container rebuild without living in the volume.
FROM ${RUNNER_BASE_IMAGE} AS runner

ARG GH_VERSION
ARG JUST_VERSION
ARG TARGETARCH

USER root

# build-essential/procps/file/git: Homebrew's declared prerequisites.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    procps \
    file \
    git \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# gh: NOT shipped by the upstream runner image, and assumed present the way it
# is on GitHub-hosted runners. The acquisition and campaign lanes that run on
# this fleet invoke it directly and no workflow installs it, so its absence
# surfaces mid-lane as a command-not-found in a step that never names the
# missing tool. Ubuntu 24.04 ships 2.45; pin the current upstream release
# instead so the fleet matches GitHub-hosted expectations.
RUN arch="${TARGETARCH:-amd64}" \
    && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${arch}.tar.gz" \
    | tar -xz -C /tmp \
    && install -m 0755 "/tmp/gh_${GH_VERSION}_linux_${arch}/bin/gh" /usr/local/bin/gh \
    && rm -rf "/tmp/gh_${GH_VERSION}_linux_${arch}" \
    && gh --version

# just: workflows install it themselves through an action, but baking it in
# removes one more "assumed present" from the fleet and makes the container
# usable for the same recipes contributors run.
RUN arch="${TARGETARCH:-amd64}" \
    && case "${arch}" in \
    amd64) target="x86_64-unknown-linux-musl" ;; \
    arm64) target="aarch64-unknown-linux-musl" ;; \
    *) echo "unsupported TARGETARCH: ${arch}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-${target}.tar.gz" \
    | tar -xz -C /usr/local/bin just \
    && chmod 0755 /usr/local/bin/just \
    && just --version

# Homebrew at the CANONICAL prefix. The acquisition lane runs
# `/home/linuxbrew/.linuxbrew/bin/brew` and fails its first step
# (`test -x "$BREW_PATH"`) without it.
#
# Do NOT relocate this tree and symlink `/home/linuxbrew` at it. Homebrew
# computes relative link traversals against the RESOLVED path, so through a
# symlink the `..` walk climbs too far and `brew link` dies with
# "Permission denied @ dir_s_mkdir - /linuxbrew" only at the very END of an
# install, after building every resource. Installing it into the IMAGE at the
# real path is what finally makes it survive a container rebuild — the one
# dependency the volume-based scheme could never keep.
#
# Full history, not `--depth=1`: a shallow clone leaves `brew --version`
# reporting "shallow or no git repository" and Homebrew refuses to work.
RUN mkdir -p /home/linuxbrew \
    && chown runner:runner /home/linuxbrew \
    && git clone https://github.com/Homebrew/brew /home/linuxbrew/.linuxbrew/Homebrew \
    && mkdir -p /home/linuxbrew/.linuxbrew/bin \
    && ln -sfn ../Homebrew/bin/brew /home/linuxbrew/.linuxbrew/bin/brew \
    && chown -R runner:runner /home/linuxbrew \
    && test -z "$(readlink -f /home/linuxbrew/.linuxbrew/bin/brew | grep -v '^/home/linuxbrew/')" \
    && su runner -c '/home/linuxbrew/.linuxbrew/bin/brew --version'

# Pre-warm Homebrew's first-use state, and keep it OUT of /home/runner.
#
# Deliberately NOT `brew update --force`, which the old by-hand sequence ended
# with: modern Homebrew resolves core formulae through the JSON API, so a fresh
# clone taps and installs fine and cloning homebrew-core would cost roughly a
# gigabyte for nothing. Measured on this image: `brew tap` self-provisions
# portable-ruby and fetches the API data, and `brew info --json=v2` on a core
# formula resolves with no core tap present at all.
#
# What DOES need doing is where that state lands. `HOMEBREW_CACHE` defaults to
# `~/.cache/Homebrew` — i.e. inside `/home/runner`, which the state volume
# mounts over — so every runner pays for and stores its own copy. Relocating it
# under /home/linuxbrew puts it in a shared image layer instead: one copy for
# the whole fleet rather than one per volume, which is the right trade on
# space-constrained hosts. Pre-warming here also means the first real job does
# not stop to download a Ruby.
ENV HOMEBREW_NO_ANALYTICS=1 \
    HOMEBREW_CACHE=/home/linuxbrew/.cache
RUN install -d -o runner -g runner /home/linuxbrew/.cache \
    && su runner -c 'HOMEBREW_NO_ANALYTICS=1 HOMEBREW_CACHE=/home/linuxbrew/.cache \
    /home/linuxbrew/.linuxbrew/bin/brew info --json=v2 jq > /dev/null' \
    && test -d /home/linuxbrew/.linuxbrew/Homebrew/Library/Homebrew/vendor/portable-ruby

# The entrypoint lives in the IMAGE, at a path the state volume cannot
# shadow. The previous incarnation was bind-mounted from an ephemeral temp
# directory; when that directory was cleaned up Docker recreated the bind
# source as an empty DIRECTORY, exec failed, and the container exited 127 and
# stayed down even with `--restart always`.
COPY dev/runners/runner-entry-linux.sh /usr/local/bin/cadrumo-runner-entry.sh
RUN chmod 0755 /usr/local/bin/cadrumo-runner-entry.sh

# The disk-hygiene hook, baked for the same reason as the entrypoint: it must
# live OUTSIDE /home/runner, which the runner state volume mounts over, or it
# disappears the moment the volume is attached.
#
# These containers mount the host docker socket so the packaging smoke lanes can
# start nested containers on the host daemon. Those nested runs leave anonymous
# volumes and dangling images behind ON THE HOST, and nothing in the job
# lifecycle reclaims them - only ACTIONS_RUNNER_HOOK_JOB_COMPLETED fires when a
# job fails, cancels or times out.
#
# dev/runners/README.md already names cleanup-linux.sh as this runner's hygiene
# script. It was never baked into the image, so the Linux runners have run
# without it: of the seven runner installs on the shared build host, exactly one
# has a hygiene hook, and it is the Windows one.
COPY dev/runners/cleanup-linux.sh /usr/local/bin/cadrumo-cleanup-linux.sh
RUN chmod 0755 /usr/local/bin/cadrumo-cleanup-linux.sh

USER runner
WORKDIR /home/runner

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/cadrumo-runner-entry.sh"]
