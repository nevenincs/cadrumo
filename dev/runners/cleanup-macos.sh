#!/usr/bin/env bash
# runner disk-hygiene hook - macOS self-hosted runner.
#
# Wired via ACTIONS_RUNNER_HOOK_JOB_COMPLETED in the runner root .env, so it
# fires after EVERY job (success or failure). It MUST stay fast (<30s typical)
# and MUST always exit 0 - a cleanup failure must never redden a green build.
#
# What it does, in order: purge stale _work/_temp entries; prune per-run lane
# roots (cadrumo-homebrew* / cadrumo-scoop* / cadrumo-claude-* / oracle-emit-work) older than 24h;
# purge var/ residue in the reused checkout (evidence dirs <7d exempt); bound
# the uv / pip / npm speed caches; macOS residue - uninstall + untap leftover
# cadrumo-smoke Homebrew test formulas/taps and brew cleanup; clear stale /tmp
# lane dirs; one audit summary line.
#
# It NEVER touches: tracked files, runner binaries/credentials (.runner /
# .credentials), the reused checkout's .venv, the operator's real Homebrew
# packages (only cadrumo-smoke* test formulas/taps), or real financial data.
#
# BSD userland: stat -f %m, du -k, find -mtime (minute granularity via -mmin
# is GNU-only, so age math uses stat + epoch).

set +e

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
BREW_PRUNE_DAYS=7
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
    # This replaces a hardcoded "${HOME}/actions-runner/_work". The macOS runner
    # roots now live under ~/action-runners/<name>/, so that constant named a
    # path that no longer exists — and because this hook must never redden a
    # build it always exits 0, so the miss would have been invisible: hygiene
    # simply stops and nothing says so. Deriving from the script's own location
    # survives any future relocation.
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

# --- helpers (BSD) ---------------------------------------------------------
mtime_epoch() { stat -f %m "$1" 2>/dev/null || echo 0; }
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
        local age_min=$(( ( $(date +%s) - $(mtime_epoch "$marker") ) / 60 ))
        [[ $age_min -lt $HEAVY_THROTTLE_MIN ]] && return 1
    fi
    date -u +%FT%TZ > "$marker" 2>/dev/null
    return 0
}

# Runner-managed state and repository checkouts are never lane roots, whatever
# the tokens say. actions/checkout materialises _work/<repo>/<repo>, so a
# checkout root is a directory containing a same-named child — that is the
# structural tell, and it holds for any repo without hardcoding a name.
#
# This matters because matching is SUBSTRING: a lane token broad enough to
# cover the repo's own temp dirs ("vaultspec-", which the dashboard workflows
# use for ${RUNNER_TEMP}/vaultspec-*) also matches the "vaultspec-dashboard"
# checkout sitting in the same WORK_ROOT, and would delete the entire working
# copy on the first sweep past 24h.
is_protected_root() {
    case "$2" in
        _actions|_tool|_temp|_diag|_PipelineMapping|.hygiene) return 0 ;;
    esac
    [[ -d "$1/$2" ]] && return 0
    return 1
}

