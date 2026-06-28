---
tags:
  - '#adr'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-google-auth-ux-research]]'
  - '[[2026-04-16-google-workspace-mcp-auth-adr]]'
---

# `google-auth-ux` adr: `kent-first-google-authentication-ux-contract-for-cli-mcp-bootstrap` | (**status:** `accepted`)

## Problem Statement

The current Google authentication journey is split across bootstrap recipes, `aeat oauth-client init`, gcloud login steps, MCP launch behavior, and `aeat doctor`. Kent cannot follow that journey reliably without inferring hidden dependencies from source code, prior ADRs, or trial-and-error. The existing operator story also exposes multiple overlapping credential concepts at once, which makes it unclear which path is primary, which artifacts are optional, and which failures actually block progress.

The architectural problem is to contract one Kent-first, user-facing authentication UX for CLI, MCP, and bootstrap before any further implementation proceeds. That contract must let Kent complete setup without reading Python, must explain each step in plain operational terms, and must end in an explicit verification gate that proves the chosen auth path is ready.

## Considerations

- The Kent journey audit established that bootstrap ordering, hidden prerequisites, and ambiguous `doctor` output already create first-run failure points for a non-developer operator.
- Prior Google Workspace MCP auth work established two durable technical facts that the UX must respect: secrets stay in gitignored local paths, and MCP credential state must remain isolated per worktree.
- The current repo and docs still speak in three Google credential paths, but for a human operator that is the wrong abstraction. Kent needs to choose an operator intent, not reason about internal token formats.
- Desktop OAuth already maps to the local-dev, human-at-a-workstation use case. Service-account credentials already map to automation and server-oriented flows. Those are the two operator stories that matter.
- ADC may still be required for some bootstrap and Google client-library behavior, but that should be treated as a derived sub-step inside the chosen path, not as a third peer path Kent must evaluate.
- `aeat doctor` is already the authoritative health surface and must remain the final proof point, but it currently does not explain active path, cache ownership, or stale optional configuration clearly enough for Kent.
- The contract must cover the full user journey across CLI, MCP, bootstrap, and final diagnostics. A partial fix in one surface would preserve the current fragmentation.
- This ADR is intentionally architectural and user-facing. It specifies the UX contract and acceptance bars, not a patch-level implementation.

## Constraints

- The user-facing narrative must support exactly two named auth paths:
  - Desktop OAuth local-dev
  - Service-account automation
- Desktop OAuth local-dev is the primary local development path for Kent and any human operator on a workstation.
- Service-account automation remains the automation and server-oriented path.
- ADC may exist technically, but it must not appear as a third named auth path in the operator narrative. If required, it is explained as a named subordinate step inside the Desktop OAuth local-dev flow.
- One guided entrypoint must own sequencing across env setup, project validation, OAuth client import, token acquisition, optional ADC acquisition if required, MCP readiness, API enablement, bootstrap, and final `aeat doctor`.
- Every user-facing auth message must explain:
  - why the step exists
  - the exact action Kent must take
  - the expected file, value, or browser result
  - what command to run next
- `aeat doctor` and related diagnostics must become active-path-aware and report CLI OAuth cache, MCP OAuth cache, ADC, and stale optional config as separate surfaces.
- Secret-bearing values must remain outside tracked files, and repo-local credential caches must remain isolated in gitignored paths.
- Existing auth commands and recipes must not remain free-floating after the new flow lands. Each existing surface must become either the primary guided entrypoint, a compatibility wrapper that redirects to it, or an internal implementation detail removed from Kent-facing guidance.
- No implementation should proceed beyond UX scaffolding until the proposed flow is validated against explicit operator checks and acceptance bars.

## Implementation

### User-facing auth contract

The product will present exactly two named auth paths everywhere user-facing copy appears: CLI help, onboarding text, bootstrap guidance, and diagnostics summaries.

`Desktop OAuth local-dev` is the primary path for a human operator on a fresh workstation. This path owns the browser-based setup story, including project validation, OAuth desktop client import, user consent, any required supporting ADC acquisition, CLI readiness, MCP readiness, bootstrap, and final verification.

