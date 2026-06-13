---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P22-S88]]'
---

# `secure-storage-production-hardening` Code Review

S89-SELF | INFO | Review opened for `W12.P22.S89`.
Scope: named profile lifecycle storage spans for create/switch/delete/logout, removal of CLI/wizard direct pointer and master-key span ownership, profile create custody provisioning, and hardened setup smoke fixtures.

S89-001 | HIGH | Profile create still wrote the active-profile pointer outside `ProfileRepository`.
Review found `profile_create_storage_span` wrote the active-profile pointer before `ProfileRepository.create`, violating the repository's documented sole-writer contract.

S89-002 | MEDIUM | Delete lifecycle span was still assembled in the CLI.
Review found `config_profile_delete` opened an app-layer storage session from the CLI and then called `ProfileRepository().delete()` directly instead of delegating to a named application lifecycle operation.

S89-003 | MEDIUM | Switch still performed storage-scoped event persistence from the CLI.
Review found `config_profile_switch` opened the lifecycle session from the CLI and then appended `PROFILE_ACTIVATED` through a CLI-local bucket-event repository write.

S89-REMEDIATION | PASS | Review findings remediated locally before closure.
Create now passes a bootstrap routing profile id into `ProfileRepository.create`, and the temporary route pointer is restored and re-written inside that repository method before the encrypted record commit. Switch and delete now delegate to named application lifecycle operations, and the `PROFILE_ACTIVATED` event append moved to application user-profile orchestration. CLI, wizard, and setup-service scans show no direct master-key provider, active-pointer, active-profile override, direct delete, or CLI-local activation event writes in the reviewed lifecycle surfaces. Validation passed with ruff and focused pytest gates.

S89-REREVIEW | PASS | Narrow re-review after remediation found the three prior findings closed: create pointer ownership is inside `ProfileRepository.create`, switch/delete lifecycle spans are application-owned, and activation event persistence is in user-profile orchestration. Reviewed lifecycle CLI/wizard/setup surfaces have no direct master-key provider, active-pointer, active-profile override, direct delete, or CLI-local activation event writes.
