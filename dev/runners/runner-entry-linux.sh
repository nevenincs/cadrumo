#!/usr/bin/env bash
# Entrypoint for the cadrumo Linux X64 container runners.
#
# This script lives INSIDE the cadrumo-runner-state-<n> named volume, beside the
# runner's own config and credentials, so it shares the runner's lifetime. The
# previous incarnation was bind-mounted from an ephemeral temp directory; when
# that directory was removed Docker recreated the bind source as an empty
# DIRECTORY at /entry.sh, exec failed, and the container died with code 127 and
# stayed down despite restart-policy=always.
set -euo pipefail

# Tools the workflows need that the base runner image does NOT ship -- notably
# the gh CLI, which dev.release.version_identity shells out to for the tag and
# release namespace check, and which several workflow steps call directly. They
# live in the volume rather than the container's writable layer so that
# recreating the container from the base image does not silently lose them:
# that is exactly how the gh dependency went missing once already, surfacing as
# "REFUSED: forge check needs the gh CLI on PATH" mid-release.
export PATH="/home/runner/tools/bin:${PATH}"

# The host docker socket is mounted in as root:root 0660, so the unprivileged
# runner user cannot reach it. The packaging smoke lanes drive nested
# containers through this socket, so open it before handing off.
if [ -S /var/run/docker.sock ]; then
  sudo chmod 666 /var/run/docker.sock || true
fi

cd /home/runner
exec ./run.sh