`Service-account automation` is the automation path. This path owns service-account key validation, any required impersonation context, MCP readiness, bootstrap compatibility checks, and final verification.

All other credential artifacts are subordinate evidence within one of those two paths. They are not separate operator choices.

### Supporting ADC sub-step

If ADC acquisition remains necessary for gcloud-managed tooling or specific bootstrap surfaces, the product must present it as a named subordinate step inside `Desktop OAuth local-dev`, not as a third auth path.

That step must state:

- why ADC is still needed
- which exact surfaces it unlocks
- that Kent is still on the Desktop OAuth local-dev path
- what success looks like
- what exact command comes next

The UX must never imply that Kent needs to compare or choose between Desktop OAuth and ADC as peer paths.

### Guided entrypoint concept

A single guided entrypoint will orchestrate the full Google-auth readiness flow. The final command name may be chosen later, but the contract is fixed: Kent enters once, picks or confirms one of the two named paths, and is then led through every required step in order.

That entrypoint must handle, in sequence:

- env setup and project validation
- import or validation of the path-specific credential input
- token acquisition or refresh
- MCP readiness and cache preparation
- API enablement checks
- bootstrap steps when needed
- final `aeat doctor`

For Desktop OAuth local-dev, the guided flow must explicitly tell Kent when to open the browser, when to create or download the OAuth desktop client JSON, where that JSON is expected to land locally, what value must be written into local config, and what command comes next.

For Service-account automation, the guided flow must explicitly tell the operator what key file is expected, what config value must point at it, whether an impersonation email is expected, what local readiness check is being performed, and what command comes next.

### Legacy command disposition

The existing auth commands and recipes are part of the current confusion and cannot be left semantically ambiguous once the guided entrypoint exists.

- The primary guided entrypoint becomes the only auth command described as the normal Kent-facing setup path.
- Existing surfaces such as `just bootstrap`, `just gcloud-auth`, `just gsuite-oauth-client`, and `aeat oauth-client init` must become one of:
  - a redirecting compatibility wrapper that points to the guided entrypoint
  - a deliberately documented sub-step invoked by the guided flow
  - an internal implementation detail removed from Kent-facing docs
- No legacy command may keep standalone user-facing copy that contradicts the guided flow.

### Message contract

Every auth step must answer these operator questions in order:

- Purpose: why this step exists in the journey.
- Action: the exact thing Kent must do now.
- Source: where Kent gets the required file, value, or account context.
- Browser: what browser behavior or consent flow should happen next.
- Success: the file, value, cache, or browser outcome that should now exist.
- Continuation: the exact next command to run.

Messages must be Kent-facing, stepwise, and free of source-code assumptions. They must not require the operator to infer whether a step is optional, path-specific, or stale from status words alone.

### Diagnostic contract

`aeat doctor` becomes the final readiness proof for the active auth path and must state that path explicitly at the top of its output.

Doctor and any supporting auth diagnostics must report these surfaces separately:

- active path
- Desktop OAuth client material
- CLI OAuth cache
- MCP OAuth cache
- ADC state
- service-account key state
- stale optional config from the inactive path
- bootstrap/API readiness

These surfaces must not be collapsed into one generic "Google auth" result. The operator must be able to tell whether the problem is:

- the CLI cache
- the MCP cache
- ADC acquisition
- inactive-path leftovers
- bootstrap/API readiness

`SKIP` and equivalent states must become explicit. They must say whether something is "not required for the active path", "not configured yet", or "configured but stale and ignored". Kent must not have to guess.

### Path resolution rules

The auth UX contract requires deterministic precedence across CLI, bootstrap, MCP, and diagnostics.

- If both path families are configured and the system cannot safely infer one active path, the state is blocking until a path is chosen explicitly.
- If the active path is selected but one of its required artifacts is missing, the state is blocking.
- If the inactive path has stale artifacts, the state is advisory and labeled ignored for the current path.
- If CLI/bootstrap readiness is complete but MCP readiness is incomplete, the state is partial success.
- If MCP readiness is complete but CLI/bootstrap readiness is incomplete, the state is partial success.
- The precedence and state labels must be identical across the guided flow, wrappers, and `aeat doctor`.

