---
tags:
  - '#adr'
  - '#live-agent-evaluation'
date: '2026-10-12'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:163e2f956d3fc2f22f426ac1a449cbea658064e6d24427f00aab77a48d27dd21'
related:
  - "[[2026-10-12-live-agent-evaluation-reference]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-07-03-agent-harness-operability-followup-audit]]"
  - "[[2026-10-11-mcp-parity-full-parity-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
  - "[[2026-10-03-application-packaging-interpreter-foundation-adr]]"
  - "[[2026-10-07-application-distribution-windows-versioned-msi-adr]]"
  - "[[2026-08-14-test-harness-sanity-successor-adr]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
---

# `live-agent-evaluation` adr: `live agent evaluation runs an agent client over MCP against a verified copy of the built package` | (**status:** `accepted`)

## Problem Statement

`2026-07-02-agent-harness-refoundation-adr` R7 chose live measurement: a real `cadrumo-mcp`, a real MCP client session driven by a language model, the trajectory captured and scored against golden scenarios, with zero submission attempts as a hard invariant. The scoring half was built in `dev/agent_eval`. Nothing in the repository drives it (`2026-10-12-live-agent-evaluation-reference`). A live agent has twice operated Cadrumo end to end from throwaway tooling: on 2026-07-03 through the command line (`2026-07-03-agent-harness-operability-followup-audit`), and on 2026-10-12 through MCP against a real runtime. On 2026-10-12 the agent signed in, booked ledger rows, and created, calculated, verified and exported Modelo 130. Both runs found defects the suites had missed. On 2026-10-12 these were a search deadline that ended the session, verify and export disagreeing on IVA, and oversized replies. Neither run left anything that can be run again. The second run also put the profile password, and a host messaging token, into files it kept.

The owner, 2026-10-12: "I'm concerned that you set up a non-reproducible adhoc testing system that is good on paper and useful but not actually part of the project, yet it is crucial." On the scratch files: "I don't know what is in the scratch file. It should be clear from my ask that I want the real test not to be lost and reproducible."

## Considerations

- The owner's rulings, first-hand and verbatim, 2026-10-12:
  - On where the harness runs and how the runtime is stood up: "I'd suggest the we test against the cmake built actual cadrumo environment - that is the most honest manner of operating, The agent work must rest on the actual cadrumo env and we already build and ship the python and packaged deps. It is our python environment. The runtime is NOT managed by default but cadrumo and the runtime manager are part of the application package. So the cmake has an package target that is not zipped or an install but the binary composition of the python interpreter, python deps, and the cadrumo apps and binaries (runtime and manager). I don't want us to modify the build artefacts but using it as a copy perhaps to set up our agent testing? Ask the opus agent about opinion."
  - On the agent driver: use the easiest available route, a provider credential from the environment when present, otherwise an authenticated client already on the host, with a small, inexpensive model.
  - On secrets: "we should not let passwords and secrets travel in the transcript or leave the local machine. There's a design concern if the user is required to enter the password to the agents. this should never happen. In the cadrumo tui app the user should manually login and authenticate and the agent should always operate against an unlocked authed profile and ask the user to authenticate if the profile locked or does not exist."
  - On API keys: "Do not retire API keys. API keys are outside of what I just descripbed. API keys give access to the agetns cli tui, etc access to a spcific user profile. For testing, you should explciitly exercie acpi keys to verify we can access and manage access = I'm assuming the runitme manages the api access also?"
  - On scenarios, oracles, lane and cadence as proposed here: "lgtm". On a platform matrix: "do not work on this."
- The owner's stronger ruling on the agent's place inside a signed-in profile is recorded by a separate `mcp-parity` record, topic `agent-inside-the-signed-in-profile`, which is being written alongside this one and governs it. It amends the earlier MCP sign-in and secret wording. As relayed:
  - The agent never authenticates or manages authentication.
  - MCP is admitted only by resuming the person's live sign-in, or by an enrolled API key configured by reference.
  - No password or secret ever travels in a tool call or transcript.
  - Without a live sign-in or a valid key the agent does not run.
  - One profile is active and signed in at a time.
  - An agent session that times out is a logout.
  - The agent never sees data outside its profile.

  This record does not restate or amend those rulings. It holds its own lane to them.
