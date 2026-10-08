---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-07'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:6c5193675cb1987846e0ca2dfbdf423de6de547209cb36cd7e320181e451abeb'
related:
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-05-runtime-manager-architecture-audit]]"
  - "[[2026-10-04-application-distribution-audit]]"
---

# `application-distribution` adr: `Windows immutable version products and stable registration` | (**status:** `accepted`)

## Problem Statement

The manager's accepted architecture requires side-by-side versions, two installation scopes and preservation of in-use program files. The current combined CPack MSI owns a version and its shared entry together and uses a removing major upgrade. Complete installer acceptance cannot pass that policy. The operator requested completing installer/upgrade acceptance on 2026-10-07; this proposal makes the missing Windows ownership choice concrete for review.

## Considerations

Current source, the pinned CPack template, primary Windows Installer rules and host limitations are recorded in 2026-10-04-application-distribution-audit. The accepted 2026-10-04-application-distribution-adr and 2026-10-04-runtime-manager-architecture-adr already decide topology, binary placement, privilege and lifecycle authority. This record refines their format-specific ownership prerequisite; it does not reverse or supersede either decision.

## Considered options

- Keep one combined major-upgrade MSI: cannot preserve a prior product's in-use version; rejected.
- Remove MajorUpgrade from a combined MSI: leaves successive products competing for shared entry, marker and registration resources; component ownership and uninstall remain unresolved; rejected.
- One immutable version MSI per release, behind a separate stable registration MSI: preferred. More authoring and two-product transaction/recovery work, but version removal cannot implicitly remove shared launch registration or another version.

## Constraints

Authorized 2026-10-07: after reviewing the concrete Windows ownership proposal and specifying MSI delivery, the operator directed continued installer and upgrade implementation. This accepts the two native MSI roles, both scopes and the preservation/publication obligations in this record; format setup alone did not constitute that acceptance. Manager IPC, handoff, rollback, preferences and package removal retain their accepted owners and open Steps; passing this ADR or its local tests does not complete them.

1. The verified package remains unchanged under the canonical prefix's versions/<major.minor.patch>. Manager and desktop images remain at each package root. Only the distribution owner adds version-independent prefix resources; no business data, credential or profile connection enters an MSI.
2. Each release/scope/channel/target has a distinct immutable version product and unique path-derived component ownership. Its MSI owns only that version. Its normal install/upgrade never schedules removal or replacement of another version. Same-version different bytes are refused; repair uses the identified release inventory, not a replacement disguised as repair.
3. One registration product per scope/channel/target owns the stable manager copy, prefix marker, shared notices, EntryPoint/InstallLocation, login registration and shortcuts. Compatible updates preserve shared component identity. Version products never own those resources. Registration records which version supplies its manager copy and desktop shortcut; those anchor versions remain installed until registration is safely advanced. The current catalogue requirement that the stable copy match a complete version is preserved.
4. Identity projections distinguish legacy combined, registration and version product roles and user/machine scope. ProductCode and PackageCode retain their documented independent lifetimes; component identity includes its actual resource location. Existing published family identifiers are not silently reinterpreted. Legacy combined products or ambiguous ownership refuse migration until released fixtures and a separately reviewed migration prove preservation.
5. Build separate perUser and perMachine packages from the same owners. Per-user installation needs no administrator token and registers HKCU; per-machine installation uses installer elevation and HKLM. Program-file locations follow native conventions and the explicit scope. The runtime and manager remain unelevated interactive-user processes. Installing never invokes the manager from an elevated context or turns an override into a managed default.
6. Scope admission refuses a conflicting installation for an affected account. Machine admission checks native registered products across account contexts rather than treating the elevated installer's HKCU as every user's hive. Missing evidence, malformed ownership or inaccessible inventory is a refusal. If conflicting scopes nevertheless exist, this-user precedence at manager startup remains the accepted fallback; it grants no second runtime owner.
7. Install a new version and prove its inventory before updating registration. Publication/removal needs installer-owned transaction state outside the immutable package inventory, consumed through the shared catalogue owner; an uncommitted or removing native product is not eligible. Atomic status publication, concurrent startup and native rollback must be verified. Failed registration preserves the prior launch configuration and reports incomplete work; rollback never deletes a version acquired by a process.
8. Installer maintenance does not use Restart Manager to close CADRUMO processes, force a reboot or signal a runtime. Package-owned removal excludes new version launches while proving that no process in any session uses it. If exclusion or liveness cannot be proved, retain the product and report deferred maintenance. This-user cleanup is requested through its native package manager; all-users cleanup requires the next elevated maintenance run. Runtime cutover and readiness rollback stay with the manager.
9. Uninstall removes the scoped shared registrations and stable entry, then permits running managers to detect removal and drain gracefully. In-use version products remain for safe deferred native removal; user state is preserved. Directly deleting program directories is not a substitute for native package ownership.
10. Signing, matching WiX tools/extensions, any applicable tool terms, real release-payload proof and disposable-host acceptance remain separate gates. An artifact with no such evidence is not manager-shippable.

