#!/usr/bin/env bash
# runner disk-hygiene hook - Linux self-hosted runners (the two docker
# containers cadrumo-runner-linux / cadrumo-runner-linux-2).
#
# Wired via ACTIONS_RUNNER_HOOK_JOB_COMPLETED in the runner root .env, so it
# fires after EVERY job (success or failure). It MUST stay fast (<30s typical)
# and MUST always exit 0 - a cleanup failure must never redden a green build.
#
# What it does, in order: purge stale _work/_temp entries; prune per-run lane
# roots (cadrumo-homebrew* / cadrumo-scoop* / cadrumo-claude-* / oracle-emit-work) older than 24h;
# purge var/ residue in the reused checkout (evidence dirs <7d exempt); bound
# the uv / pip / npm speed caches; docker hygiene against the host daemon the
# smoke's nested containers share (dangling images, stopped containers,
# unreferenced volumes, builder cache) - NEVER the runner containers or the
# named cadrumo-runner-state* volumes; one audit summary line.
#
# It NEVER touches: tracked files, runner binaries/credentials (.runner /
# .credentials), the reused checkout's .venv, named docker volumes, or real
# financial data.

set +e   # never abort the hook; each step guards itself.

# --- constants -------------------------------------------------------------
# Lane roots section (b) is allowed to reap. These default to cadrumo's own
# lane names, which is correct on a cadrumo runner and silently inert on any
# other: this same hook is deployed to the vaultspec-* runners, where nothing
# has ever matched and the audit line has read `freed=0.0MB` on every run
# since the hook was installed. A runner serving another repository names its
# own lanes via RUNNER_HYGIENE_LANE_GLOBS (space-separated) in its .env.
if [[ -n "${RUNNER_HYGIENE_LANE_GLOBS:-}" ]]; then
    read -r -a LANE_GLOBS <<< "$RUNNER_HYGIENE_LANE_GLOBS"
else
    LANE_GLOBS=(cadrumo-homebrew cadrumo-scoop cadrumo-claude oracle-emit-work)
fi
LANE_MAX_AGE_MIN=$((24 * 60))
EVIDENCE_EXEMPT="distribution-install-readiness"
EVIDENCE_KEEP_MIN=$((7 * 24 * 60))
UV_CAP_GB=5
PIP_CAP_GB=3
NPM_CAP_GB=3
HEAVY_THROTTLE_MIN=$((6 * 60))
DOCKER_BUILDER_KEEP=5GB
LOG_MAX_BYTES=$((2 * 1024 * 1024))

# --- path derivation -------------------------------------------------------
if [[ -n "${RUNNER_TEMP:-}" ]]; then
    WORK_ROOT="$(dirname "$RUNNER_TEMP")"
elif [[ -n "${RUNNER_WORKSPACE:-}" ]]; then
    WORK_ROOT="$(dirname "$(dirname "$RUNNER_WORKSPACE")")"
else
    # Invoked outside a job, so RUNNER_TEMP/RUNNER_WORKSPACE are unset. The hook
    # is copied to the runner root, so its OWN directory is that root.
    #
    # This replaces a hardcoded "${HOME}/actions-runner/_work", which was never
    # right for these container runners: their runner root IS ${HOME}
    # (/home/runner), so the work root is ${HOME}/_work — the old constant
    # pointed one level too deep at a path that has never existed here. It went
    # unnoticed because this hook must never redden a build, so it always exits
    # 0 and a wrong root reports nothing at all.
    _self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -d "${_self_dir}/_work" ]]; then
        WORK_ROOT="${_self_dir}/_work"
    else
        # Nothing to clean from here (e.g. run out of a repository checkout).
        exit 0
    fi
fi
TEMP_DIR="${RUNNER_TEMP:-$WORK_ROOT/_temp}"
LOG_FILE="$WORK_ROOT/runner-hygiene.log"
STATE_DIR="$WORK_ROOT/.hygiene"
mkdir -p "$STATE_DIR" 2>/dev/null

FREED_KB=0
NOTES=""

# --- helpers ---------------------------------------------------------------
dir_kb() { [[ -e "$1" ]] && du -sk "$1" 2>/dev/null | awk '{print $1}' || echo 0; }

remove_path() {
    [[ -e "$1" ]] || return 0
    local kb; kb=$(dir_kb "$1")
    if rm -rf "$1" 2>/dev/null; then
        FREED_KB=$((FREED_KB + kb))
    else
        NOTES="${NOTES}skip-locked,"
    fi
}

should_run_heavy() {
    local marker="$STATE_DIR/$1.stamp"
    if [[ -f "$marker" ]]; then
        local age_min=$(( ( $(date +%s) - $(stat -c %Y "$marker" 2>/dev/null || echo 0) ) / 60 ))
        [[ $age_min -lt $HEAVY_THROTTLE_MIN ]] && return 1
    fi
    date -u +%FT%TZ > "$marker" 2>/dev/null
    return 0
}