- Yes, the runtime manages API access. `2026-09-26-mcp-purpose-authentication-profile-access-adr` binds each key to a durable grant. The grant is bound to profile, installation, OS owner, client, scopes, data projections, validity and custody generations. The server retains only a verifier and protected grant state. A key admits a fresh, bounded session of at most five minutes, and revocation fences admission, data release and commit. The same record excludes runtime start and stop management from that scope. In code:
  - The runtime's profile host resolves a presented key to its grant and scope before the access authority admits a lease (`src/cadrumo_runtime/host/profile_connection_sessions.py:128-147`).
  - The runtime serves the grant inventory (`src/cadrumo_runtime/host/operation_authority.py:235`).
  - The person issues, approves, denies, locks and resumes keys through `config automation` (`src/cadrumo/entrypoints/cli/config/runtime_access_management_specs.py:52-317`).
  - `cadrumo-mcp` takes `--profile-id` and `--credential-reference` to run on an enrolled key (`src/cadrumo_harness/mcp/main.py:43-52`).
  - Enrollment, revocation and lock are already proved with scripted clients (`dev/agent_eval/tests/test_installed_mcp_first_enrollment.py`, `test_mcp_revocation_runtime.py`, `test_runtime_automation_grant_lock_parity.py`). None of them is proved with a live agent.
- The package the owner means is the CMake `bundle` target: `build/<preset>/stage/<Config>/app`. It holds the interpreter, the locked dependencies, `bin/aeat.exe`, `bin/cadrumo-mcp.exe`, `bin/cadrumo-runtime.exe`, `cadrumo-manager.exe` and the bundled authority. Its own `data/package-manifest.json` hashes every file, and `dev/packaging/native/installation.py:51-57` already checks a payload against that manifest. `dev/packaging/native/platforms/windows_verify.py:270-320` already copies a package and runs it on a temporary storage root.
- The staged package on this host is from 2026-10-08. Of 3 284 first-party modules in it, 307 differ from `src/cadrumo`. A package run measures the package, not the checkout, unless the run checks that the two match.
- The manager launches the packaged runtime with `--storage-root`, `--storage-identity`, `--expected-version` and `--supervised`. It uses a cleared, allow-listed environment pinned to `P/data/authority` (`native/manager/src/supervision/launch.rs:138-164`, `native/manager/src/supervision/environment.rs:110-140`). The shipping manager manages only the canonical root. Override roots "stay developer-owned and unmanaged" (`2026-10-04-runtime-manager-architecture-adr`). The supervisor stream protocol belongs to the manager, and unsupervised test launches are unchanged by it (`2026-10-04-runtime-manager-architecture-supervisor-contract-adr`). The 2026-10-12 scratch host spoke that protocol, which made it a stand-in manager.
- MCP resume borrows the human sign-in receipt's proof from the platform credential store (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:1099-1135`). A logon session the store refuses (WinError 1312 under SSH) yields `custody_unavailable` (`src/cadrumo_harness/mcp/runtime_admission.py:64-66`). Under the secrets ruling, an agent run therefore needs a logon whose credential store works.
- Today MCP still accepts a password in several places, until the governing record's changes land:
  - the `session` tool takes a typed `secret` (`src/cadrumo_harness/mcp/protocol_contract.py:536-545`, `src/cadrumo_harness/mcp/runtime_adapter.py:679-693`)
  - `execute` and `installation` take typed secrets (`protocol_contract.py:426-427`, `:152`)

  The lane must hold the rule from its own side in the meantime.
- `child_environment(STRICT)` keeps every ambient name it does not clear (`src/cadrumo/core/storage_environment.py:672-684`). That is how a host token reached the scratch `mcp.json`. An environment handed to a model-driven client must be built from an allow-list.
- The `dev/agent_eval` claim that it imports only `cadrumo.core` is a docstring (`dev/agent_eval/__init__.py:12-21`). No import-linter contract enforces it, and the package already breaks it. No contract limits what `dev` imports from `src`.
- Verdict granularity follows determinism (`2026-08-05-ci-lane-deconflation-adr`). A harness lane is chosen by owned paths or recipe membership, not a cost marker (`2026-08-14-test-harness-sanity-successor-adr`). A gate carries positive controls (`2026-07-25-test-harness-honesty-adr`).

