---
tags:
  - '#audit'
  - '#native-build-incremental'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:a85ad77f906ce96b2cb70c51cf58e6b0265c99cd9e2e32ff12c814f7f46f91fd'
related:
  - "[[2026-10-16-native-build-incremental-plan]]"
---
# `native-build-incremental` audit: incremental packaging and single-MSI integration

## Scope

Rolling integrated review against the approved native-build-incremental plan and accepted decision. S01 is committed at 01b2e2ff76; S02/S03 reviews cover current working-tree producer, assembly and parent integration changes. The installer worker owns S04, independently reviewed by the assembly worker. Parent owns native build integration and shared verification. Unrelated concurrent source edits remain outside the commit scope.

## Findings

### compiler-version | medium | Compatible developer interpreter initially conflicted with exact bytecode gates

Resolved: both bytecode gates admit the pinned runtime major/minor and a developer patch at least as new, preserving actual compiler identity in cache currency. A real developer CPython3.13.15 produced checked-hash bytecode executed successfully by the existing SDK CPython3.13.11. The packaged runtime/SDK pins are unchanged.

### assembly-ownership | medium | Missing helper inputs and temporary cleanup ownership could leave stale outputs

Resolved: the CMake assembly input list includes assembly_transaction, and temporary work has a BuildPaths/cleanup owner. app-payload owns its assembly receipt and clean paths; bundle/app-distro cleanup delegates to it. The unshipped test-consumer application rlib is no longer an explicit app-payload prerequisite; native verification retains it.

### authority-reuse | medium | Relocated authority files were copied again on native-only changes

Resolved: verified reuse maps the exact layout-declared authority subtree to its final package location. Windows/POSIX regression tests confirm prior immutable bytes are reused without sharing mutable source inputs. The persistent product snapshot publishes a coherently captured authority pair before pruning obsolete snapshot-owned generations, retaining the authoring authority untouched.

### obsolete-base-members | medium | Changed obsolete base members could remain orphaned

Resolved: base closure synchronization refuses an obsolete member that no longer matches its prior owner's bytes, and preserves its receipt on refusal. Unchanged owned members retain timestamps; separately owned application files survive normal base refresh.

### deleted-wheel-members | high | New-wheel hashes alone failed to detect deleted installed members

Resolved: installed wheel currency now checks installed RECORD ownership membership against the new wheel as well as member bytes. Only exact installer metadata additions and wrappers declared by the new wheel are admitted. Three real uv tests prove deletion-only module/corpus edits trigger reinstall and remove old members, while legitimate installer additions remain reusable.

### snapshot-links | high | Persistent snapshot links could redirect changed writes outside ownership

Resolved: retained snapshot roots, ancestors and members reject symlinks/junctions before mutation; build_product preserves lexical output ownership for that admission. Two regressions prove refusal occurs before changing an earlier ordinary member.

### build-and-native-acceptance | medium | Final integration evidence remains pending

PENDING: S02/S03 focused producer, rollback, authority, bytecode, native platform, Node and content-currency checks pass, along with changed-file style/type checks. The first configured Python product build passes and installed only one changed cohort wheel; source edits during that build correctly prevent a reusable checkout identity. Parent must finish current-source Debug/Release app-payload builds and unchanged-repeat verification. Independent installer review and rebuilt-adapter tests are active; genuine disposable installed lifecycle acceptance is not established by source/unit/compiler evidence.

## Recommendations

Retain the corrected content/membership and ownership refusal tests. Close S04 only after one actual compilation/zero unchanged evidence and native owner/admission regression checks pass. Append final build/no-op/package verification evidence before declaring the plan complete. A prior platform-specific release acceptance gate remains explicit when the required disposable host is unavailable.
