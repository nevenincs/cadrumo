---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:f95336e102124cd9ecf5c30e6624b92785f5c13672ebc3a79b571eb70df1a672'
related:
  - "[[2026-10-08-application-distribution-darwin-versioned-installation-research]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-10-08-canonical-environment-darwin-transport-adr]]"
  - "[[2026-10-07-application-distribution-windows-versioned-msi-adr]]"
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
---

# `application-distribution` adr: `Darwin scoped native packages and version publication` | (**status:** `proposed`)

## Problem Statement

The current macOS DMG contains one application bundle and cannot implement accepted side-by-side versions, retained stable anchors and lease-safe removal. Shared native installation ownership currently models Windows MSI ProductCode/SID semantics. Darwin needs honest native receipt-domain ownership and a completion boundary outside package scripts.

This is a proposal, not an accepted decision or activation authorization. The user's instruction to code and build everything except unavailable signing certificates supports implementation and unsigned artifact work after decision review. It does not supply missing native receipt, signing or interactive lifecycle evidence, or authorize product installation on the supplied personal Mac.

## Considerations

The grounded evidence is recorded in `2026-10-08-application-distribution-darwin-versioned-installation-research`. Native Installer supports separate CurrentUserHomeDirectory and LocalSystem domains. pkgutil supports a home directory as its receipt domain, but the observed absent-identifier queries do not establish positive schema or reliable absence/error classification. Package script success does not prove final receipt publication.

Machine-scope conflict admission must cover every affected account, including network and offline homes. Neither getpwent nor local/mobile account enumeration proves completeness. The proposal preserves the accepted refusal requirement instead of treating an incomplete inventory as empty.

## Considered options

- Keep a drag-copy bundle: lacks native installation ownership, version publication, native scoped registration and guarded removal.
- Publish Ready in postinstall: lacks independently observed native completion and cannot recover safely from all interrupted outcomes.
- Add a privileged resident broker or defer all registration to first app launch: adds a service or changes installed-scope default login behavior without necessity.
- Use one-shot CLI maintenance around real native Installer completion, with scope-restricted packages and native receipt verification: proposed. It fits CMake installation orchestration and keeps elevation out of the manager.

## Constraints

Windows native transaction, owner serialization and installed-state semantics remain unchanged. A discriminated Darwin contract must preserve existing Windows consumers and on-disk meaning; implementation must inspect serde and all callers before selecting schema mechanics. This proposal does not require a breaking migration or authorize guessed compatibility conversion.

Sealed bundle bytes are immutable. No taxpayer data, secrets, user preferences or Darwin transport namespace moves or becomes installer-owned. No new storage-root environment pin, daemon, resident privileged helper or elevated manager is introduced.

Every installation, repair, removal and recovery path must enforce owner admission and existing lifetime leases. A standalone PKG must refuse direct Installer invocation or repair that bypasses its authenticated maintenance owner. An environment flag, marker existence or postinstall publication check is insufficient: a bypass could overwrite a currently Ready, in-use version before publication is examined.

Unproven native state, incomplete account discovery, failed custody checks and uncertain native completion refuse activation or remain explicitly fenced. These gates do not prohibit source implementation, unsigned package construction or isolated non-installing tests.

## Implementation

### Declare the Darwin topology through existing owners

Extend `native/package-layout.json` and `native/platforms/macos-arm64.json`, consumed by `dev/packaging/native/layout.py`, `identity.py` and `generate.py`. Names come from canonical product/channel identity; consumers do not duplicate path literals.

Let D be the native current user's canonical home for user scope, or the filesystem root for machine scope. Proposed paths are:

- Stable sealed launcher: `D/Applications/<display_name>.app`.
- Installation prefix: `D/Library/Application Support/<application_id>/installation`.
- Immutable version: `<prefix>/versions/<version>/<display_name>.app`.
- Marker and publication: the existing declared relative members `data/installation.json` and `data/installation-state` under that prefix.
- Retained sealed launcher generation: a newly declared `anchors/<generation>/<display_name>.app` member under the prefix.
- Scoped login agent: `D/Library/LaunchAgents/<manager_id>.plist`.

