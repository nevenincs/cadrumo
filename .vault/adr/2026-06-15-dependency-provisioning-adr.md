---
tags:
  - '#adr'
  - '#dependency-provisioning'
date: '2026-06-15'
modified: '2026-10-29'
body_hash: 'sha256:231a479cd98fe0457dd626b0e13a57a2c535534f3f0f590182c9e1a4e899f5c0'
related:
  - "[[2026-06-15-service-capabilities-research]]"
  - "[[2026-06-15-service-capabilities-adr]]"
  - '[[2026-07-06-dependency-provisioning-research]]'
---
# `dependency-provisioning` adr: `Dependency management and graceful degradation: a missing dependency is a typed point-of-use refusal` | (**status:** `accepted`)

## Problem Statement

The application's external dependencies must fail cohesively. The OS keychain,
Google export and ECB FX degrade gracefully (typed refusals, fallbacks), and the
Playwright browser-missing case is typed. A dependency that is absent at the moment
an operation needs it must never surface as a raw `httpx.ConnectError` traceback,
and never as a silent no-op. This is the companion to the profile-capabilities ADR:
a service runs only when (capability opted-in) AND (safety posture permits), and the
operation then refuses at the point of use if the dependency is not there.

## Considerations

- The in-tree graceful-degradation references are strong: the keychain provider's
  `KeyringUnavailableError` + file fallback, the Google `GoogleAuthError` →
  locale-rendered `_google_refusal`, and the subprocess-CLI typed pre-check. Every
  other dependency path matches these rather than inventing a new pattern.
- Diagnostics belong on the typed `Notice`/refusal channel
  (`cli-notices-are-the-only-diagnostic-channel`); a missing dependency is an
  instructive refusal, never a stack trace and never a silent no-op
  (`no-silent-under-declaration`).
- `src/cadrumo` is a tax calculation engine, not a dependency platform. It does not
  check, probe, diagnose, size hardware for or report the readiness of any
  third-party dependency: the AEAT browser, Ollama, models, model lanes or optional
  extras. The desktop owns dependency readiness and setup.
- `torch` is a ~GB CUDA core dependency that **no runtime path imports** (deptry
  DEP002-suppressed) — it exists only for the dev-only vaultspec-rag pin. Carrying
  it in `[project.dependencies]` bloats every install (`aeat-source-hygiene`,
  `no-legacy-compatibility` spirit: don't ship dead weight).

## Constraints

- The shared-Windows-worktree exe-lock hazard forbids `uv sync` in `bootstrap`
  (documented); provisioning recipes must stay additive (`uv pip install`).
- Live AEAT writes remain permanently forbidden (`aeat-safety-legal-gates`).
- A refusal is raised only when the operation actually reaches the dependency. No
  operation spends time on a pre-flight check of a dependency it may not need.
- Parent surfaces (the LLM client/adapter, the browser session, the justfile, the
  CLI config surface) are shipped and stable; this layers additively.

## Implementation

**Decision: one cohesive missing-dependency contract — a dependency that is
unavailable when an operation needs it is a typed refusal/Notice that names the
missing dependency and nothing else — and a pyproject with a capability-mapped
extras structure over a lean core.**

1. **Typed refusal at the point of use.** When a call reaches an unavailable
   dependency, the adapter raises a typed refusal that the CLI renders as an
   instructive `Notice`. The refusal names the missing dependency (the browser, the
   optional extra, the agent's own refusal) and names no command, no application
   and no setup step. Availability is never probed ahead of the call, never
   aggregated into a report and never exposed as a status row.

2. **Browser refusal.** The `BrowserError(BROWSER_LAUNCH_FAILED)` message names the
   missing browser when the failure is browser-not-installed.

3. **Optional extras.** The capability-mapped `[project.optional-dependencies]`
   extras (`google`, `browser` and others) sit over a lean core. Each
   library is imported lazily, and the feature that needs it raises
   `MissingOptionalExtraError` naming the missing extra when it is absent.

4. **pyproject torch relocation.** `torch` is the vaultspec-rag embedding backend —
   no `src/cadrumo/` runtime path imports it — so it lives in
   `[dependency-groups].dev`, which vaultspec-rag's `torch_config` accepts as a valid
   direct-dep location (PEP 735). The `[tool.uv.sources]` cu130 pin still applies
   and `just install` (dev group) still provisions it for contributors.

## Rationale

The graceful paths already in the tree are the template. Routing every
missing-dependency outcome through the typed refusal/Notice channel (not a
traceback, not a silent skip) satisfies `cli-notices-are-the-only-diagnostic-channel`
and `no-silent-under-declaration`. Mapping extras to capabilities makes the install
surface mirror the runtime opt-in surface. Keeping the refusal at the point of use
leaves the tax engine with no dependency-management surface to maintain.

## Consequences

- An operation that reaches a missing dependency refuses instructively instead of
  crashing.
- The default install stays lean because integrations sit behind extras.
- The `torch` relocation must be verified against the vaultspec-rag dev workflow so
  contributors' RAG still installs.

## Codification candidates

- **Rule slug:** `missing-dependency-is-a-typed-refusal`.
  **Rule:** When an external dependency (a Playwright browser, Google credentials,
  an optional extra, a provider CLI) is unavailable at the point of use, the runtime
  MUST surface a typed refusal / `Notice` that names the missing dependency, never a
  raw stack trace and never a silent no-op, and MUST NOT probe or report dependency
  availability outside that refusal.

## Amendment: component setup belongs to the desktop

Setup and readiness of the browser and the local AI belong to the desktop
application, driven by the native engine
(`2026-10-18-dependency-provisioning-unified-setup-adr`,
`2026-10-24-rust-component-provisioning-adr`). A missing component shown to a person
is one plain sentence and one action in the desktop's provisioning panel.