# Purge immediate children of $1 whose name contains any lane token and whose
# mtime is older than $LANE_MAX_AGE_MIN. Top-level mtime only - cheap stat.
purge_stale_lane_dirs() {
    local root="$1"
    [[ -d "$root" ]] || return 0
    local entry base age_min keep_min
    for entry in "$root"/*; do
        [[ -e "$entry" ]] || continue
        base="$(basename "$entry")"
        local match=0 tok
        for tok in "${LANE_GLOBS[@]}"; do [[ "$base" == *"$tok"* ]] && match=1; done
        [[ "$base" == release-cohort* || "$base" == *.tar.gz ]] && match=1
        [[ $match -eq 1 ]] || continue
        age_min=$(( ( $(date +%s) - $(stat -c %Y "$entry" 2>/dev/null || echo 0) ) / 60 ))
        if [[ "$base" == "$EVIDENCE_EXEMPT" || "$base" == "$EVIDENCE_EXEMPT"* ]]; then
            keep_min=$EVIDENCE_KEEP_MIN
        else
            keep_min=$LANE_MAX_AGE_MIN
        fi
        [[ $age_min -ge $keep_min ]] && remove_path "$entry"
    done
}

# Bound a cache dir to $2 GB by evicting oldest immediate children until under.
cap_cache() {
    local path="$1" cap_gb="$2" tag="$3"
    [[ -d "$path" ]] || return 0
    should_run_heavy "$tag" || return 0
    local cap_kb=$((cap_gb * 1024 * 1024))
    local total; total=$(dir_kb "$path")
    [[ $total -le $cap_kb ]] && return 0
    # oldest-first: sort children by mtime, evict until under the cap.
    local entry
    while IFS= read -r entry; do
        [[ $total -le $cap_kb ]] && break
        [[ -e "$entry" ]] || continue
        local kb; kb=$(dir_kb "$entry")
        remove_path "$entry"
        total=$((total - kb))
    done < <(find "$path" -mindepth 1 -maxdepth 1 -printf '%T@ %p\n' 2>/dev/null | sort -n | cut -d' ' -f2-)
    NOTES="${NOTES}cap:${tag},"
}

# --- (a) stale _work/_temp beyond the current job --------------------------
if [[ -d "$TEMP_DIR" ]]; then
    find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -mmin +"$LANE_MAX_AGE_MIN" 2>/dev/null | while IFS= read -r p; do
        rm -rf "$p" 2>/dev/null
    done
fi

# --- (b) per-run lane roots older than 24h ---------------------------------
purge_stale_lane_dirs "$WORK_ROOT"
purge_stale_lane_dirs "$TEMP_DIR"
# var/ residue inside the reused checkout (var/ is gitignored)
for repo_ws in "$WORK_ROOT"/*/; do
    var="${repo_ws%/}/$(basename "${repo_ws%/}")/var"
    [[ -d "$var" ]] && purge_stale_lane_dirs "$var"
done

# --- (c) bound the persistent speed caches ---------------------------------
if command -v uv >/dev/null 2>&1; then uv cache prune >/dev/null 2>&1; fi
UV_CACHE="${UV_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/uv}"
cap_cache "$UV_CACHE" "$UV_CAP_GB" uv
cap_cache "${HOME}/.cache/pip" "$PIP_CAP_GB" pip
cap_cache "${HOME}/.npm" "$NPM_CAP_GB" npm

# --- (d) docker hygiene against the shared host daemon ---------------------
# The smoke spawns nested containers via the mounted host socket, stranding
# anonymous volumes / dangling images on the host daemon.
#
# This used to be four blanket prunes, justified by "the running runner
# containers and the named cadrumo-runner-state* volumes are never
# candidates". That reasoning holds only while the sibling runners are
# RUNNING. On the battery-gated MacBook host they are NOT: the power gate
# stops every runner container whenever the machine is unplugged, so a job
# finishing near that transition would meet `container prune -f` and delete
# the sibling runner outright — and the `volume prune -f` on the next line
# would then reap its now-unreferenced state volume, destroying the runner's
# registration and every build cache with it.
#
# So: targeted removal, never a blanket prune. Skip anything named like a
# fleet runner, and reap only ANONYMOUS volumes (a 64-hex name is Docker's
# generated id, so a named state volume can never match).
if command -v docker >/dev/null 2>&1 && should_run_heavy docker; then
    if docker info >/dev/null 2>&1; then
        for _cid in $(docker ps -aq --filter status=exited --filter status=dead 2>/dev/null); do
            _cname="$(docker inspect -f '{{.Name}}' "$_cid" 2>/dev/null)"
            case "${_cname#/}" in *runner*) continue ;; esac
            docker rm -f "$_cid" >/dev/null 2>&1
        done
        docker image prune -f >/dev/null 2>&1          # dangling only (never -a)
        for _vol in $(docker volume ls -q --filter dangling=true 2>/dev/null); do
            [[ "$_vol" =~ ^[0-9a-f]{64}$ ]] || continue
            docker volume rm "$_vol" >/dev/null 2>&1
        done
        docker builder prune -f --keep-storage "$DOCKER_BUILDER_KEEP" >/dev/null 2>&1
        NOTES="${NOTES}docker,"
    fi
fi

# --- (f) audit summary + log rotation --------------------------------------
if [[ -f "$LOG_FILE" ]]; then
    sz=$(stat -c %s "$LOG_FILE" 2>/dev/null || echo 0)
    [[ $sz -gt $LOG_MAX_BYTES ]] && mv -f "$LOG_FILE" "$LOG_FILE.1" 2>/dev/null
fi
freed_mb=$(awk "BEGIN{printf \"%.1f\", $FREED_KB/1024}")
notes="${NOTES:-none}"
printf '%s job=%s run=%s freed=%sMB pruned=%s\n' \
    "$(date -u +%FT%TZ)" "${GITHUB_JOB:--}" "${GITHUB_RUN_ID:--}" "$freed_mb" "${notes%,}" \
    >> "$LOG_FILE" 2>/dev/null

exit 0
