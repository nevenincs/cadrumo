---
tags:
  - '#research'
  - '#application-distribution'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:244954a55d37647501df34b2731e1a1bc2961a4f59cb41b0ae58db7397f8cfe2'
related:
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-application-distribution-audit]]"
---

# Darwin scoped installation and receipt authority

A CMake-invoked, one-shot maintenance owner can wait for native Installer completion and then verify receipts and installed bytes before publishing a version. Native documentation supports both local-system and current-user-home package domains. It does not yet establish this application's positive receipt schema, reliable absence classification, complete all-account conflict discovery, or interrupted-install recovery. These remain release-blocking evidence requirements, not conclusions from package construction.

## Findings

### Existing installation state and macOS packaging cannot yet represent this ownership

`dev/packaging/native/installation.py` selects versioned layout only for Windows with a manager; macOS currently maps the payload into one application bundle's `Contents/MacOS`. `native/application/src/installation/maintenance.rs` expresses native ownership as an MSI product code and machine or SID context. Darwin needs a distinct typed native owner, not a fabricated ProductCode or SID. Existing Windows serialization and semantics must remain compatible. A distinct Darwin contract does not by itself require a breaking shared-state migration; its schema mechanics require caller and serde review.

`native/package-layout.json` owns the relative installation marker, versions directory and publication directory. `dev/packaging/native/layout.py`, `identity.py` and `generate.py` own their platform interpretation and generated contracts. A Darwin topology must extend these declarations rather than introduce consumer-specific paths. Installation metadata is separate from taxpayer data. The accepted Darwin transport exception remains limited to transient sockets and namespace locks.

### Public Installer domains support scope-restricted packages

Apple's Distribution XML reference documents `enable_currentUserHome`: installation runs as the current user, cannot write outside that user's home and must function from that home. It separately controls local-system and other-volume domains. CPack's productbuild generator exposes these controls. Swift's official macOS instructions demonstrate `installer -target CurrentUserHomeDirectory -pkg …`.

A user package should permit only CurrentUserHomeDirectory; a machine package only LocalSystem. This is support for constructing and invoking distinct native packages, not proof of our resulting receipt records or launch behavior. The user-scope maintenance owner must bind the actual non-root caller to the native account home, independently of ambient HOME or SUDO_UID. A machine maintenance owner may run elevated once; the manager must remain unelevated.

### pkgutil exposes a home-directory receipt domain without a public fixed receipt path

The supplied Mac's installed `pkgutil(1)` explicitly accepts a volume or home directory with `--volume`, defaults to `/`, and warns that receipt storage locations can change. Exact identity queries include `--pkg-info-plist` and `--export-plist`. Implementations must use the tool's declared domain and exact package identity, not inspect assumed receipt directories.

Read-only native observations used one deliberately absent synthetic identifier, `md.neve.cadrumo.receipt-domain-uninstalled-probe`. Both `--volume /` and the caller's canonical home accepted exact info queries and returned exit 1 with a domain-specific missing-receipt diagnostic. Anchored `--pkgs=REGEXP` queries returned exit 1 and empty streams. No unrelated package inventory was requested. These observations do not prove that exit 1 always means absence, or distinguish unavailable databases, permission errors and native failures. Positive receipt schema, error classification and cross-account isolation require controlled installed fixtures before installation may be enabled.

The read-only account binding established real UID, effective UID, native account UID and home owner UID all equal to 501. The canonical home was mode 0700. Identity came from the native account record, not HOME. Reused numeric UIDs, changed home identity, aliases and uncertain account resolution must not silently adopt an existing owner.

### Postinstall cannot substitute for observed native completion

Earlier topology grounding in `2026-10-04-application-distribution-audit` establishes the receipt-timing problem: a package script cannot claim the completed transaction's receipt is already durable. A package script therefore cannot publish shared Ready state merely because its own work succeeded.

The proposed CLI-first flow has a one-shot owner hold maintenance custody, admit exact artifacts and scope, record Pending, run Installer once, wait for its actual terminal result, then independently verify the native receipt and complete installed inventory before atomic publication. A failed or lost owner leaves recovery work. Native Installer is not assumed to provide MSI's transaction or rollback semantics; compensation must verify exactly what remains before removing or restoring anything.

