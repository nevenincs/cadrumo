---
tags:
  - '#adr'
  - '#canonical-environment'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:2337591d34ae8410fd35747804624a520e203b6a4684c9c7b17af109c31ae091'
related:
  - "[[2026-10-08-runtime-manager-architecture-darwin-socket-paths-research]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
  - "[[2026-07-13-data-output-standardization-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `canonical-environment` adr: `Darwin transient transport namespace` | (**status:** `accepted`)

## Problem Statement

The installed Darwin runtime cannot bind its default socket on the supplied Mac because the canonical data-root path exceeds the native Unix socket limit. The manager filename is longer still. The measured failure and rejected alternatives are recorded in 2026-10-08-runtime-manager-architecture-darwin-socket-paths-research. Signing does not affect this failure.

## Considerations

The operator requested implementation and builds of all installer/manager work except signing certificates and authorized dependency installation. Both supplied machines are non-disposable. This decision concerns transient transport endpoints only; no application data, installed product or login registration is moved by deciding or implementing it.

The accepted canonical-environment and storage-management decisions remain the authority for location declarations, strict child environments, ownership and conformance. Their single-root/member-preservation wording needs a narrow exception for Darwin transport. The pre-release regime forbids compatibility readers and migrations.

## Considered options

- Keep the full data-root socket path: rejected because both measured installed channels fail before bind.
- Shorten only filenames: preserves identity strength but merely shifts the username/path ceiling; insufficient as the default-platform remedy.
- Public descriptor-relative calls or /dev/fd aliases: no public bindat/connectat was found and native alias probes failed.
- Thread-local private APIs, global chdir, or a helper process: rejected as a public production foundation; helper socket identity is not transparently the parent's identity.
- OS temporary-directory lookup: rejected because the inspected implementation can fall back to ambient TMPDIR and its cleanup differs from persistent namespace-lock requirements.
- Public per-user cache base, one compact product-family directory, unchanged peer checks: chosen. It avoids home-directory length without moving persistent application data or changing which process connects.

## Constraints

Only the default socket location in installed Darwin mode gains an external transient anchor for RUNTIME_SOCKETS. It holds runtime, worker and manager socket leaves and their namespace-ownership lock inodes. Application data, start claims, boot and installation records, preferences, logs, credentials and taxpayer information remain at their existing locations. Development roots remain root-relative, and explicit synthetic or operator-selected socket namespaces keep their isolation; the existing operator socket-directory override remains an operator feature and is removed by the manager's strict environment.

Selection uses installed mode plus absence of an explicit runtime-socket member or namespace override. An inherited storage-root pin does not suppress the external transport default. Custom installed storage roots retain distinct root-derived runtime/worker endpoint leaves within the shared transient family directory; an explicit synthetic namespace controls fixture directory isolation. Development mode remains root-relative. Neither mode nor channel is inferred from the root pathname or from the presence of a pin. Native packages retain their projected channel identity and pip/uvx remain stable-only. The manager's existing admission to only the installed default storage root remains unchanged; this transport rule grants no management authority over custom roots.

The canonical owner declares the public _CS_DARWIN_USER_CACHE_DIR base and the identity-projected channel-independent product-family directory. Python and Rust consume the same declaration and generated conformance vectors. Native lookup and filesystem work occur at the location/endpoint boundary, never during Settings construction. No consumer invents a subpath, setting or native default. The taxonomy explicitly represents external transient materialisation and reclaim policy; it must not pretend this directory is below the data root.

Each process resolves this transport base once through the canonical owner. Resolve the OS-provided alias to its canonical path, then use no-follow directory handles and retain namespace identity. Both base and product directory must belong to the current UID and be owner-only. The public OS query may materialise its own cache base; that returned base is validated before use. Application filesystem operations create only a missing product directory, with mode 0700. An insecure existing base or product directory is refused, never repaired. Missing native evidence, replacement, ownership mismatch or a final socket pathname at or above the platform bound refuses. There is no temporary-directory, environment-base, private-API or working-directory fallback.

No new environment pin is introduced. The established storage-root pin and strict/operator profiles remain unchanged. Independently queried UID-scoped native bases must obey equivalent resolution/refusal rules; retained namespace checks detect disappearance or replacement. A pathname pin would not provide inode custody.

Stable and preview share the transient product-family directory but keep separate persistent roots and endpoint identities. Runtime/worker names retain their existing root-derived identities. The manager filename is manager- plus the unpadded base64url encoding of the first 16 bytes of a SHA-256 digest, then .sock. The digest input is a canonical compact JSON array of exactly four strings, in order: the domain/version tag `cadrumo-manager-session-v1`, channel-qualified manager identifier, UID as a decimal string, and native session identifier as a decimal string. The core declaration owns the tag, grammar and vectors. Names remain independent of version, installation scope and image path; the full owner/session/image admission remains mandatory.

Namespace lock inodes are persistent while contenders may exist. Ordinary product materialisation/reclaim/uninstall never deletes the shared directory or its lock files. Socket cleanup remains incarnation-checked. Safe-boot or externally removed namespaces are absence/refusal, not permission to recreate authority beneath a live retained handle. No old endpoint reader, migration or automatic old-directory cleanup is introduced.

## Implementation

We will add the Darwin transient anchor to the canonical location declaration and generated contract, implement equivalent lazy Python and native-platform resolution, and consume it in installed runtime/worker and manager endpoints. Existing explicit fixture namespace injection stays available. Compact manager naming receives shared vectors and native tests. Per-session manager ownership must coordinate with the IPC namespace lock instead of reacquiring it implicitly; this decision does not resolve that separate integration step.

The affected prior wording is amended together: canonical-environment's one-root and unchanged-member passages permit this transport-only exception; storage-management R3/R5 permit this declared member relocation and owner-level native query, with explicit materialisation/reclaim treatment; data-output-standardization R1 and its single-root consequences exclude only these transient transport leaves and locks; the manager POSIX IPC/naming contract consumes the declared external anchor and compact filename. Their broader persistent-data and strict-environment commitments remain binding.

Verification requires Python/Rust vectors, no Settings-side effects, refusal of insecure/replaced namespaces, stable/preview separation, long-home independence, retained lock contention and cleanup behavior, and actual native Darwin bind/connect peer-identity checks in synthetic namespaces. Installed graphical lifecycle acceptance remains separate and cannot run on the supplied non-disposable hosts.

## Rationale

The public user cache base removes the measured dependence on home-path length while retaining native peer identity and canonical location ownership. A family directory avoids spending the path budget on channel directory names; existing root identity and the manager's channel-qualified digest retain separation. The narrow external transport exception does not create multiple locations for persistent application data. See the linked research for native evidence and limits.

## Consequences

Default installed Darwin endpoint discovery changes in the pre-release regime. Old transient namespaces are neither consumed nor migrated. Native cache lookup, canonical custody and external-anchor policy become required and must match across Python and Rust. Cache-base length still receives a runtime bound check; no universal Apple pathname-length guarantee is claimed. Reconsider this decision if the public cache API becomes unavailable, secure ownership cannot be established, or native peer identity changes. Acceptance establishes the implementation contract, not completed native installation or lifecycle evidence.

## Acceptance

Accepted 2026-10-08 under the user's advance authorization to fix the identified high, medium and low defects, install required dependencies, and code/build all installer and manager work except signing certificates. This narrow transient-default correction is necessary to remove the measured installed Darwin launch blocker within the approved runtime-manager work. The four governing ADRs are reconciled in the same change. Persistent data locations, host non-disposability, signing requirements and native lifecycle acceptance gates remain unchanged. Acceptance authorizes the implementation contract; it is not implementation or release evidence.
