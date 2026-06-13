---
tags:
  - '#research'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-16-google-workspace-mcp-auth-research]]'
  - '[[2026-04-16-google-workspace-mcp-auth-adr]]'
---

# `google-auth-ux` research: `kent-first-google-authentication-ux-for-cli-mcp-bootstrap`

This research audits the current Google authentication journey across `justfile`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`, `src/aeat/entrypoints/cli/oauth.py`, `src/aeat/entrypoints/cli/doctor.py`, `src/aeat/entrypoints/cli/bootstrap.py`, `src/aeat/entrypoints/mcp/launch_google_workspace.py`, `README.md`, `CONTRIBUTING.md`, `env/.env.example`, and the live operator journey executed on 2026-04-21. The goal is to define a Kent-first UX contract for CLI, bootstrap, and MCP readiness, not an implementation patch sequence.

## Findings

### 1. The shipped promise is simpler than the real operator path

`just bootstrap` still advertises a one-command setup path, but the 2026-04-21 live journey proved the real path is materially longer: provision `env/.env`, create a GCP project, manually create an OAuth Desktop client in Cloud Console, download the JSON, import it with `aeat oauth-client init --json`, then run `just gcloud-auth`, enable APIs, run `aeat bootstrap`, and finally run `aeat doctor`.

This is not a copy bug. `just gsuite-bootstrap` calls `just gcloud-auth`, and `gcloud-auth` hard-fails until `env/oauth-client.json` already exists. The one-command story therefore breaks on the first real workstation.

### 2. The docs say ADC-first, but the runtime becomes OAuth-first once OAuth vars exist

`README.md` still frames Application Default Credentials as the default local-development path and Desktop OAuth as optional. The resolver in `aeat.adapters.outbound.aeat.auth.get_credentials()` does not match that story. Its order is service account, then OAuth desktop, then ADC. Once `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are present in `env/.env`, the CLI stops behaving like an ADC-first product.

The operator is therefore given two different truths:
- docs truth: ADC is the default path
- runtime truth: OAuth wins as soon as OAuth client values exist

That mismatch is load-bearing. Kent cannot debug it from the command line.

### 3. There are three overlapping auth stories with different files, tokens, and success conditions

The repo currently exposes three separate Google auth surfaces:
- `gcloud` / ADC in the well-known gcloud credential store
- repo-local CLI OAuth tokens in `.tokens/google_oauth_token.json`
- repo-local MCP credentials in `env/workspace-mcp-credentials`

These surfaces are not interchangeable. `aeat bootstrap` and `aeat doctor` validate the CLI path selected by `aeat.adapters.outbound.aeat.auth`, while `aeat.entrypoints.mcp.launch_google_workspace` uses a different upstream contract and a different credential cache. A successful CLI bootstrap does not prove MCP readiness. A healthy ADC file does not prove the repo-local OAuth token exists. A working MCP cache does not prove the CLI is using the same path.

### 4. `just gsuite-oauth-client` is an instruction printer, not an end-to-end setup path

`aeat oauth-client init` prints the Cloud Console URL, the required fields, and the next command. Without `--json`, it completes no setup work. Even with `--json`, it only copies the downloaded JSON into `env/oauth-client.json` and writes env vars into `env/.env`. It does not create the Cloud project, does not create the OAuth client, does not confirm the operator downloaded the right file, and does not explain the full downstream chain.

The current naming suggests a completed setup step. The real behavior is guided manual provisioning.

### 5. `just gcloud-auth` is not a pure gcloud step

The recipe name implies "sign into gcloud." The real behavior is "sign into gcloud after manually provisioning a separate OAuth Desktop client, because Google blocks the required Workspace scopes on gcloud's built-in client." It also depends on `GOOGLE_CLOUD_PROJECT` already being set correctly.

That hidden prerequisite matters. Kent cannot infer from the command name why a downloaded JSON file is required first, why a browser will open multiple times, or why the step fails if the project value is missing.

### 6. `aeat doctor` is informative, but not path-aware enough

`aeat doctor` does surface useful rows, but it mixes active-path truth with advisory noise from inactive paths. `check_credentials_path()` identifies one active path, yet the table still includes `ADC file`, `ADC scopes`, `service account`, and `oauth desktop` rows regardless of which path is actually in use. That is acceptable for contributor diagnostics, but it is not a Kent-first diagnosis surface.