## Considered options

Where the agent's Cadrumo comes from:
- **A verified, unmodified copy of the CMake `bundle` package, its runtime started the way the manager starts it, unsupervised.** Chosen, as the owner proposed. It is the interpreter, dependencies, entry points and authority a person runs.
- **The development `.venv` and the worktree `.authority`.** Rejected as the measured environment. It is what the 2026-10-12 run used, and it tests something no person runs. It stays as the development loop for the harness's own code.
- **Running inside the staged directory itself.** Rejected. A run writes into the interpreter tree, and the owner ruled that build artefacts are not modified.
- **Supervision by the packaged `cadrumo-manager.exe`.** Rejected for the default run. The shipping manager owns only the canonical root and would contend with an installed manager on a developer host. The debug lifecycle driver (`dev/runtime_lifecycle/harness.py:49-116`, `fixture-test-mode`) runs the same supervision core on a test root. A supervised variant may use it when that driver is built. It is not part of the package, so its verdict is reported separately.

Where the harness lives (agent-product development ownership):
- **A `live` subpackage of `dev/agent_eval`, run by recipes and never collected by pytest.** Chosen as agent-product tooling, not tax/runtime authority. The R7 models, scorer, flywheel and report are already there.
- **A new top-level `dev` package.** Rejected. It splits R7 across two homes, and every `dev` package must be enrolled in `closed-dev-classification`.
- **A product-owned test-support module under `src`.** Rejected. The harness is development tooling, spends money, and drives a built package. `src` never imports `dev`, and nothing in `src` needs this harness.

The agent driver:
- **An agent client over the package's `cadrumo-mcp`, using whichever supported provider credential is configured.** Chosen, as the owner ruled. Which providers and models exist is not this record's to rule.

The sign-in:
- **The harness plays the person.** Chosen. The harness signs in through the product's command line on the protected secret channel, and the MCP server resumes that shared sign-in. In the API-key scenarios, the harness also issues and approves a key through `config automation` and starts the MCP server with `--profile-id` and `--credential-reference`. The agent never holds a password or a key.
- **A password in the prompt, scrubbed from the transcript.** Rejected by the secrets ruling. The password still reaches the model and the model provider.
- **The agent signing in by a reference named in its own tool call.** Rejected. The agent never authenticates.

## Constraints

Binding:

1. The live agent lane runs against an unmodified copy of the CMake `bundle` package. Before a copy is used, the staged package and the copy each have exactly the manifest's file set and digests. The harness never writes into the staged package. It discards a copy whose contents change.
2. The copy runs on a fresh storage root that the run creates and removes. The root is selected through the package's documented storage selection, with the package's own `data/authority`. The harness changes nothing inside the copy to point it there. The packaged runtime is launched with the manager's arguments, without `--supervised`, inside a kill-on-close process scope the harness owns. No login or boot registration is made. The operator's real storage, installed manager and installed runtime are never touched.
3. Each run records which build it measured: the manifest digest, the build metadata and the comparison of the packaged first-party modules with the checkout. A run against a package that differs from the checkout is refused, unless the operator explicitly asks to measure that package. In that case the receipt says so.
4. The model is declared by configuration and recorded per run with the id the provider reports. The driver uses whichever supported provider credential is configured. Each run records which driver ran. The agent's only tools are the cadrumo MCP server's. Each run has turn, token and spend limits.
5. No password, API key or other secret is ever given to the agent, travels in an MCP tool call or result, appears in a captured artefact, or leaves the machine. The harness acts as the person:
   - It signs the synthetic profile in through the packaged command line on its protected secret channel.
   - In the key scenarios, it issues and approves a key the same way, and the key is delivered to the client's protected store.

   The agent run starts only after that sign-in or key exists. The agent operates the resumed sign-in, or a key session configured by reference in the MCP launch configuration. A secret the harness holds lives only in its memory for that run.
