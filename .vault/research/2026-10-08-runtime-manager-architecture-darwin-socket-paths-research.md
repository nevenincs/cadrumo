---
tags:
  - '#research'
  - '#runtime-manager-architecture'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:ffd8b772eff2925f794e95f92d229f77d829e41e9dee50ff1e359e326ce182c6'
related:
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

# `runtime-manager-architecture` research: `Darwin installed socket path limits`

The supplied Mac's normal installed storage roots cannot host the current runtime socket filename: the stable path is 104 UTF-8 bytes and preview is 112, while the endpoint refuses lengths at or above 104. This blocks installed runtime and manager integration independently of signing. Compact names mitigate particular homes; a robust solution needs either a reviewed canonical transport-directory exception or an authority-preserving mechanism that avoids the full pathname limit. No namespace change is selected here.

## Findings

### The existing default already exceeds the runtime's bound

Read-only SSH confirmed HOME=/Users/gergely.wootsch. The declared stable socket directory is /Users/gergely.wootsch/Library/Application Support/cadrumo/runtime (66 bytes), and preview adds eight bytes. The slash, 32 hexadecimal identity characters and .sock suffix add 38 bytes. `src/cadrumo/adapters/local_runtime/posix_endpoint.py:189` selects the typed runtime member and `:201` refuses both resulting paths before bind. `native/manager/src/macos/ipc.rs:26` uses an even longer owner/session-qualified basename. No product directories were created and no installed application was launched to establish these lengths.

### The current managed contract permits no shorter ambient override

`src/cadrumo/core/storage_taxonomy_locations.py:154` declares RUNTIME_SOCKETS as runtime beneath the root. The accepted canonical-environment ADR, Installed default root and Process environment sections, keeps members beneath that root and makes strict children pass no operator overrides. `native/manager/src/supervision/environment.rs:24` admits only the installed default; its runtime_environment uses that strict profile. The declared CADRUMO_RUNTIME_SOCKET_DIR operator override is therefore not a managed-install remedy. Any different default transport namespace must remain owned by the canonical declaration and generated projection and must reconcile those existing commitments.

### Public descriptor-relative socket calls and descriptor aliases do not supply a remedy

The public Apple socket header and supplied SDK expose bind/connect, not bindat/connectat. The Unix socket header declares sun_path[104]. An isolated actual-Mac probe connected an ordinary socket and verified that LOCAL_PEERPID and the audit-token PID matched the connecting process. A held-directory /dev/fd/<fd>/<leaf> alias failed stat and connect with ENOENT; binding through that alias for a 152-byte canonical path also failed ENOENT. CWD stayed unchanged and the synthetic temporary directory was cleaned normally. Evidence: `build/macos-process-typecheck/fd_alias_probe.py` and `fd-alias-probe.log`.

### Private thread-directory APIs and helper processes are not transparent substitutes

Apple declares pthread_fchdir_np in its private pthread header, absent from the supplied public SDK header; it is not a supported public-API foundation. Process-global chdir is unsuitable for concurrent runtime/manager code. A dedicated helper can use public fchdir or the SDK's posix_spawn_file_actions_addfchdir_np, but Darwin records socket peer identity at connect/listen. Relaying a connected descriptor does not establish that existing PID, image and audit-token admission would still identify the intended product process. No helper-authority design or positive acceptance was established.

### Compact names preserve identity strength but only extend the pathname budget

Encoding the existing 128-bit runtime filename identity as 22 base64url characters instead of 32 hexadecimal characters would produce 94-byte stable and 102-byte preview paths on this host, with no loss of those identity bits. It does not support arbitrary longer home directories and requires consistent endpoint naming across consumers. It is a possible bounded mitigation, not a complete platform-default remedy.

### The public user cache directory is a concrete alternative requiring a canonical exception

Apple documents the user cache directory as owner-only and not automatically cleaned except at safe boot. Unlike its user temporary-directory query, the cache query has no TMPDIR fallback in the inspected Libc implementation. On the supplied Mac, SDK constant _CS_DARWIN_USER_CACHE_DIR=65538 returned /var/folders/37/kcxbsyx14rs1n3jlnyb6j07c0000gn/C/. Its canonical /private/var path is 56 bytes, a real 0700 directory owned by the current UID 501; canonical ancestors were checked without symlinks. A cadrumo subdirectory plus the current runtime filename would be 102 bytes, but cadrumo-preview would be 110. Thus selecting the OS base alone does not settle compact channel/owner names, cleanup, custody or cross-version discovery. Evidence: `build/macos-process-typecheck/probe-user-cache.py`, `user-cache-probe-command.json` and `user-cache-probe-native.log`. No product subdirectory was created.

The user temporary-directory query is weaker evidence: Apple's implementation can fall back to TMPDIR and then P_tmpdir if its native directory helper fails. Its output alone cannot prove environment-independent canonical authority. The generic user directory is documented 0755 and is unsuitable by itself. The cache option deserves further design work, but the accepted single-root and unchanged-member rules have not been amended, and no prototype establishes complete endpoint behavior there.

## Sources

- `src/cadrumo/core/storage_taxonomy_locations.py:154`
- `src/cadrumo/core/storage_environment.py:182`
- `src/cadrumo/adapters/local_runtime/posix_endpoint.py:189`
- `native/manager/src/supervision/environment.rs:24`
- `native/manager/src/macos/ipc.rs:26`
- `build/macos-process-typecheck/fd_alias_probe.py` and `fd-alias-probe.log`
- `build/macos-process-typecheck/user-cache-probe-command.json` and `user-cache-probe-native.log`
- https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/socket.h
- https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/un.h
- https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/uipc_usrreq.c
- https://raw.githubusercontent.com/apple-oss-distributions/Libc/main/gen/confstr.3
- https://raw.githubusercontent.com/apple-oss-distributions/Libc/main/gen/confstr.c
- https://raw.githubusercontent.com/apple-oss-distributions/libpthread/main/private/pthread/private.h
- https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/chdir.2.html
