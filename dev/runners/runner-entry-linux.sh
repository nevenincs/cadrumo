#!/usr/bin/env bash
# Entrypoint for the cadrumo Linux X64 container runners.
#
# Baked into the runner image at /usr/local/bin/cadrumo-runner-entry.sh (see
# the `runner` stage of the repository-root Dockerfile). That path is OUTSIDE
# /home/runner, which the cadrumo-runner-state-<n> volume mounts over, so the
# entrypoint cannot be shadowed by the volume and cannot go missing.
#
# Two earlier incarnations failed differently and both are worth remembering.
# Bind-mounted from an ephemeral temp directory: when that directory was
# cleaned up Docker recreated the bind source as an empty DIRECTORY at
# /entry.sh, exec failed, and the container died with code 127 and stayed down
# despite restart-policy=always. Copied into the state volume: it survived, but
# so did every hand-provisioning step around it, and a rebuild silently lost
# whatever nobody remembered to re-copy.
set -euo pipefail

# Tool paths, most-specific first.
#
# /usr/local/bin now carries gh and just from the IMAGE (the upstream runner
# image ships neither). gh in particular is assumed present the way it is on
# GitHub-hosted runners: the acquisition and campaign lanes invoke it directly,
# no workflow installs it, and its absence surfaces mid-lane as a
# command-not-found inside a step rather than as a missing-tool error.
#
# /home/runner/tools/bin is kept ahead of it for backward compatibility: a
# container still running on the OLD stock image keeps its volume-provisioned
# tools, so this one script drives both the pre- and post-cutover fleet.
export PATH="/home/runner/tools/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:${PATH}"

# The host docker socket is mounted in as root:root 0660, so the unprivileged
# runner user cannot reach it. The packaging smoke lanes drive nested
# containers through this socket, so open it before handing off.
if [ -S /var/run/docker.sock ]; then
  sudo chmod 666 /var/run/docker.sock || true
fi

cd /home/runner
exec ./run.sh