6. The lane exercises access, not only work. Its scenarios include:
   - a run on the person's resumed sign-in
   - a run authenticated by a person-issued API key, configured by reference
   - an operation outside the key's scope, refused
   - revocation of the key during a run, after which the agent's next call is refused
   - a locked profile, refused
   - no sign-in, refused
   - an expired session, treated as a logout and refused

   In every refusal the oracle checks that nothing changed in the profile. The capture must show that the agent told the person to authenticate in Cadrumo, and did not try another way in.
7. The provider credential, the profile's Cadrumo API key and every host variable outside an allow-list stay out of the MCP server's environment, the runtime's environment and every artefact.
8. The verdict rests on an independent oracle: the packaged command line's JSON envelopes for ledger, work and history state, and the product's export parser for the exported bytes. The agent's narration is evidence of conduct, never of outcome.
9. Hard invariants, any one of which fails the run:
   - no call to an operation whose registered effect reaches the tax agency
   - no secret in any tool argument, result or kept artefact
   - no attempt by the agent to authenticate or to manage authentication
   - no disagreement between the oracle readings of the same fact
10. The lane is opt-in and runs only from its own recipe. It is never part of `gate-local`, `test-product`, `merge-gate.yml`, `release.yml` or any lane that collects `dev/agent_eval/tests`. When a model credential, a usable credential store or a current package is missing, the result is "unavailable" with a reason, never a pass.
11. Nothing remains in scratch. The scenario prompt, the profile creation, the isolated root, the agent run, the oracle checks and the redacted capture are all project code and data.

## Governing and affected records

- The `mcp-parity` record on the agent inside the signed-in profile (topic `agent-inside-the-signed-in-profile`) governs sign-in, keys and secrets on MCP. It owns the amendments to the earlier MCP sign-in and secret wording and the code changes they need. This record proposes none of them. It adds a `related` link once that record exists.
- Until those changes land, the lane holds the rule from its side. It never offers the agent a secret. It fails a run whose tool call or result carries one. It treats a password `sign_in` attempted by the agent as a conduct failure.
- `2026-07-02-agent-harness-refoundation-adr` R7 is refined, not changed: this lane is its substrate. `2026-09-26-mcp-purpose-authentication-profile-access-adr` is reused unchanged for what a key may do.

## Implementation

Agent-product evaluation tooling lives in `dev/agent_eval/live/`; it is independent of tax/runtime implementation and runs by two opt-in recipes:
- `just eval-agent-floor` runs the scenario with a scripted MCP client and no model.
- `just eval-agent-live SCENARIO RUNS` runs it with the live agent.