### Verification-first scaffold

No implementation should be considered ready to continue until the UX scaffold itself passes explicit operator validation.

The acceptance bars are:

- A fresh-clone Kent can identify the correct path from the first auth screen without reading repo source or opening implementation files.
- For every step, an independent reviewer can answer all four questions: why this exists, what exact action to take, what evidence to expect, and what to run next.
- The Desktop OAuth local-dev path can be followed end-to-end without branching into a separate MCP guide or separate bootstrap guide.
- The Service-account automation path can be followed end-to-end without leaking Desktop OAuth instructions into the primary story.
- The final diagnostic output lets an operator identify, without ambiguity, whether CLI OAuth cache, MCP OAuth cache, ADC, or stale optional config is the failing surface.
- If any of these checks fail, implementation pauses and the UX scaffold is revised before code expansion continues.

### Executable verification requirement

Human review alone is insufficient. Before implementation proceeds, the UX scaffold must define executable verification for:

- path selection and mixed-state precedence
- stale-config diagnosis
- CLI-ready plus MCP-not-ready and MCP-ready plus CLI-not-ready splits
- exact readiness labels in diagnostics
- legacy wrapper redirection behavior
- final active-path success summaries in `aeat doctor`

## Rationale

This decision reduces the operator problem to the two real human choices in the system: a person on a workstation, or an automation context. That is the correct Kent-facing abstraction. Preserving ADC as a technical artifact while removing it as a peer narrative choice lowers cognitive load without removing any underlying capability.

A single guided entrypoint solves the current fragmentation between CLI auth, MCP auth, bootstrap, and doctor. Kent should not have to reconstruct ordering from multiple commands or know which credential cache belongs to which subsystem. The product should own that sequencing.

Making diagnostics active-path-aware is the only way to turn `aeat doctor` into a trustworthy operator tool for this domain. The current blended view hides whether a failure is in the active path or in stale optional configuration. Separating the caches and readiness surfaces makes remediation explicit.

Requiring verification before implementation prevents the repo from hardening a technically correct but operator-hostile auth journey. This ADR intentionally prioritizes clarity of operator experience over incremental code-first changes.

## Rejected Alternatives

- Keep the current three-path user narrative of ADC, OAuth Desktop, and Service Account. Rejected because it exposes implementation mechanics as operator choices and forces Kent to reason about internals before he can start.
- Keep separate entrypoints for CLI auth, MCP auth, bootstrap, and final doctor. Rejected because that preserves hidden ordering dependencies and repeats the current fragmented journey.
- Make `aeat doctor` path-agnostic and report one blended Google-auth verdict. Rejected because it conceals which cache or subsystem is actually broken and leaves stale optional configuration indistinguishable from active-path failures.
- Implement the flows first and improve wording later. Rejected because the wording, ordering, and verification contract are the architecture here; postponing them would make Kent the integration test.

## Consequences

- Existing user-facing guidance that presents three peer Google auth paths is superseded by this two-path contract.
- Future implementation work must coordinate CLI, MCP, bootstrap, and doctor as one operator journey rather than as separate features with separate copy.
- Desktop OAuth becomes the explicit primary local-dev story even if some sub-steps still acquire ADC under the hood.
- If ADC remains technically necessary, it must be framed and tested as a subordinate Desktop OAuth sub-step rather than a peer operator choice.
- Service-account automation remains supported, but its operator story becomes clearly separate from the human local-dev path.
- `aeat doctor` and related diagnostics gain more structure and more explicit cache ownership reporting.
- Existing auth commands and recipes lose permission to carry independent contradictory copy; they must redirect, subordinate themselves, or disappear from Kent-facing guidance.
- The project takes on upfront UX-validation work before further implementation proceeds, which slows short-term coding but reduces long-term operator confusion and support burden.
- Earlier decisions about repo-local secret handling and worktree-local MCP cache isolation remain in force; this ADR narrows and clarifies how those decisions are presented to operators.