This uses the user's requested CMake installation steps. It does not require an invented graphical elevation broker, resident privileged service or detached postinstall finalizer. Direct package invocation must remain unable to bypass maintenance admission; the concrete package/owner interlock is still an implementation and native-proof obligation.

### Sealed bundles require external publication and retained anchors

Apple's signing guidance prohibits treating a signed bundle as mutable state and constrains nested code layout. Publication, maintenance locks and receipts must stay outside sealed bundles. A stable launcher may execute a selected version's executable; the design must not load unsigned or externally mutable code into its signed process as a shortcut.

A complete older stable bundle generation and every active version must survive failed upgrade and compensation. Replacing the stable entry requires custody covering its actual lifetime, not merely an open POSIX descriptor. All direct launch paths must participate in the shared guard; a retained descriptor alone does not prevent unlinking. Existing shared-store and launch-guard APIs provide useful primitives, but do not prove the new Darwin topology.

### Installed-scope login defaults need scoped LaunchAgents

Apple documents per-user launchd loading system-wide agents from `/Library/LaunchAgents` and user agents from `~/Library/LaunchAgents`. A scoped Aqua agent can preserve the accepted installation-scope default login behavior. Its Program would be an absolute stable bootstrap path, with generated identity and the existing manager policy.

The current `dev/packaging/native/macos_launchagent.py` instead emits a bundled `SMAppService.agent` hypothesis. Per-user registration by a running application does not establish default registration for every account of a machine installation. Replacing that hypothesis requires an explicit decision amendment. It does not establish graphical acceptance, unlocked-session evidence, user approval behavior, immediate registration, or signing readiness.

### Complete machine-scope conflict discovery is not established

The accepted manager decision refuses opposite-scope installations affecting an account. Local account enumeration, getpwent, currently mounted homes and mobile-account caches cannot be assumed to include every network or offline home. No complete all-account authority was established by this research.

Machine installation must therefore remain refused when completeness cannot be proved. A user install may inspect its exact native home domain and the machine domain, but must also distinguish query errors from absence. Runtime precedence for a conflicting user installation does not discharge installer admission. Introducing a central enrollment registry or weakening this rule would be a separate decision, not a hidden implementation assumption.

### Native receipt removal is distinct from uninstalling files

The native pkgutil manual states that `--forget` discards receipt data without touching installed files. Apple's Command Line Tools removal guidance likewise separates filesystem removal and receipt forgetting. Thus the blanket requirement to remove only through a package manager needs a narrow Darwin amendment.

A product-owned one-shot remover can use native receipts as ownership evidence, shared leases to refuse in-use removal, exact inventory and no-follow custody to remove only admitted resources, and then forget the exact receipt only after verifying removal. Unexpected or changed files, uncertain native state and lost custody must retain a fenced recovery state. Taxpayer data and the Darwin transport namespace are excluded.

## Sources

- Apple Distribution XML reference: https://developer.apple.com/library/archive/documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html
- CMake productbuild generator: https://cmake.org/cmake/help/latest/cpack_gen/productbuild.html
- Swift current-user package instructions: https://www.swift.org/install/macos/package_installer/
- Apple packaging guidance: https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution
- Apple code signing guide TN2206: https://developer.apple.com/library/archive/technotes/tn2206/_index.html
- Apple launchd job locations: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
- Apple ServiceManagement: https://developer.apple.com/documentation/servicemanagement/smappservice
- Apple Command Line Tools installation/removal: https://developer.apple.com/documentation/xcode/installing-the-command-line-tools
- Native evidence retained under `build/macos-process-typecheck/receipt-domain-evidence/`: installed manual pages, help, exact absent-identifier queries, native account binding and manifest. `pkgutil.man` SHA-256: `f68b556f9e850d4f19e45f0f7a4cc6f8db503e14f9052e87966cb35bbc00f6eb`; `installer.man`: `74455e53b0395375f08d741a6231eec92ba07d43f584727ea2d68849f9a7fc87`; `productbuild.man`: `7f1148e3a595d2d35b021f6a272edf5ba65046161dc3fb1ff9737f8b6d372b6f`. No fixture or product was installed, no launch service was registered and no host lifecycle was changed.