Each run carries the 2026-10-12 test into the project as follows:
- **Package copy.** Verify the staged `bundle` against its manifest. Copy it to the development build root. Verify the copy, and re-verify it after each run.
- **Isolated root.** Create a fresh root per run. Steps that touch storage run as the package's own code, through the copy's interpreter or command line: installation record, profile creation, sign-in, oracle reads and export parsing. The dev environment only orchestrates processes and reads JSON.
- **Profile and sign-in.** The deterministic person-side driver uses generic runtime admission/held session through the packaged runtime, with direct AEAT login/logout/profile-create retained only as explicitly authorized auth exceptions. Create a synthetic profile with a random password through `bin/aeat.exe` on `--secrets-stdin`. Sign in with `config login` on the same channel, which leaves the shared receipt (auth command/payload ownership now belongs to `src/cadrumo_runtime/commands` with the explicit direct AEAT exceptions). Remove the profile's credential-store receipt at teardown, as `dev/runtime_lifecycle/harness.py:229-249` does.
- **Scenario.** The prompt, profile facts, seeded or agent-entered ledger rows, required end state and oracle figures are declared in a live scenario file beside the golden scenarios. The prompt carries no secret.
- **Agent run.** The driver spawns `bin/cadrumo-mcp.exe` over stdio with an allow-list environment, offers only its tools to the model, with no other tools, no session persistence, no user settings and a spend limit, and records every call as a `LiveToolCallRecord`. Any temporary client configuration is private and deleted after the run. Every driver yields the same `LiveTrajectory`.
- **Oracle.** Read the ledger, work list and work history with `bin/aeat.exe --format json` on the protected channel. Parse the export with the product parser under the copy's authority. Compare all of them with the scenario's figures and with each other.
- **Capture.** Scrub in the stream before anything is written. Exact values are replaced: the run's password, the provider credential, the profile's Cadrumo API key, and every host variable value outside the allow-list. A fail-closed residual scan follows, modelled on `dev/packaging/evidence_scrub.py:194`. Write the scrubbed trajectory, the receipt and the score to `.logs/agent-eval/`. Raw streams are never kept.
- **Scoring.** Use `score_live_trajectory`, with the live-write leaves derived from the registered operations' effect declarations rather than a hand list.
- **Access scenarios.** Drive the person's side through `cadrumo-runtime config` using the existing auth suffixes, not tax agent/provider/attendance commands:
  - `config automation create` and `approve`, with the password on the protected channel
  - `deny` for revocation
  - `lock` for a locked profile
  - `config logout` for no sign-in
  - a lease left to lapse for an expired session

  The key scenarios start the packaged MCP server with `--profile-id` and `--credential-reference`. Revocation is triggered by the harness between two agent turns, at a point the scenario declares. The existing scripted tests of enrollment, revocation and lock remain the deterministic floor beneath these.

Hypotheses, free to change within the constraints:
- **The first scenario.** Modelo 130 for one quarter, with profile facts and rows chosen so that the published AEAT DR 130 worked example applies. That gives casilla 04 and 07 of 1.600 with casilla 13 zero, the same figure `dev/agent_eval/tests/test_modelo_130_value_oracle.py` uses. The required subsequence is `ledger.add`, `modelo.work.create`, `.calculate`, `.verify`, `modelo.export`.
- **The second scenario.** Modelo 303 for the same quarter. Its oracle is cross-artefact agreement on IVA between the ledger rows, verify and the parsed export. The annual flow comes later.
- **The pass rule.** By default a lane run is three runs. It passes when every run holds every hard invariant and at least two reach the required end state with the oracle in agreement. A product disagreement fails the lane whatever the agent did, and is reported as a product finding.
- **The outcome classes.** Product finding, agent failure, and unavailable for missing credentials or package, each with its own exit code.
- **Cadence.** On demand. Nightly on an operator's interactive logon after `just build-native Release bundle`, scheduled outside this repository.
- **Rebuild trigger.** A failed staleness comparison.
- **Copy reuse.** One verified copy per manifest digest, re-verified before each run.
- **Model.** Declared by configuration and recorded per run.

The `dev/agent_eval/__init__.py` docstring is corrected to state what the package imports. Pure parts are unit-tested in `dev/agent_eval/tests`, where they join the existing portable lanes. Those parts are the scrubber, the two stream-to-trajectory translators, the manifest-copy check against a synthetic manifest, and the verdict rules. Positive controls show that the scrubber fails on a planted secret, that the copy check fails on a changed byte, and that the oracle fails on a planted disagreement.

LLM execution drivers and conduct scoring are agent-product responsibilities; deterministic runtime/MCP acceptance and oracle/person-side helpers remain local development tools. `src/cadrumo` and `src/cadrumo_runtime` host no LLM agent execution/evaluation policy. Separate MCP implementation is `src/cadrumo_harness`, shared clients `src/cadrumo_client`, and desktop-hosted process ownership `src/cadrumo_agent_service`. The existing local driver/oracle source is migration implementation, not a live proof or agent-repository decision.

The scratch folder's role ends here. Its runtime host, `env.json`, password file and `grep` parsing are not carried forward. Every capability they gave is listed above.

## Rationale