## Implementation

We will author two MSI roles through the existing CMake distribution graph and its Python identity/layout owners. A custom WiX template removes cross-release RemoveExistingProducts behavior from version products. The registration product handles only its shared resources and scoped registration. The operator explicitly selected MSI delivery on 2026-10-07. Deliver the two roles as native MSI artifacts with an ordered installation and maintenance workflow; an EXE bootstrapper is not the requested format. Product sequencing and rollback still require the installer-owned publication protocol described above; this delivery choice does not establish its implementation or acceptance. Generated product locators and native maintenance status belong to the installation contract, not duplicated manager or desktop declarations.

Before source execution, refine the owning distribution plan for role/scope identities, immutable product authoring, transaction and scope admission, safe repair/uninstall, and a real acceptance harness. The existing manager plan owns IPC, default login start and opt-out, designated successor handoff/rollback and uninstall detection. A safe native installer is required before those package acceptance runs.

Acceptance uses two genuinely built different releases, exact artifact/manifest identities and an explicitly disposable Windows host. Cover both scopes and channels, standard/admin accounts, relocated Unicode/space prefixes, an old manager/runtime and desktop held live during installation, incomplete/corrupt/interrupted candidates, idle/busy handoff, lost readiness and rollback, concurrent sessions, conflicting scopes, repair and uninstall with user-state/unowned-file preservation, reboot-deferred residue and actual login/logoff/cancelled shutdown. Record build, product/component identities, logs, process image/creation-time observations and before/after hashes. Catalogue fixtures, ZIP staging and Session-0 refusal do not satisfy these gates.

### 2026-10-08 native transaction refinement

Under the operator's instruction to implement and build the unsigned installers, ordered native maintenance is the supported installation entry. CMake invokes an installer-only transaction runner over hash-bound version and registration MSIs. It owns MsiBeginTransaction and holds exact prefix/version exclusion, verifies the installed version before submitting shared registration, and permits atomic Ready-plus-anchor publication only after successful MsiEndTransaction(COMMIT) and exact native ownership/inventory revalidation. Callback success, InstallFinalize, an idle _MSIExecute mutex, process exit and ProductState=5 alone do not prove commitment. Rollback, owner loss, timeout or ambiguous native evidence retains the durable Pending/Removing fence and prior anchors. Machine maintenance requires installer elevation; manager/runtime remain governed by their existing interactive-user admission policy. Delivery remains MSI; the runner is CMake orchestration support. Direct standalone MSI installation remains refused until an equivalent authenticated owner participates. Software and disposable-host acceptance remain separate from unsigned artifact generation.