purge_stale_lane_dirs() {
    local root="$1"
    [[ -d "$root" ]] || return 0
    local entry base age_min keep_min match tok
    for entry in "$root"/*; do
        [[ -e "$entry" ]] || continue
        base="$(basename "$entry")"
        is_protected_root "$entry" "$base" && continue
        match=0
        for tok in "${LANE_GLOBS[@]}"; do [[ "$base" == *"$tok"* ]] && match=1; done
        [[ "$base" == release-cohort* || "$base" == *.tar.gz ]] && match=1
        [[ $match -eq 1 ]] || continue
        age_min=$(( ( $(date +%s) - $(mtime_epoch "$entry") ) / 60 ))
        if [[ "$base" == "$EVIDENCE_EXEMPT"* ]]; then keep_min=$EVIDENCE_KEEP_MIN; else keep_min=$LANE_MAX_AGE_MIN; fi
        [[ $age_min -ge $keep_min ]] && remove_path "$entry"
    done
}

cap_cache() {
    local path="$1" cap_gb="$2" tag="$3"
    [[ -d "$path" ]] || return 0
    should_run_heavy "$tag" || return 0
    local cap_kb=$((cap_gb * 1024 * 1024))
    local total; total=$(dir_kb "$path")
    [[ $total -le $cap_kb ]] && return 0
    local entry kb
    # oldest-first via BSD stat; portable loop over immediate children.
    while IFS= read -r entry; do
        [[ $total -le $cap_kb ]] && break
        [[ -e "$entry" ]] || continue
        kb=$(dir_kb "$entry")
        remove_path "$entry"
        total=$((total - kb))
    done < <(for e in "$path"/*; do [[ -e "$e" ]] && echo "$(mtime_epoch "$e") $e"; done | sort -n | cut -d' ' -f2-)
    NOTES="${NOTES}cap:${tag},"
}

# --- (a) stale _work/_temp beyond the current job --------------------------
if [[ -d "$TEMP_DIR" ]]; then
    find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -mtime +1 2>/dev/null | while IFS= read -r p; do
        rm -rf "$p" 2>/dev/null
    done
fi

# --- (b) per-run lane roots older than 24h ---------------------------------
purge_stale_lane_dirs "$WORK_ROOT"
purge_stale_lane_dirs "$TEMP_DIR"
for repo_ws in "$WORK_ROOT"/*/; do
    var="${repo_ws%/}/$(basename "${repo_ws%/}")/var"
    [[ -d "$var" ]] && purge_stale_lane_dirs "$var"
done

# --- (c) bound the persistent speed caches ---------------------------------
if command -v uv >/dev/null 2>&1; then uv cache prune >/dev/null 2>&1; fi
UV_CACHE="${UV_CACHE_DIR:-$HOME/Library/Caches/uv}"
[[ -d "$UV_CACHE" ]] || UV_CACHE="$HOME/.cache/uv"
cap_cache "$UV_CACHE" "$UV_CAP_GB" uv
cap_cache "$HOME/Library/Caches/pip" "$PIP_CAP_GB" pip
cap_cache "$HOME/.npm" "$NPM_CAP_GB" npm

# --- (e) macOS Homebrew residue: only cadrumo-smoke test formulas/taps ------
if command -v brew >/dev/null 2>&1 && should_run_heavy brew; then
    # uninstall leftover test formulas whose name matches cadrumo-smoke*.
    for f in $(brew list --formula 2>/dev/null | grep -iE '^cadrumo(-smoke)?' 2>/dev/null); do
        brew uninstall --force --ignore-dependencies "$f" >/dev/null 2>&1 && NOTES="${NOTES}brew-rm:${f},"
    done
    # untap the smoke test taps (never the operator's real taps).
    for t in $(brew tap 2>/dev/null | grep -iE 'cadrumo.*smoke|.*cadrumo-smoke' 2>/dev/null); do
        brew untap "$t" >/dev/null 2>&1 && NOTES="${NOTES}untap:${t},"
    done
    brew cleanup -s --prune="$BREW_PRUNE_DAYS" >/dev/null 2>&1
    NOTES="${NOTES}brew-cleanup,"
fi

# --- stale /tmp lane dirs --------------------------------------------------
purge_stale_lane_dirs "/tmp"

# --- (f) audit summary + log rotation --------------------------------------
if [[ -f "$LOG_FILE" ]]; then
    sz=$(stat -f %z "$LOG_FILE" 2>/dev/null || echo 0)
    [[ $sz -gt $LOG_MAX_BYTES ]] && mv -f "$LOG_FILE" "$LOG_FILE.1" 2>/dev/null
fi
freed_mb=$(awk "BEGIN{printf \"%.1f\", $FREED_KB/1024}")
notes="${NOTES:-none}"
printf '%s job=%s run=%s freed=%sMB pruned=%s\n' \
    "$(date -u +%FT%TZ)" "${GITHUB_JOB:--}" "${GITHUB_RUN_ID:--}" "$freed_mb" "${notes%,}" \
    >> "$LOG_FILE" 2>/dev/null

exit 0