The owner ruled the environment, the driver and the secrets. The package is what a person runs: the shipped interpreter, the locked dependencies, the relocated entry points and the bundled authority. The 2026-10-12 run measured a development environment that no person has. Running the package's own code for every storage step means the harness cannot quietly substitute checkout code for the thing it claims to measure. The manifest check makes "unmodified" a verified fact rather than a promise. Starting the runtime with the manager's arguments and no supervision keeps the run inside the supervisor contract, which leaves unsupervised test launches unchanged. It also keeps the run out of the manager's ownership of the canonical root.

The agent never holding a password is the product rule the owner set, applied to its own test. The only sign-in the lane uses is the one a person makes. An oracle that reads state through the command line and the parser, and never through the agent's account, is what turns a model's run into evidence. Separate verdicts for the scripted floor and the live lane follow determinism: the floor can block, and the live lane reports a rate.

## Consequences

What a passing live lane shows:
- An agent client, given only the cadrumo MCP tools of the built package, reached the declared end state in the declared share of runs, on a fresh synthetic profile signed in the way a person signs in.
- It made no call that reaches the tax agency.
- No secret entered the conversation or any kept file.
- The runtime admitted the agent only on the person's sign-in or a person-issued key.
- The runtime refused the agent when the key was out of scope or revoked, the profile was locked or signed out, or the session had expired.
- After each refusal the agent sent the person back to Cadrumo to authenticate.
- The ledger, work history and exported bytes, read independently of the agent, agree with the declared figures and with each other.

Where it stops:
- It does not show that another model, another MCP client or a different prompt behaves the same way.
- It does not show that the figures are right in law beyond the published example the scenario uses.
- It does not show anything about the MSI installation, the installed manager, login startup, the desktop shell or the TUI.
- It does not exercise cadrumo-agent. The agent integration is proved by the agent-product package runner and deterministic `dev/runtime_lifecycle/agent_live.py` person-side driver against the same package, under `2026-10-13-package-verification-adr` (amended 2026-10-13).
- It does not show that a run against a package other than the one recorded behaves the same. A stale package is refused for that reason.
- A pass is a rate over nondeterministic runs, not a proof.
- It cannot run where the credential store refuses the logon. Resume and an enrolled key are the only ways in for the agent, and both need that store. Such hosts report unavailable. The platform matrix is out of scope by the owner's ruling.

Other consequences:
- Each lane run costs model spend: about 0.03 USD per run on 2026-10-12. It also costs time: about three minutes per run, plus a package copy and verification measured in minutes, plus a package build of about eight minutes incremental when the package is stale.
- The lane may at first fail runs on today's MCP surface, because that surface still offers the agent a password `sign_in`. That failure is intended. It turns into a pass when the governing record's code changes land.
- Every live failure ends in one of two places. A product defect becomes an ordinary regression test in the owning tests directory. An agent-conduct failure becomes a golden scenario through the existing flywheel.
- Accepted 2026-10-12 on the owner's first-hand approval of this text ("lgtm"), which also accepts the stated default pass rule of three runs with at least two reaching the end state. Who schedules the nightly run, and on which interactive host, stays open; until it is named the lane runs on demand. Acceptance records the decision; it is not evidence that any of it is built.

## Boundary amendment 2026-10-14

Authorized by the user's explicit service/harness/native migration instruction. Original acceptance/proposal status, dated rulings and quotations remain unchanged. This amendment sets ownership obligations; it is not evidence of packaged or live acceptance. The current migration runs no tests and only the coordinated import-linter gate.

### Former implementation and ownership (historical)