Primary evidence: Microsoft documents that successful [MsiEndTransaction(COMMIT)](https://learn.microsoft.com/en-us/windows/win32/api/msi/nf-msi-msiendtransaction) deletes rollback scripts, that [commit custom actions](https://learn.microsoft.com/en-us/windows/win32/msi/commit-custom-actions) can fail and trigger rollback, and that [_MSIExecute](https://learn.microsoft.com/en-us/windows/win32/msi/-msiexecute-mutex) covers the execute sequence. Implementation must verify the owner protocol and native custody before lifting the existing gate.


### 2026-10-08 owner compatibility refinement

Under the existing authorization to complete native maintenance, old cached registration actions must admit a newer maintenance runner without pinning every future release to the first runner's bytes. Use a bounded protected owner record inside the immutable contract's publication directory. The native runner holds maintenance exclusion and namespace custody, publishes an atomic record for the current synchronous native operation, and invalidates it when that operation ends. The record binds a fresh transaction-incarnation nonce, endpoint, exact prefix and native scope/account, product role and operation, and held runner PID, creation time, image path and digest. A callback independently admits existing namespace/content ACLs and ancestry without creating or repairing anything, retains file custody, and verifies the actual native pipe peer against the record before requesting the exact active claim. Machine records admit only trusted administrative/system mutation, including protection against implicit owner WRITE_DAC; user records bind the native user SID. Public MSI properties and record paths remain locators only. Initial new-artifact admission still checks its authored runner digest. Cached product metadata still proves the exact native product/family/role and cannot alone authorize an unknown runner.

A transaction nonce or opaque native handle is correlation, never independent proof that a callback belongs to a committed transaction. The broker additionally authenticates the actual System32 Windows Installer client and effective token and limits admission to the active synchronous native operation. Nested removal of an old registration must be explicitly admitted from retained native cached-product evidence within that operation; unrelated products or standalone requests refuse. Owner loss, identity mismatch, stale records or ambiguous native settlement retain the publication fence. Only the existing successful MsiEndTransaction(COMMIT) boundary followed by native inventory verification can publish Ready. No new manager authority, premature candidate publication or signing bypass is introduced.

This refines the same transaction-owner decision; it does not establish acceptance. Required negative evidence includes wrong SID/scope/prefix/product/operation, mutable ancestor or owner ACL, stale PID/creation/image/endpoint, altered record, owner death and unauthenticated standalone installation. A genuine changed-runner two-release upgrade must exercise old cached custom actions. Microsoft documents [single transaction ownership and owner-loss rollback](https://learn.microsoft.com/en-us/windows/win32/api/msi/nf-msi-msibegintransactionw), the [owner-only settlement boundary](https://learn.microsoft.com/en-us/windows/win32/api/msi/nf-msi-msiendtransaction), and the need to preserve the effective context and protected data in [custom action security](https://learn.microsoft.com/en-us/windows/win32/msi/custom-action-security). The record's correlation design is our implementation choice, not a native API guarantee.

### Exact same-version no-op admission, 2026-10-08

The user's continuing authorization to complete unsigned installation code includes an exact already-installed no-op. This does not relax anchored repair exclusion or native installation gates. A no-op may succeed only under maintenance exclusion after verifying the exact native owners and cached product identity, Ready publication and anchors, complete immutable version bytes, and the actual shared registration resources. Cached MSI properties or component key-path status alone do not prove installed registration integrity.

The existing MSI authoring owner projects a bounded, typed registration-resource description into its immutable registration MSI: shared file hashes including the native marker bytes, scoped registry values and component identity, and desktop shortcut semantics. Installer verification consumes that same bound description and reads actual native resources without invoking repair, launching a shortcut, changing publication, or opening a native installation transaction. Missing, legacy, damaged or ambiguous evidence refuses no-op admission; normal ordered maintenance retains its own existing admission rules. A distinct successful result must identify that an already-published installation was verified, not claim that native installation or repair ran. No-op verification may coexist with readers of unchanged version files while retaining maintenance exclusion and file/version custody through its observation.

## Rationale

Separating immutable version ownership from shared registration lets Windows Installer retain its repair/uninstall responsibilities without a new release removing the old runtime's program files. It follows the already accepted topology while making the installer-specific lifetimes explicit. Removing one XML upgrade element alone cannot solve competing shared-resource ownership.

## Consequences

The Windows installer becomes a composed delivery rather than one combined product. Disk use increases while anchor or in-use versions are retained. Transaction publication and safe maintenance require shared catalogue integration and new native acceptance evidence. The existing accepted ADRs need no wording change or supersession. Linux/RPM/DEB and macOS ownership remain separate platform-specific ownership and acceptance gates; this Windows proposal establishes none of their acceptance. Approval authorizes this ownership design, not public distribution, tool-term acceptance, deployment or profile migration.
