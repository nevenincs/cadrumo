---
tags:
  - '#adr'
  - '#native-build-incremental'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:80513e5ef9322a2d3185a791fd61838292b64522bda064768c14ddca7b9ce9bb'
related:
  - "[[2026-10-16-native-build-disk-audit-reference]]"
  - "[[2026-10-03-application-packaging-interpreter-foundation-adr]]"
  - '[[2026-10-07-application-distribution-windows-versioned-msi-adr]]'
---
# `native-build-incremental` adr: externally managed tools and one incremental installer | (**status:** `accepted`)

## Problem Statement

Repeated packaging copies, local uv caches and four MSI products consume disk space and repeat compilation. The user explicitly requires incremental CMake builds, no build-created environment, no `_deps` or `var` build writes, and one MSI compilation.

## Considerations

The native-build-disk-audit reference records cache duplication and producer ownership overlaps. Existing interpreter, application distribution and native maintenance ownership decisions still govern runtime isolation, authenticated installation and rollback.

## Considered options

- Keep managed builders and cache all four MSI products: rejected by the explicit user requirements.
- Hide four compiler calls behind a wrapper: rejected; compilation count is actual compiler invocations.
- Use existing developer tools, incremental content producers and one scope-aware MSI with feature-qualified ownership: selected.

## Constraints

Accepted 2026-10-16 under the user's explicit implementation directions, including installer delegation. This refines build ownership and reverses build-local environment provisioning only; it does not change packaged runtime environment or user storage policy. CMake remains the sole build orchestrator. Existing final application/package paths stay unchanged. Build dependencies use enrolled `inputs` directories instead of `_deps`; build temporary work stays inside the binary directory or inherited OS temporary storage. Importing developer path constants never redirects machine caches. uv locations retain machine configuration; no repository uv cache or build-created virtual environment is permitted.

The release runtime and SDK retain their exact CPython pin. Existing developer Python may use the same major/minor and a patch at least as new as that pin; compiler identity must invalidate bytecode and wheel producers. The build validates already provisioned dependencies and never synchronizes an environment.

One changed Windows MSI payload compiles once, unchanged inputs compile zero times. Installation must retain scope isolation, authenticated product/callback admission, independent version and shared-registration lifetime, candidate verification, rollback and side-by-side version retention. Feature-qualified MSI ownership is permitted to represent those independent lifetimes in one product. Legacy ownership never silently becomes feature-qualified: missing qualifiers retain legacy product observation or fail closed where conversion would be ambiguous. No existing installation or user state is migrated by this work.

## Implementation

Narrow and incrementally synchronize coherent wheel snapshots, cache each wheel and agent runtime separately, and install only changed or missing wheel members. Assemble a sibling candidate using verified unchanged immutable members, private mutable relocation/adaptation inputs, content-bound bytecode and atomic promotion with rollback. Fix overlapping receipt ownership rather than weakening output validation. Port the Windows runner and native maintenance owner observation together before switching the MSI producer to one scope-aware product with independently maintained version and registration features.

## Rationale

Content-bound producer reuse removes actual repeated work while preserving tamper detection. Machine-managed uv configuration avoids private cache proliferation. One MSI requires role-qualified native observation; merely removing the current distinct-product check would break installation lifetime and rollback.

## Consequences

Existing build trees require reconfiguration. Already acquired dependency directories can be moved within their enrolled binary directory without changing final package paths. Old caches are removed only after committing and pushing code as previously instructed. Full acceptance requires real Debug/Release builds, no-op currency evidence, independent installer review and disposable native lifecycle tests. Acceptance of this decision does not assert those tests have passed.