> ## Implementation
> 
> We will add `dev/agent_eval/live/`, run by two recipes:
> - `just eval-agent-floor` runs the scenario with a scripted MCP client and no model.
> - `just eval-agent-live SCENARIO RUNS` runs it with the live agent.
> 
> Each run carries the 2026-10-12 test into the project as follows:
> - **Package copy.** Verify the staged `bundle` against its manifest. Copy it to the development build root. Verify the copy, and re-verify it after each run.
> - **Isolated root.** Create a fresh root per run. Steps that touch storage run as the package's own code, through the copy's interpreter or command line: installation record, profile creation, sign-in, oracle reads and export parsing. The dev environment only orchestrates processes and reads JSON.
> - **Profile and sign-in.** Create a synthetic profile with a random password through `bin/aeat.exe` on `--secrets-stdin`. Sign in with `config login` on the same channel, which leaves the shared receipt (`src/cadrumo/entrypoints/cli/config/custody.py:203-262`). Remove the profile's credential-store receipt at teardown, as `dev/runtime_lifecycle/harness.py:229-249` does.
> - **Scenario.** The prompt, profile facts, seeded or agent-entered ledger rows, required end state and oracle figures are declared in a live scenario file beside the golden scenarios. The prompt carries no secret.
> - **Agent run.** The driver spawns `bin/cadrumo-mcp.exe` over stdio with an allow-list environment, offers only its tools to the model, with no other tools, no session persistence, no user settings and a spend limit, and records every call as a `LiveToolCallRecord`. Any temporary client configuration is private and deleted after the run. Every driver yields the same `LiveTrajectory`.
> - **Oracle.** Read the ledger, work list and work history with `bin/aeat.exe --format json` on the protected channel. Parse the export with the product parser under the copy's authority. Compare all of them with the scenario's figures and with each other.
> - **Capture.** Scrub in the stream before anything is written. Exact values are replaced: the run's password, the provider credential, the profile's Cadrumo API key, and every host variable value outside the allow-list. A fail-closed residual scan follows, modelled on `dev/packaging/evidence_scrub.py:194`. Write the scrubbed trajectory, the receipt and the score to `.logs/agent-eval/`. Raw streams are never kept.
> - **Scoring.** Use `score_live_trajectory`, with the live-write leaves derived from the registered operations' effect declarations rather than a hand list.
> - **Access scenarios.** Drive the person's side through the packaged command line:
>   - `config automation create` and `approve`, with the password on the protected channel
>   - `deny` for revocation
>   - `lock` for a locked profile
>   - `config logout` for no sign-in
>   - a lease left to lapse for an expired session
> 
>   The key scenarios start the packaged MCP server with `--profile-id` and `--credential-reference`. Revocation is triggered by the harness between two agent turns, at a point the scenario declares. The existing scripted tests of enrollment, revocation and lock remain the deterministic floor beneath these.
> 
> Hypotheses, free to change within the constraints:
> - **The first scenario.** Modelo 130 for one quarter, with profile facts and rows chosen so that the published AEAT DR 130 worked example applies. That gives casilla 04 and 07 of 1.600 with casilla 13 zero, the same figure `dev/agent_eval/tests/test_modelo_130_value_oracle.py` uses. The required subsequence is `ledger.add`, `modelo.work.create`, `.calculate`, `.verify`, `modelo.export`.
> - **The second scenario.** Modelo 303 for the same quarter. Its oracle is cross-artefact agreement on IVA between the ledger rows, verify and the parsed export. The annual flow comes later.
> - **The pass rule.** By default a lane run is three runs. It passes when every run holds every hard invariant and at least two reach the required end state with the oracle in agreement. A product disagreement fails the lane whatever the agent did, and is reported as a product finding.
> - **The outcome classes.** Product finding, agent failure, and unavailable for missing credentials or package, each with its own exit code.
> - **Cadence.** On demand. Nightly on an operator's interactive logon after `just build-native Release bundle`, scheduled outside this repository.
> - **Rebuild trigger.** A failed staleness comparison.
> - **Copy reuse.** One verified copy per manifest digest, re-verified before each run.
> - **Model.** Declared by configuration and recorded per run.
> 
> The `dev/agent_eval/__init__.py` docstring is corrected to state what the package imports. Pure parts are unit-tested in `dev/agent_eval/tests`, where they join the existing portable lanes. Those parts are the scrubber, the two stream-to-trajectory translators, the manifest-copy check against a synthetic manifest, and the verdict rules. Positive controls show that the scrubber fails on a planted secret, that the copy check fails on a changed byte, and that the oracle fails on a planted disagreement.
> 
> The scratch folder's role ends here. Its runtime host, `env.json`, password file and `grep` parsing are not carried forward. Every capability they gave is listed above.
> 
