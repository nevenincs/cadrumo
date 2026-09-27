---
tags:
  - '#research'
  - '#mcp-purpose-authentication'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:6a442a4e5d188589e3cadd7d806e70a224af4e66a5e91e93b58601c663d9265e'
related:
  - "[[2026-09-26-mcp-purpose-authentication-reference]]"
---

# mcp-purpose-authentication research: local automation authorization and lifecycle options

The question is how local Cadrumo automation can resume over months or years while human profile login expires and several agent sessions share one user's authorization. The user confirmed local deployment, concurrent agents with separately tracked sessions, durable API-credential capability, and replacement of the old MCP implementation. Evidence favors separating durable authorization, short-lived access, encrypted key custody and durable work. Exact API-token formats and cryptographic mechanisms remain implementation research.

## Findings

### MCP connection state does not authenticate a profile

The 2025-11-25 authorization specification addresses HTTP transport; stdio obtains credentials through its local execution environment instead. The security guidance explicitly separates session identification from authentication and requires authorization on inbound requests. Therefore an initialized MCP connection, clientInfo name or remembered session ID cannot establish a Cadrumo profile grant. Local API credentials need not be an OAuth deployment. Sources: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization and https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices (accessed 2026-09-26).

### Host-owned stdio and a persistent local runtime can have separate lifetimes

The transport specification defines stdio as a subprocess launched by the MCP client. A Cadrumo-owned local service can be reached through a short-lived stdio adapter without treating the chat process as the owner of durable jobs or profile grants. Direct host-owned execution is simpler; a shared runtime adds installation, IPC authentication, upgrade and recovery obligations but provides one authority for simultaneous grants, revocation and work coordination. The comparison is an architectural inference, informed by https://modelcontextprotocol.io/specification/2025-11-25/basic/transports and the related current-code reference.

### Long-term automation needs an explicit alternate unlock capability

A scoped API-token verifier alone cannot decrypt a password-protected profile after its interactive session ends. Supporting unattended access therefore requires an explicitly enrolled capability to unlock that profile, protected independently of the remembered human login. Otherwise the choices are retaining the password, keeping plaintext keys alive indefinitely, or requiring user unlock. This follows from the password/receipt boundary documented in the related reference; it is not an OAuth feature.

A durable per-profile grant is more appropriate than an immortal all-profile bearer. Authorization lifetime, credential rotation, access-lease lifetime and job lifetime can differ. Device-bound custody is useful locally, but same-OS-user process compromise remains outside strong tenant isolation. Separate OS accounts or a stronger sandbox are required for that guarantee. These are threat-model conclusions, not claims of implemented controls.

### Process containment must own descendants

Windows Job Objects can group and terminate processes and support kill-on-job-close, with explicit inheritance and breakaway semantics. They are a relevant primitive for worker containment; they do not themselves establish user authorization. A process-tree kill fallback is weaker than proving all children belonged to an owned containment boundary. Source: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects (accessed 2026-09-26). Linux/macOS supervisor integration and crash/parent-death behavior require platform execution evidence; none was gathered here.

### Password collection stays outside model-visible tool data

MCP form elicitation cannot collect passwords or API tokens. The spec has out-of-band URL mode, but a local Cadrumo credential surface can preserve the existing product secret boundary without making host elicitation support a prerequisite. Approval must be completed and verified by Cadrumo; a claimed button click is not a credential. Source: https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation (accessed 2026-09-26).

The requested Claude full documentation export was inaccessible through the browser tool. The current connector authentication page was fetched instead; it distinguishes hosted OAuth registration from local Claude Code behavior and now documents organization request-header credentials. Older skill statements about all client token support must therefore not be assumed current. None of those hosted mechanisms is necessary for the confirmed local stdio deployment. Source: https://claude.com/docs/connectors/building/authentication (accessed 2026-09-26).

### Native credential stores must be selected explicitly

The keyring project supports native Windows Credential Locker, macOS Keychain and Linux Secret Service/KWallet, and also permits third-party backends. A usable priority is therefore not a security attestation. Its macOS security notes also distinguish access by the hosting Python executable from independent application isolation. Native backend selection plus tested locked/unavailable behavior fits the declared same-OS-user trust boundary; arbitrary plugins or plaintext fallback do not. Source: https://keyring.readthedocs.io/en/latest/ (accessed 2026-09-26).

Secret Service makes locked items unreadable and may require a prompt to unlock. A daemon cannot promise silent success merely because a collection was available during enrollment. Background reads need a non-prompting path and a typed unavailable/needs-user outcome. Source: https://specifications.freedesktop.org/secret-service/latest/unlocking.html (accessed 2026-09-26).

### Existing authenticated encryption avoids a new cryptographic stack

AES-GCM authenticates associated data and requires unique nonces for each key; authentication fails when ciphertext, key, nonce or associated data changes. This supports binding a sealed record to profile, grant and generation, but does not make the filesystem or a restored old record fresh. A separately protected current-record witness is needed for disk-record rollback detection. The first statement is the primitive contract; the witness conclusion is this review's inference. Source: https://cryptography.io/en/latest/hazmat/primitives/aead/ (accessed 2026-09-26). The exact existing Cadrumo primitive and dependency range are recorded in the Reference.

### Local transport needs explicit OS peer and access controls

Windows named-pipe defaults can grant read access to Everyone and anonymous users; broad generic write rights also include pipe-instance creation. An explicit DACL and narrowly selected rights are necessary. The Windows pipe APIs expose the peer process identity, from which the adapter can verify an opened process token rather than trusting a supplied PID. Local-only rejection and network denial are required because named pipes can otherwise be remotely reachable. Sources: https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights ; https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid ; https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipes (accessed 2026-09-26).

Linux pathname UNIX sockets inherit filesystem ownership/permission controls and support SO_PEERCRED peer credentials. An owner-only directory and peer check serve different purposes. Source: https://www.man7.org/linux/man-pages/man7/unix.7.html (accessed 2026-09-26).

Python multiprocessing.connection supplies optional HMAC authentication, but that is not an encrypted channel or profile authorization; object receive also carries pickle semantics. It is not sufficient as an unreviewed public runtime protocol. Source: https://docs.python.org/3/library/multiprocessing.html (accessed 2026-09-26). The evidence favors an OS-protected local byte protocol, with application credential checks and no object deserialization, within the explicitly trusted OS-account boundary.

### Background ownership follows OS login

Windows TASK_LOGON_INTERACTIVE_TOKEN uses an already logged-on user's interactive token. Apple's user LaunchAgents run under the per-user launchd context. These fit the local-user deployment and do not imply execution before OS login. Sources: https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type ; https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html (accessed 2026-09-26).

Platform documentation is not cross-platform execution evidence. Native store behavior, user-supervisor installation, socket peer APIs, descendant cleanup and sign-out/suspend behavior remain required real-platform acceptance tests.

## Sources

- 2026-09-26-mcp-purpose-authentication-reference.
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://claude.com/docs/connectors/building/authentication