The result is a table that can be technically correct and still operationally confusing. The operator can see warnings or skips for paths they are not using, while the actual next remediation step remains implicit.

### 7. MCP readiness is a separate contract that the current UX does not name clearly

`aeat.entrypoints.mcp.launch_google_workspace` supports only a complete Desktop OAuth configuration or a service-account key path. It does not expose ADC as a supported MCP launch path. It also writes refresh-token state to `env/workspace-mcp-credentials`, which is distinct from both ADC and the CLI OAuth token cache.

The already-recorded execution evidence shows the consequence: CLI bootstrap and `aeat doctor` can pass while a real `workspace-mcp` Drive tool call still needs the OAuth client path. The current UX therefore allows the operator to believe "Google auth is done" when only the CLI half is done.

### 8. The current copy does not consistently answer Kent's basic questions

Across `README.md`, `env/.env.example`, `justfile`, and the CLI messages, the operator is not told consistently:
- why a tax tool needs Google auth
- what each step is doing
- where the required values or files come from
- what browser flow is about to happen
- what success looks like
- what exact next command to run

`CONTRIBUTING.md` now centers Kent, but the Google auth surface still speaks in contributor and platform terms. The journey still assumes the operator can mentally reconcile Cloud Console, gcloud, repo-local env, CLI token caches, and MCP launch semantics.

## Design Principles

- The public contract must expose one local-default path and one automation path, not three competing stories.
- The selected auth path must be explicit at every operator touchpoint.
- Inactive-path diagnostics must never drown out the active next step.
- CLI readiness and MCP readiness must be reported separately.
- Every step must explain purpose, required inputs, browser side effects, success signal, and exact next action.
- Repo-local secret surfaces must remain explicit and bounded.
- User-facing truth must match resolver truth. If runtime priority differs from docs, the docs are wrong.

## UX Requirements

- The supported operator contract must be reduced to exactly two named paths:
  - Desktop OAuth local-dev path
  - Service-account automation path
- Desktop OAuth must be the clear local default for Kent-facing setup.
- ADC may remain an internal compatibility mechanism, but it must not be presented as a first-class supported operator story unless CLI, bootstrap, and MCP all genuinely align on it.
- If ADC acquisition is still required inside the Desktop OAuth local-dev path, it must be an explicitly labeled subordinate step. The UX must state what surface it unlocks, why Desktop OAuth alone is insufficient for that surface, and that ADC acquisition is not a third path Kent must choose.
- The first Google-auth entrypoint must begin by telling the operator why Google auth is required and which of the two supported paths they are entering.
- Every guided step must state:
  - what the step does
  - what file, value, or account is needed
  - where to find it
  - whether a browser will open and for which account
  - what success looks like
  - the exact next command to run
- Existing auth commands and recipes must be classified explicitly as one of:
  - the primary guided entrypoint
  - a compatibility wrapper that redirects to the guided entrypoint
  - an internal implementation detail that Kent is not expected to run directly
- The bootstrap contract must make clear that scratch-resource creation is CLI/bootstrap readiness, not MCP readiness and not proof that the operator's real Drive data surface is ready.
- The doctor contract must report:
  - active auth path
  - CLI/bootstrap readiness
  - MCP readiness
  - stale or conflicting config
  - one exact next remediation step
- Mixed state must be handled explicitly. Examples include:
  - OAuth vars present plus stale ADC file
  - service-account path present plus missing file
  - both Desktop OAuth and service-account values configured
  - CLI-ready state with MCP-not-ready state
- Success messages must be terminal. The operator should never have to infer the next step from a table or from source code.

## Deterministic Resolution Rules

The future UX cannot stop at "handle mixed state explicitly." It needs normative precedence so all surfaces converge on the same answer.

- If both path families are configured and the active path cannot be inferred safely, the state is blocking until the guided flow or the operator chooses one path explicitly.
- If the active path is selected but one of its required artifacts is missing, the state is blocking and the UX must show one exact remediation step.
- If the inactive path has stale artifacts, the state is advisory and the UX must say that those artifacts are ignored for the current path.
- If CLI/bootstrap readiness is complete but MCP readiness is incomplete, the state is partial success, not full success.
- If MCP readiness is complete but CLI/bootstrap readiness is incomplete, the state is partial success, not full success.
- Every surface that reports auth readiness must use the same precedence order and the same labels for blocking, advisory, ignored, and partial states.