These are installation resources, not an additional canonical taxpayer-data root. Stable and preview identities remain distinct. Package content roots and signing-aware nested-code placement must be declared explicitly; the current single-bundle Contents/MacOS mapping is not silently assumed sufficient for final signed distribution.

The stable launcher executes the selected immutable version's executable through the shared catalogue and launch guard. It does not load mutable external version libraries into its own process. Stable-bundle replacement requires exclusive custody proving it unused; otherwise defer replacement. Retain the previous complete sealed generation and version anchors until recovery and lifetime conditions permit cleanup.

### Build scoped native artifacts and invoke one owner

The canonical CMake distribution graph produces separate user and machine productbuild packages, then includes them with the one-shot maintenance interface in a DMG. Domain declarations permit exactly CurrentUserHomeDirectory for the user package, or LocalSystem for the machine package; anywhere/alternate domains are disabled. CMake install/upgrade/remove targets invoke the same owner as direct CLI use.

User ownership binds real/effective non-root UID, native account identity and canonical home identity. It must not infer authority from HOME, SUDO_UID or a root caller's requested username. Machine ownership requires explicit elevated one-shot maintenance. Scope, role and version receipt identifiers are generated and bound into the admitted package contract, together with destination and manifest identity.

Before Installer starts, the owner validates scope conflicts, complete relevant inventory, incoming artifacts, publication and every affected lifetime lease, then records durable Pending state while retaining prior anchors. Actual package preflight must authenticate the held owner, admitted artifact and actual Installer invocation through a non-forgeable native admission protocol, or equally strong native exclusion. It must cover direct package invocation, repair and recovery before payload mutation. The specific protocol is an unresolved feasibility prerequisite, not an established mechanism. Installer may delegate package scripts to installd; script ancestry must not be assumed to identify the original CLI child. A marker or nonce alone also cannot establish which transaction retains mutation authority after postinstall. Primary/native evidence must show authenticated transaction binding and custody through actual settlement, including negative direct-invocation and repair tests. Existing literal install gates remain until that proof; this proposal must not be treated as a complete executable backend before the mechanism is established.

The owner waits for the actual Installer child to settle. Only native success followed by exact receipt-domain queries, bound receipt identity/version, complete payload and registration inventory, retained custody and final owner/publication rechecks permits atomic Ready publication. Scripts never publish Ready. A detached finalizer is not used.

### Preserve platform-specific native ownership and recovery

Add a Darwin owner representation carrying scope/domain, UID and canonical home identity for user scope, exact receipt identity/version, admitted destination and package identity. Preserve existing Windows serialization and semantics where representable; reject unsupported states explicitly. Do not fabricate MSI identities for Darwin.

Before activation, controlled native fixtures must establish positive receipt fields, exact queries, domain isolation and a reliable distinction between absent, permission-denied, unavailable and malformed native state. Always use pkgutil's public domain interface, never assumed receipt database paths.

Owner loss, failed Installer completion, partial native changes or failed publication leave a fenced state. Recovery revalidates what actually exists under a fresh exclusive owner. Same-version repair requires exact bound bytes and native ownership; a prior receipt alone cannot prove a new attempt succeeded. Compensation may restore retained complete anchors or precisely remove admitted newly installed resources after lease checks. It is not described as MSI rollback, and cannot erase uncertain effects.

### Refuse incomplete scope admission

User admission inspects the exact caller/home receipt domain and machine domain, with native query errors distinct from absence. Machine admission must prove complete opposite-scope discovery for all affected accounts. If network/offline account and home coverage cannot be established, machine install remains gated and refuses. No local enumeration heuristic, runtime user-precedence fallback or signing certificate substitutes for completeness.

A central enrollment authority or a narrower supported account population would require a separately reviewed decision. This proposal does not quietly introduce either.

### Preserve installed-scope login defaults

Replace the bundled SMAppService-agent hypothesis with a scoped Aqua LaunchAgent: user scope under the native home, machine scope under /Library. Generate its identity and absolute Program path to the stable bootstrap; use the existing RunAtLoad, unsuccessful-relaunch and AbandonProcessGroup policy. The bootstrap must execute the actual manager so launchd tracks the right process.

