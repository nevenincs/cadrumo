---
tags:
  - '#research'
  - '#runtime-manager-architecture'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:a340d0170b9f577ad237f2376cfb0acb569c2fbb399a45d0deae30a486c26d85'
related:
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-05-runtime-manager-architecture-audit]]"
---

# `runtime-manager-architecture` research: `Linux placement and native login identity`

The Linux rollout must keep native desktop-session admission while moving the runtime out of frontend-owned lifetime. The proposed user-systemd placement does not preserve the process-to-logind-session mapping used by current admission. A direct child can preserve an existing mapping, but whether packaged autostart supplies that mapping and whether manager failure leaves the runtime alive still need an interactive runner. No alternative has native acceptance.

## Findings

### A user-manager cgroup is not a logind session cgroup

In systemd v253, `sd_pidfd_get_session` resolves the pidfd to a PID, calls `sd_pid_get_session`, then verifies the held descriptor. The latter obtains the cgroup path; `cg_path_get_session` accepts its first non-slice unit only when it names a `session-*.scope`. A runtime moved beneath `user@UID.service` therefore loses this mapping even if its UID and inherited display environment stay unchanged. This is an inference from the pinned upstream implementation, not a successful desktop experiment. Sources: upstream `sd-login.c` and `cgroup-util.c` below.

The current Rust `native/manager/src/linux/login.rs` and Python `src/cadrumo/adapters/local_runtime/linux_logind_native.py` require that native mapping. Replacing it with an environment session ID would change authority. `native/manager/src/linux/placement.rs` builds scope and pipe-service commands but is deliberately not integrated into release launch.

### Existing native APIs impose a separate compatibility limit

The two pidfd sd-login functions first appear in `LIBSYSTEMD_253`; Python additionally requires `sd_bus_set_method_call_timeout` from 240 and `sd_bus_close_unref` from 241. The glibc 2.28 build floor does not settle this libsystemd API floor. Current placement also requests `--expand-environment=no`, absent from v253 `run.c`. No new supported distribution minimum is established here.

A compatibility adapter could reproduce upstream held-pidfd-to-PID lookup and final identity verification rather than treating a bare PID as authority. It would require coordinated Python/Rust review because the Python adapter expressly excludes PID/peer APIs, plus race tests and older-libsystemd runner evidence. This does not repair cgroup session loss.

### The available host cannot establish the missing desktop evidence

`dev/packaging/native/linux_manager_probe.py` provides a bounded disposable-runner probe for direct, scope, and pipe children. The recorded WSL check refused because the calling process had no native logind session; its cgroup was `/non-systemd`. The visible loginctl session was class user/type tty, not an admitted graphical session. Display environment variables were not accepted as evidence. No login registration was added to the development host.

### The smallest alternatives trade placement rather than weakening admission

Keeping mandatory user-systemd placement leaves Linux release activation blocked until a genuine runner demonstrates the existing native identity survives; upstream behavior gives no reason to assume it will. Direct inherited-session launch preserves the current identity checks when its manager already has the required native identity, but separate cgroup isolation is lost and the installed autostart lifetime must be proven. A separately authenticated native login-binding design could support user-manager placement, but would coordinate runtime admission, manager/session IPC, boot identity, logout invalidation and adoption; it is a larger authority decision with no completed design here. Naming a user scope after a session, copying an environment variable or relaxing missing-session admission is not native evidence.

2026-10-08 additional native evidence: a root-owned isolated Ubuntu 24.04.5 ARM-independent x86-64 KVM guest was provisioned from Canonical's release-20260926 cloud image (SHA256 6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2; SHA256SUMS signature verified with the packaged ubuntu-cloudimage-keyring). GNOME/X11 autologin produced native logind session 1, user runner/UID 1000, Remote=no, Class=user, Active=yes, State=active, LockedHint=no. An ordinary XDG autostart process called native sd_pid_get_session(0) and received -61/ENODATA, with cgroup 0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome-cadrumo\\x2drunner\\x2devidence-23658.scope. Thus a real local graphical session exists while its ordinary autostart process lacks the session mapping required by current admission. Inference: merely launching a direct child from this default GNOME autostart placement does not restore that mapping. This does not prove all desktop profiles behave identically or establish application lifecycle acceptance.

Runner artifacts and the source of the read-only native probe are retained at /home/hello/.local/share/cadrumo-runners/noble-20261008 in WSL and build/windows-installers-x64/verification/linux_runner_seed.py. No CADRUMO product was installed. After the user emphasized that their supplied Windows and Mac machines are non-disposable, root powered down this temporary guest cleanly and retained its disk. Existing real hosts are reserved for isolated builds and read-only verification; no reset or product installation was performed.

## Sources

- https://raw.githubusercontent.com/systemd/systemd/v253/src/libsystemd/sd-login/sd-login.c
- https://raw.githubusercontent.com/systemd/systemd/v253/src/basic/cgroup-util.c
- https://raw.githubusercontent.com/systemd/systemd/v253/src/libsystemd/libsystemd.sym
- https://raw.githubusercontent.com/systemd/systemd/v253/src/run/run.c
- `native/manager/src/linux/login.rs`
- `native/manager/src/linux/placement.rs`
- `src/cadrumo/adapters/local_runtime/linux_logind_native.py`
- `src/cadrumo/adapters/local_runtime/linux_login.py`
- `dev/packaging/native/linux_manager_probe.py`