## Options Considered

### Option 1: keep the current ADC-first public story and only improve wording

Reject. It leaves the core contradiction intact: docs say ADC-default while the resolver prefers OAuth once OAuth vars exist, and the MCP launcher does not support ADC as a named operator path.

### Option 2: keep all three paths as equal supported stories

Reject. This preserves flexibility for contributors but keeps Kent in a branchy decision tree with three token stores, three success models, and no single default. It optimizes for technical completeness over operator clarity.

### Option 3: define two explicit supported paths and make Desktop OAuth the local default

Accept. This matches the observed reality better than the current docs, aligns with the existing MCP launcher constraints, and gives Kent a simple decision: local workstation or headless automation.

## Recommendation

Adopt a two-path public contract.

For local workstation use, the supported story is Desktop OAuth. That path must cover the full operator journey from credential creation through CLI bootstrap and through explicit MCP readiness. For automation, the supported story is service account. That path must remain clearly separate, headless, and explicit about its limits.

Under this contract, "Google auth complete" becomes a layered statement:
- CLI/bootstrap ready
- MCP ready

Both states must be surfaced separately. A passing CLI bootstrap or `aeat doctor` result must never imply MCP readiness unless the MCP contract has been verified too.

The required shift is not primarily new commands. It is truthfulness. The repo should stop telling Kent that Google auth is a one-command ADC-first setup when the lived path is manual Desktop OAuth provisioning followed by multiple distinct readiness checks.

## Verification Scaffold

Before coding, the proposed UX should be validated against a scripted operator journey and message review.

### Operator-Journey Checkpoints

- Fresh clone: Kent can explain, in one sentence, why Google auth is needed before running any auth command.
- Path selection: Kent can identify whether he is on the Desktop OAuth path or the service-account path without reading source code.
- Desktop OAuth setup: Kent can find the required Cloud Console page, create the correct client, import the JSON, and understand why the browser opens next.
- CLI bootstrap readiness: Kent can tell when scratch provisioning succeeded and what it does not prove.
- MCP readiness: Kent can tell whether the MCP launcher is ready independently of CLI success.
- Recovery: Kent can recover from a failed step using the message shown on screen, not a repository search.

### Message Review Criteria

Every operator-facing message in the selected path must answer:
- Why am I doing this?
- What is this step changing?
- Where do I get the required value or file?
- What browser behavior should I expect?
- What does success look like?
- What exactly do I run next?

### Stale-Config Drift Scenarios

The UX must be reviewed against at least these drift cases:
- stale ADC present while Desktop OAuth is the selected path
- stale OAuth vars present while service-account path is selected
- missing or moved service-account JSON
- both paths configured at once
- CLI token present but MCP credentials absent
- MCP credentials present but CLI path broken

Each case needs a deterministic active-path diagnosis and one explicit next action.

### Executable Verification

Human walkthroughs are necessary but not sufficient. The UX scaffold must also define executable checks that guard against future docs/runtime drift.

- Fixture-backed tests must cover active-path selection and mixed-state diagnosis.
- Fixture-backed tests must cover CLI-ready plus MCP-not-ready and MCP-ready plus CLI-not-ready splits.
- Auth diagnostics tests must assert the exact readiness labels for blocking, advisory, ignored, and partial states.
- Documentation or help-surface checks must assert that the named supported paths remain exactly two and that legacy wrappers point at the guided entrypoint.
- Any final `aeat doctor` success summary for the active path must be asserted in tests so message regressions are caught automatically.

### Success Criteria

- Kent can complete the local default path without needing to infer hidden prerequisites.
- The active auth path shown by docs, bootstrap, doctor, and MCP messages is the same path.
- Kent can tell the difference between CLI readiness and MCP readiness.
- No inactive-path advisory row obscures the active remediation step.
- The final success state names the exact surfaces that are ready.

### Failure Criteria

- Kent must guess which auth path is actually active.
- A command name hides a required prior manual step.
- CLI success is presented as MCP success.
- The next action is only inferable from source code or prior project knowledge.
- Docs and runtime still describe different defaults.