This preserves installation-scope defaults without claiming that one user's SMAppService registration registers all accounts. Existing per-user opt-out remains in the existing user data root and is checked before manager startup. Installers do not write those preferences. Immediate current-session enrollment, graphical behavior and platform approval remain native acceptance obligations. Signing gates remain in force.

### Remove only exact owned resources after lifetime admission

Registration removal records Removing and withdraws launch/login visibility under exact scope and anchor custody. Managers detect removal and follow the existing bounded drain policy. In-use version or anchor removal refuses or defers; machine maintenance does not signal another user's processes.

An explicit installer-owned remover checks exact receipt domain, package identity, unchanged complete inventory, no-follow path custody and exclusive lifetime leases before removing admitted files. Unexpected or changed contents remain fenced rather than being recursively deleted. Prune only owned empty directories. Forget the exact receipt only after verified removal; receipt forgetting alone is never uninstall, and failure remains recoverable.

For Darwin only, this replaces the requirement that user cleanup operate through a package manager that deletes files. The manager may request the same scoped one-shot remover; it never performs arbitrary directory deletion. Taxpayer data, per-user opt-out and persistent Darwin socket locks are excluded.

### Reconcile governing wording before acceptance

The following older accepted commitments require dated, scoped amendments; this proposal does not edit them:

- `2026-10-04-application-distribution-adr`: clarify application-bundle/DMG delivery as a DMG carrying scoped native packages and a stable Applications launcher; narrow “Native package managers own uninstall” to permit the Darwin installer-owned remover with native receipt verification.
- `2026-10-04-runtime-manager-architecture-adr`: replace the macOS bundled SMAppService-agent hypothesis and its normative path with scoped Aqua LaunchAgents; replace Darwin “through the native package manager, never directory deletion” with precise installer-owned removal under native receipts and leases. Preserve installation-scope login defaults, complete scope conflict admission, stable anchors and no in-use removal.
- `2026-10-04-canonical-environment-adr`: clarify that these machine/user installation resources do not change canonical taxpayer-data paths, mode/channel authority or environment projection. No general exception to the single user-data-root rule is proposed.
- `2026-10-08-canonical-environment-darwin-transport-adr` and the Windows versioned-MSI decision remain unchanged; transport namespace ownership and Windows transaction rules are not transferred to Darwin.

### Implement in independently verifiable stages

First extend canonical declarations and platform-specific ownership while preserving Windows behavior; add generated-contract, parsing and layout tests. Then build scope-restricted unsigned PKGs/DMGs through CMake and inspect their exact payload, domains and identifiers without installing.

Next implement one-shot admission, authenticated package preflight, receipt observation, publication and recovery with isolated fixtures. Follow with shared launcher/lease integration, exact removal and scoped login artifact authoring. Keep activation gates until controlled native installations prove positive/error receipt classification, bypass refusal, owner loss, same-version integrity, partial completion, compensation, scope conflicts and in-use retention.

Finally require two genuinely built distinct releases and appropriate disposable interactive Mac evidence for install, launch, login opt-out, upgrade/cutover, rollback/compensation and uninstall. Supplied personal-host read-only tooling or unsigned artifact builds do not satisfy those scenarios. Signing and notarization remain release prerequisites; unavailable certificates do not block the authorized unsigned work.

## Rationale

A one-shot completion owner supplies the missing observation and publication boundary without elevating the manager or inventing a service. Native scope declarations and explicit receipt domains provide the starting point for real Darwin ownership. Sealed version bundles and shared lifetime guards preserve the existing architecture. Refusing incomplete discovery and uncertain native observations keeps unsupported configurations visible rather than treating them as successful installs.

## Consequences

The DMG remains the delivery format, with CLI-first CMake maintenance instead of an assumed drag-copy workflow. Darwin needs a real native backend, scoped package admission and an explicit remover. Source and unsigned build work can proceed after acceptance, while native installation remains gated by specific missing evidence. Machine scope may remain unavailable on hosts where complete opposite-scope discovery cannot be proved.
