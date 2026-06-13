---
tags:
  - '#adr'
  - '#settings-di-deferral'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-04-settings-di-deferral-research]]'
---

# `settings-di-deferral` adr: explicit deferral of ContextVar-backed Settings override seam to follow-up sprint | (**status:** `accepted`)

## Problem Statement

The `2026-05-14-settings-di-plan` was authored to execute a complete dependency-injection migration for the Settings model: expanding `aeat.core.config.Settings` with three Category-B fields (`aeat_log_dir`, `aeat_libreoffice_executable`, `aeat_master_key_passphrase`), introducing a `ContextVar`-backed `override_settings()` context manager, and migrating 7+ call sites across the codebase to read from the validated Settings singleton instead of `os.environ`.

The plan represents a substantial, cross-package refactor anchored on the `2026-05-14-settings-di-research` and `2026-05-14-settings-di-adr` findings, which identified 27 production `os.environ` reads, categorised them, and selected Strategy 3 (`ContextVar`-backed override) as the DI path forward. All steps were marked complete in the plan document, but the work was never committed to the main branch and execution did not land. The plan explicitly notes deferral to a follow-up sprint.

## Forces in Tension

- **DI refactor scope** — the migration spans 10+ files across `core/config`, `core/i18n`, `core/logging`, `core/access_gate`, `domain/calculations/registry`, and `adapters/persistence`. Execution requires coordination and a clear phase dependency graph (P02 depends on P01, P04 depends on P02.S05, etc.). The scope is non-trivial for a solo agent.

- **Live-write perimeter integrity** — the `aeat_master_key_passphrase` field addition is security-sensitive: it must remain `None` by default and the fail-closed branch must raise identically to the current unset-env path. The research document explicitly warns that a truthy default would be a security regression.

- **Test-side mechanical migration deferred** — the plan notes 223 `monkeypatch.setenv` sites in the test suite that would benefit from the `override_settings()` helper, but sequencing this as a follow-up sprint keeps the first sprint focused on the production-side foundation (3 new Settings fields + override helper + 7 call-site migrations). Test migration is explicitly out of scope for this deferral.

- **Concurrent campaign load** — at the time the plan was authored (2026-05-14), other campaigns (executable-parity-evidence gate hardening, cross-domain continuity work, documentation-surface closure) were active and consuming agent capacity. Deferral to a dedicated DI-focused sprint allows the Settings refactor to proceed with full attention in its own campaign boundary.

## Decision

The `settings-di` plan is **accepted as architecturally sound** (the research is thorough, the ADR decision is well-grounded, the plan phasing is clear) but **deferred explicitly to a follow-up sprint** scheduled after the current campaign cluster closes. The deferral preserves the full research, ADR, and plan as the blueprint for the follow-up execution; no architectural rework is needed.

## Consequences

- The existing 27 production `os.environ` reads remain in place and continue to work correctly. No regression.
- The follow-up sprint can pick up the `2026-05-14-settings-di-plan` wholesale, with no changes to its phase or step structure, because the research findings and ADR decision are stable.
- Test-side migration of the 223 `monkeypatch.setenv` sites is sequenced as a second follow-up sprint (after the production-side foundation lands), keeping the focus tight.
- Future agents resuming this work have the full historical audit trail: research rationale, ADR decision, phase dependencies, fail-closed contracts (especially the master-key passphrase branch), and the test-side scope boundary.

## Successor Plan

Follow-up sprint: `[[2026-06-XX-settings-di-execution-plan]]` (to be authored when the campaign cluster closes and DI work is queued). The successor plan will inherit the phase structure and step inventory from `[[2026-05-14-settings-di-plan]]` without modification.

